"""
Fitora RAG - Document Builder

Converts each structured gym record into a dense, retrieval-optimised natural
language document plus a flat metadata dict for filtered vector search.

Design notes:
  * The document text deliberately restates numbers in several phrasings
    ("Rs.1200 per month", "1200 rupees monthly", "budget friendly under 1500")
    so that semantic search matches the way real users type queries.
  * Hard numeric facts (fee, rating, distance, AC) also go into metadata so
    Chroma can pre-filter with `where` clauses before semantic ranking.
"""
from __future__ import annotations
from typing import Any


def _fee_band(fee: int) -> str:
    if fee < 800:   return "very cheap budget gym under 800 rupees"
    if fee < 1200:  return "affordable low cost gym under 1200 rupees"
    if fee < 1500:  return "budget friendly gym under 1500 rupees"
    if fee < 2000:  return "mid range gym under 2000 rupees"
    if fee < 2500:  return "premium gym under 2500 rupees"
    return "high end luxury premium gym above 2500 rupees"


def _rating_band(r: float) -> str:
    if r >= 4.5: return "excellent top rated highly rated"
    if r >= 4.0: return "very good well rated"
    if r >= 3.5: return "good decent rated"
    return "average rated"


def _distance_band(km: float) -> str:
    if km <= 5:  return "very close to Kakinada city centre nearby walking distance"
    if km <= 15: return "close to Kakinada within city limits nearby"
    if km <= 35: return "near Kakinada short drive away"
    if km <= 60: return "moderate distance from Kakinada"
    return "far from Kakinada outer region"


def build_document(gym: dict[str, Any]) -> str:
    """Build the text that gets embedded for semantic retrieval."""
    loc, pr, tm, ct = gym["location"], gym["pricing"], gym["timings"], gym["contact"]
    parts: list[str] = []

    # --- identity & place -------------------------------------------------
    parts.append(
        f"{gym['name']} is a {gym['gym_type'].lower()} {gym['ac_status']} fitness gym "
        f"located at {loc['address_line']}, {loc['locality']}, {loc['district']} district, "
        f"{loc['state']} {loc['pincode']}. "
        f"It is {loc['distance_from_kakinada_km']} km from Kakinada city centre "
        f"({_distance_band(loc['distance_from_kakinada_km'])})."
    )
    parts.append(gym["description"])

    # --- pricing (restated several ways for query matching) ---------------
    fee = pr["monthly_fee"]
    price_lines = [
        f"Membership fee is Rs.{fee} per month ({fee} rupees monthly membership).",
        f"This is a {_fee_band(fee)}.",
    ]
    if pr["coach_included"]:
        price_lines.append(
            f"Personal coach and trainer is INCLUDED free in the Rs.{fee} membership fee. "
            f"No separate or extra coach charges. Membership with coach costs Rs.{fee} per month."
        )
    else:
        cf = pr["coach_fee_separate"]
        price_lines.append(
            f"Coach fee is SEPARATE and NOT included. Gym-only membership is Rs.{fee} per month. "
            f"A personal coach costs an extra Rs.{cf} per month. "
            f"Total membership with personal trainer is Rs.{pr['membership_with_coach']} per month."
        )
    if pr["registration_fee"]:
        price_lines.append(f"One-time registration/admission fee of Rs.{pr['registration_fee']}.")
    else:
        price_lines.append("No registration or admission fee, zero joining charges.")
    for pl in pr["plans"]:
        price_lines.append(
            f"{pl['plan_name']} plan: Rs.{pl['price']} for {pl['duration_months']} month(s), "
            f"about Rs.{pl['effective_monthly']} per month"
            + (f", saves Rs.{pl['savings']}." if pl["savings"] > 0 else ".")
        )
    if pr.get("trial_available") and pr.get("trial_days"):
        price_lines.append(f"Free trial available for {pr['trial_days']} day(s) before joining.")
    parts.append(" ".join(price_lines))

    # --- amenities --------------------------------------------------------
    ac_txt = ("This gym is fully air conditioned AC gym with cooling."
              if gym["is_air_conditioned"] else
              "This is a Non-AC gym without air conditioning, naturally ventilated.")
    supp_txt = ("Protein supplements, whey and nutrition products are sold at the gym."
                if gym["supplements_available"] else
                "Supplements are not sold at this gym.")
    parts.append(f"{ac_txt} {supp_txt} Facilities available: {', '.join(gym['facilities'])}.")

    # --- equipment --------------------------------------------------------
    eq = gym["equipment"]
    by_cat: dict[str, list[str]] = {}
    for e in eq:
        by_cat.setdefault(e["category"], []).append(e["name"])
    eq_lines = [f"The gym has {len(eq)} equipment items."]
    for cat, names in by_cat.items():
        eq_lines.append(f"{cat} equipment: {', '.join(names)}.")
    parts.append(" ".join(eq_lines))

    # --- coaches ----------------------------------------------------------
    co = gym["coaches"]
    if co:
        specs = sorted({s for c in co for s in c["specialisations"]})
        max_exp = max(c["experience_years"] for c in co)
        coach_lines = [
            f"{len(co)} certified trainers and coaches work here, "
            f"with up to {max_exp} years of experience.",
            f"Training specialisations offered: {', '.join(specs)}.",
        ]
        for c in co[:5]:
            coach_lines.append(
                f"Coach {c['name']} ({c['gender']}) has {c['experience_years']} years experience "
                f"in {', '.join(c['specialisations'])}, certified: {', '.join(c['certifications'])}."
            )
        parts.append(" ".join(coach_lines))

    # --- timings ----------------------------------------------------------
    t_line = (f"Timings: morning {tm['morning_open']} to {tm['morning_close']}, "
              f"evening {tm['evening_open']} to {tm['evening_close']}. "
              f"Open {tm['open_days']}.")
    if tm.get("weekly_off"):
        t_line += f" Weekly off on {tm['weekly_off']}."
    if tm.get("ladies_timing"):
        t_line += f" Separate ladies-only timing {tm['ladies_timing']}."
    parts.append(t_line)

    # --- social proof & contact ------------------------------------------
    parts.append(
        f"Rated {gym['rating']} out of 5 stars from {gym['review_count']} customer reviews "
        f"({_rating_band(gym['rating'])}). "
        f"{gym['member_count']} active members. Established in {gym['established_year']}. "
        f"Contact phone {ct['phone']}."
    )

    return "\n".join(parts)


def build_metadata(gym: dict[str, Any]) -> dict[str, Any]:
    """Flat, Chroma-safe metadata (str / int / float / bool only)."""
    loc, pr = gym["location"], gym["pricing"]
    return {
        "gym_id": gym["gym_id"],
        "name": gym["name"],
        "slug": gym["slug"],
        "tier": gym["tier"],
        "gym_type": gym["gym_type"],
        # location
        "locality": loc["locality"],
        "district": loc["district"],
        "state": loc["state"],
        "pincode": str(loc["pincode"]),
        "latitude": float(loc["latitude"]),
        "longitude": float(loc["longitude"]),
        "distance_km": float(loc["distance_from_kakinada_km"]),
        # pricing (filterable)
        "monthly_fee": int(pr["monthly_fee"]),
        "coach_included": bool(pr["coach_included"]),
        "coach_fee": int(pr["coach_fee_separate"]),
        "fee_with_coach": int(pr["membership_with_coach"]),
        "registration_fee": int(pr["registration_fee"]),
        "trial_available": bool(pr.get("trial_available", False)),
        # amenities (filterable)
        "is_ac": bool(gym["is_air_conditioned"]),
        "supplements": bool(gym["supplements_available"]),
        "equipment_count": len(gym["equipment"]),
        "coach_count": len(gym["coaches"]),
        "max_coach_experience": max((c["experience_years"] for c in gym["coaches"]), default=0),
        # social proof
        "rating": float(gym["rating"]),
        "review_count": int(gym["review_count"]),
        "member_count": int(gym["member_count"]),
        "established_year": int(gym["established_year"]),
        "verified": bool(gym["verified"]),
        "status": gym["status"],
    }
