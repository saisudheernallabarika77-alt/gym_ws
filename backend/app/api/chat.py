"""
Fitora - RAG chatbot endpoint.

This is the default surface of the user portal: the member types what they
want in plain language ("AC gym below 1500 near me with a personal trainer")
and gets grounded recommendations drawn only from indexed gyms.
"""
from __future__ import annotations
import json
import logging
from typing import Any

from fastapi import APIRouter, HTTPException, status
from fastapi.responses import StreamingResponse
from pydantic import BaseModel, Field

from ..core.config import settings
from ..db.models import Gym, GymStatus
from ..rag.chatbot import FitoraChatbot
from ..rag.retriever import GymRetriever
from ..rag.vector_store import GymVectorStore
from .deps import DbSession, OptionalUser

log = logging.getLogger(__name__)
router = APIRouter(prefix="/chat", tags=["chat"])

_retriever: GymRetriever | None = None
_bot: FitoraChatbot | None = None


def get_retriever() -> GymRetriever:
    global _retriever
    if _retriever is None:
        _retriever = GymRetriever(GymVectorStore.get())
    return _retriever


def get_bot() -> FitoraChatbot:
    global _bot
    if _bot is None:
        _bot = FitoraChatbot(model=settings.OLLAMA_MODEL, host=settings.OLLAMA_HOST)
    return _bot


class ChatTurn(BaseModel):
    role: str
    content: str


class ChatRequest(BaseModel):
    message: str = Field(min_length=1, max_length=500)
    history: list[ChatTurn] = Field(default_factory=list)
    latitude: float | None = None
    longitude: float | None = None
    top_k: int = Field(default=6, ge=1, le=12)


def _gym_cards(db, hits: list[dict[str, Any]]) -> list[dict[str, Any]]:
    """Attach live DB rows so the chat can render real gym cards, not just text."""
    codes = [h["gym_id"] for h in hits]
    if not codes:
        return []
    rows = {g.gym_code: g for g in db.query(Gym)
            .filter(Gym.gym_code.in_(codes), Gym.status == GymStatus.active).all()}

    cards = []
    for h in hits:
        g = rows.get(h["gym_id"])
        if not g:
            continue
        cards.append({
            "gym_code": g.gym_code,
            "id": g.id,
            "name": g.name,
            "slug": g.slug,
            "cover_image": g.cover_image,
            "locality": g.locality,
            "district": g.district,
            "address_line": g.address_line,
            "latitude": g.latitude,
            "longitude": g.longitude,
            "distance_km": h.get("distance_from_user_km"),
            "monthly_fee": g.monthly_fee,
            "coach_included": g.coach_included,
            "coach_fee_separate": g.coach_fee_separate,
            "fee_with_coach": g.monthly_fee + (0 if g.coach_included else g.coach_fee_separate),
            "coach_fee_note": ("Coach included in fee" if g.coach_included
                               else f"Coach +Rs.{g.coach_fee_separate}/mo"),
            "ac_status": "AC" if g.is_air_conditioned else "Non-AC",
            "gym_type": g.gym_type,
            "supplements_available": g.supplements_available,
            "rating": g.rating,
            "review_count": g.review_count,
            "verified": g.verified,
            "facilities": (g.facilities or [])[:5],
            "match_score": h.get("final_score"),
            "why": h.get("score_breakdown"),
        })
    return cards


def _explain(parsed: dict[str, Any], relaxed: list[str]) -> dict[str, Any]:
    """Human-readable version of what the parser understood - shown as chips."""
    chips = []
    if "max_fee" in parsed: chips.append(f"Under Rs.{parsed['max_fee']}/month")
    if "min_fee" in parsed: chips.append(f"Above Rs.{parsed['min_fee']}/month")
    if parsed.get("is_ac") is True:  chips.append("AC gym")
    if parsed.get("is_ac") is False: chips.append("Non-AC gym")
    if parsed.get("coach_included"): chips.append("Coach fee included")
    elif parsed.get("wants_coach"):  chips.append("Personal trainer")
    if "gym_type" in parsed: chips.append(parsed["gym_type"])
    if parsed.get("supplements"): chips.append("Supplements available")
    if parsed.get("trial_available"): chips.append("Free trial")
    if "min_rating" in parsed: chips.append(f"{parsed['min_rating']}+ rating")
    if "locality" in parsed: chips.append(f"In {parsed['locality']}")
    if parsed.get("near_me"): chips.append("Near me")
    if "max_distance_km" in parsed: chips.append(f"Within {parsed['max_distance_km']:g} km")
    if "min_coach_experience" in parsed:
        chips.append(f"{parsed['min_coach_experience']}+ yrs coach experience")
    for f in parsed.get("required_facilities", []): chips.append(f)
    for e in parsed.get("required_equipment", []): chips.append(e)
    if "goal" in parsed: chips.append(parsed["goal"].replace("_", " ").title())

    return {
        "understood": chips,
        "relaxed": [r.replace("_", " ") for r in relaxed],
        "note": ("No gym matched every condition, so some were relaxed."
                 if relaxed else None),
    }


@router.post("")
def chat(payload: ChatRequest, db: DbSession, user: OptionalUser):
    retriever = get_retriever()
    if retriever.store.count() == 0:
        raise HTTPException(
            status.HTTP_503_SERVICE_UNAVAILABLE,
            "Gym index is empty. Run: python -m scripts.build_index",
        )

    lat = payload.latitude if payload.latitude is not None else (user.latitude if user else None)
    lon = payload.longitude if payload.longitude is not None else (user.longitude if user else None)

    retrieval = retriever.retrieve(payload.message, top_k=payload.top_k,
                                   user_lat=lat, user_lon=lon)
    answer = get_bot().answer(
        retrieval, history=[t.model_dump() for t in payload.history]
    )

    return {
        "answer": answer,
        "gyms": _gym_cards(db, retrieval["results"]),
        "interpretation": _explain(retrieval["parsed"], retrieval["relaxed_constraints"]),
        "total_matches": retrieval["total_matches"],
        "used_location": lat is not None,
    }


@router.post("/stream")
def chat_stream(payload: ChatRequest, db: DbSession, user: OptionalUser):
    """Server-sent events - the answer types out while gym cards render instantly."""
    retriever = get_retriever()
    if retriever.store.count() == 0:
        raise HTTPException(status.HTTP_503_SERVICE_UNAVAILABLE, "Gym index is empty.")

    lat = payload.latitude if payload.latitude is not None else (user.latitude if user else None)
    lon = payload.longitude if payload.longitude is not None else (user.longitude if user else None)

    retrieval = retriever.retrieve(payload.message, top_k=payload.top_k,
                                   user_lat=lat, user_lon=lon)
    cards = _gym_cards(db, retrieval["results"])
    interpretation = _explain(retrieval["parsed"], retrieval["relaxed_constraints"])
    history = [t.model_dump() for t in payload.history]

    def events():
        yield ("event: meta\ndata: "
               + json.dumps({"gyms": cards, "interpretation": interpretation,
                             "total_matches": retrieval["total_matches"]})
               + "\n\n")
        for piece in get_bot().answer_stream(retrieval, history=history):
            yield "event: token\ndata: " + json.dumps({"t": piece}) + "\n\n"
        yield "event: done\ndata: {}\n\n"

    return StreamingResponse(
        events(),
        media_type="text/event-stream",
        headers={"Cache-Control": "no-cache", "X-Accel-Buffering": "no"},
    )


@router.get("/suggestions")
def suggestions(db: DbSession):
    """Starter prompts shown on the empty chat screen."""
    return {
        "suggestions": [
            "AC gym under Rs.1500 near me",
            "Cheapest gym with a personal trainer included",
            "Ladies only gym with zumba and yoga",
            "Best rated gym in Kakinada for muscle gain",
            "Gym under Rs.1000 with a treadmill and free trial",
            "Gym with 10+ years experienced coach for weight loss",
            "Non-AC budget gym within 5 km",
            "Premium gym with supplements and steam bath",
        ]
    }


@router.get("/health")
def health():
    store = GymVectorStore.get()
    bot = get_bot()
    return {
        "indexed_gyms": store.count(),
        "embedding_model": settings.EMBED_MODEL,
        "llm_model": settings.OLLAMA_MODEL,
        "llm_available": bot.available(),
        "ready": store.count() > 0,
    }
