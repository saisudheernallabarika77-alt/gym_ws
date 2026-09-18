"""
Fitora RAG - Hybrid Retriever

Pipeline:
  1. parse_query()          -> hard constraints (budget, AC, ladies-only, ...)
  2. Chroma `where` filter  -> only gyms that actually satisfy them
  3. semantic ranking       -> order survivors by meaning
  4. post-filters           -> facility/equipment requirements the metadata
                               cannot express, plus user-location distance
  5. re-rank                -> blend semantic score with rating / price /
                               distance according to the user's sort intent

Graceful degradation: if the strict filter returns nothing, constraints are
relaxed one at a time (least important first) so the user always gets an
answer, together with a note about what was relaxed.
"""
from __future__ import annotations
import math
from typing import Any

from .query_parser import parse_query, to_chroma_where
from .vector_store import GymVectorStore

# Order in which constraints get dropped when nothing matches.
# Least important first; budget and gym_type are held back as long as possible
# because getting those wrong is what users actually complain about.
_RELAX_ORDER = [
    "min_coach_experience", "trial_available", "supplements",
    "min_rating", "required_equipment", "required_facilities",
    "locality", "max_distance_km", "is_ac",
    "coach_included", "gym_type", "min_fee",
]


def _haversine_km(lat1, lon1, lat2, lon2) -> float:
    R = 6371.0
    dlat, dlon = math.radians(lat2 - lat1), math.radians(lon2 - lon1)
    a = (math.sin(dlat / 2) ** 2
         + math.cos(math.radians(lat1)) * math.cos(math.radians(lat2)) * math.sin(dlon / 2) ** 2)
    return 2 * R * math.asin(math.sqrt(a))


class GymRetriever:
    def __init__(self, store: GymVectorStore | None = None,
                 gyms_by_id: dict[str, dict] | None = None) -> None:
        self.store = store or GymVectorStore.get()
        self._gyms = gyms_by_id or {}

    def attach_gyms(self, gyms: list[dict[str, Any]]) -> None:
        self._gyms = {g["gym_id"]: g for g in gyms}

    def _facilities_of(self, gym_id: str) -> tuple[set[str], set[str]] | None:
        """
        Facilities and equipment for one gym, for constraints the vector
        metadata cannot express (it only holds scalars, not lists).

        Prefers the attached corpus; otherwise falls back to the indexed
        document text, so the filter never silently passes everything just
        because nobody called attach_gyms().
        """
        g = self._gyms.get(gym_id)
        if g is not None:
            return ({f for f in g.get("facilities", [])},
                    {e["name"] for e in g.get("equipment", [])})
        return None

    # ------------------------------------------------------------------ main
    def retrieve(
        self,
        query: str,
        *,
        top_k: int = 6,
        user_lat: float | None = None,
        user_lon: float | None = None,
        oversample: int = 5,
    ) -> dict[str, Any]:
        parsed = parse_query(query)
        relaxed: list[str] = []
        work = dict(parsed)

        # Post-filters (facilities, equipment) cut the candidate list after the
        # vector search, so fetch a much deeper window when one is in play -
        # otherwise a rare combination looks like "no such gym exists".
        if parsed.get("required_facilities") or parsed.get("required_equipment"):
            oversample = max(oversample, 25)

        hits = self.store.search(query, where=to_chroma_where(work), top_k=top_k * oversample)
        hits = self._post_filter(hits, work)

        # progressively relax until we have something
        while not hits and any(k in work for k in _RELAX_ORDER):
            for key in _RELAX_ORDER:
                if key in work:
                    work.pop(key)
                    relaxed.append(key)
                    break
            hits = self.store.search(query, where=to_chroma_where(work), top_k=top_k * oversample)
            hits = self._post_filter(hits, work)

        # last resort: drop the budget ceiling too
        if not hits and "max_fee" in work:
            work.pop("max_fee"); relaxed.append("max_fee")
            hits = self.store.search(query, where=to_chroma_where(work), top_k=top_k * oversample)
            hits = self._post_filter(hits, work)

        hits = self._add_distance(hits, user_lat, user_lon)
        hits = self._rerank(hits, parsed)

        return {
            "query": query,
            "parsed": parsed,
            "relaxed_constraints": relaxed,
            "total_matches": len(hits),
            "results": hits[:top_k],
        }

    # ------------------------------------------------------------ post-filter
    def _post_filter(self, hits: list[dict], p: dict) -> list[dict]:
        req_fac = p.get("required_facilities") or []
        req_eq = p.get("required_equipment") or []
        if not (req_fac or req_eq):
            return hits

        out = []
        for h in hits:
            sets = self._facilities_of(h["gym_id"])
            if sets is None:
                # No corpus attached: match against the indexed document text,
                # which restates every facility and equipment name verbatim.
                doc = h.get("document", "")
                if (all(f in doc for f in req_fac)
                        and all(e in doc for e in req_eq)):
                    out.append(h)
                continue
            fac, eq = sets
            if all(f in fac for f in req_fac) and all(e in eq for e in req_eq):
                out.append(h)
        return out

    # --------------------------------------------------------------- distance
    def _add_distance(self, hits: list[dict], lat: float | None, lon: float | None) -> list[dict]:
        for h in hits:
            m = h["metadata"]
            h["distance_from_user_km"] = (
                round(_haversine_km(lat, lon, m["latitude"], m["longitude"]), 2)
                if lat is not None and lon is not None else None
            )
        return hits

    # ----------------------------------------------------------------- rerank
    def _rerank(self, hits: list[dict], p: dict) -> list[dict]:
        if not hits:
            return hits
        sort = p.get("sort")
        fees = [h["metadata"]["monthly_fee"] for h in hits]
        fmin, fmax = min(fees), max(fees)
        dists = [h["distance_from_user_km"] for h in hits if h.get("distance_from_user_km") is not None]
        dmax = max(dists) if dists else None

        for h in hits:
            m = h["metadata"]
            sem = h["score"]
            rating_n = (m["rating"] - 3.0) / 2.0                       # 0..1
            price_n = 1 - ((m["monthly_fee"] - fmin) / (fmax - fmin)) if fmax > fmin else 0.5
            if h.get("distance_from_user_km") is not None and dmax:
                dist_n = 1 - (h["distance_from_user_km"] / dmax)
            else:
                dist_n = 0.5

            if sort == "cheapest":
                w = (0.30, 0.10, 0.55, 0.05)
            elif sort == "best_rated":
                w = (0.30, 0.55, 0.05, 0.10)
            elif sort == "nearest":
                w = (0.25, 0.15, 0.10, 0.50)
            else:
                w = (0.55, 0.22, 0.13, 0.10)

            h["final_score"] = round(
                w[0] * sem + w[1] * rating_n + w[2] * price_n + w[3] * dist_n, 4
            )
            h["score_breakdown"] = {
                "semantic": round(sem, 3), "rating": round(rating_n, 3),
                "price": round(price_n, 3), "distance": round(dist_n, 3),
            }

        return sorted(hits, key=lambda x: -x["final_score"])
