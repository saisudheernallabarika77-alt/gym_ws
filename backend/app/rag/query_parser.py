"""
Fitora RAG - Hybrid Query Parser

Pure-regex/keyword extraction of HARD constraints from a natural-language query,
so the vector search can pre-filter before semantic ranking.

Why hybrid: a pure embedding search cannot reliably honour "under Rs.1500" -
embeddings blur numbers. We extract the number, filter exactly, then rank
the survivors semantically. This is what makes the answers trustworthy.

Handles Indian English + Telugu-English (Tenglish) phrasing, e.g.:
    "below 1500 fee gyms"
    "1500 lopu AC gym kavali"
    "gyms near Kakinada with personal trainer under 2000"
    "ladies only gym with zumba"
"""
from __future__ import annotations
import re
from typing import Any

# ---------------------------------------------------------------- numbers
_NUM = r"(?:rs\.?|rupees|inr|₹)?\s*(\d{3,5})\s*(?:rs|rupees|inr|/-)?"

_UNDER_WORDS = r"(?:under|below|less\s+than|lesser\s+than|upto|up\s+to|within|max(?:imum)?|cheaper\s+than|not\s+more\s+than|lopu|thakkuva|loki)"
_OVER_WORDS  = r"(?:above|over|more\s+than|greater\s+than|at\s+least|minimum|min|starting\s+from|ekkuva|paiga)"
_RANGE_WORDS = r"(?:between|from)"

# ---------------------------------------------------------------- keywords
_AC_YES = ("ac gym", "a/c", "air condition", "airconditioned", "ac ", "cool gym", "ac unna")
_AC_NO  = ("non ac", "non-ac", "no ac", "without ac", "not ac", "ac leni")

_COACH_INCLUDED = ("coach included", "trainer included", "free coach", "free trainer",
                   "coach free", "included coach", "with free trainer", "coach kalipi",
                   "trainer kalipi", "coach included lo")
_COACH_WANTED   = ("coach", "trainer", "personal training", "pt ", "guidance", "instructor")

_SUPPLEMENTS = ("supplement", "protein", "whey", "nutrition store", "mass gainer")
_LADIES      = ("ladies", "women", "female only", "girls", "womens", "ladies only", "mahila")
_MEN         = ("men only", "mens gym", "gents", "male only")

_TRIAL       = ("trial", "free trial", "demo", "test day", "try")
_PARKING     = ("parking",)
_SHOWER      = ("shower", "bath")
_LOCKER      = ("locker",)
_YOGA        = ("yoga",)
_ZUMBA       = ("zumba", "aerobic", "dance fitness")
_CARDIO      = ("cardio", "treadmill", "running", "weight loss machine")
_CROSSFIT    = ("crossfit", "functional", "hiit")
_SWIM        = ("swimming", "pool")
_STEAM       = ("steam", "sauna", "spa")

_NEAR_ME     = ("near me", "nearby", "close to me", "around me", "closest", "nearest",
                "daggara", "dagger", "pakkana", "near by")

_GOALS = {
    "weight_loss":  ("weight loss", "lose weight", "fat loss", "slim", "reduce weight",
                     "weight taggadam", "baruvu thaggu"),
    "muscle_gain":  ("muscle", "bulk", "mass gain", "bodybuilding", "body building",
                     "gain weight", "muscle growth", "size"),
    "strength":     ("strength", "powerlifting", "power lifting", "heavy lifting", "strong"),
    "general":      ("fitness", "general fitness", "healthy", "stay fit", "maintain"),
    "rehab":        ("rehab", "injury", "physiotherapy", "recovery", "back pain"),
}

_SORTS = {
    "cheapest":   ("cheapest", "lowest price", "most affordable", "low cost", "budget",
                   "takkuva", "thakkuva rate", "cheap"),
    "best_rated": ("best", "top rated", "highest rated", "best rated", "good rating",
                   "manchi", "top", "popular"),
    "nearest":    _NEAR_ME,
}

# Known localities in the 100 km service region (for place-name filtering)
KNOWN_LOCALITIES = [
    "kakinada", "rajamahendravaram", "rajahmundry", "amalapuram", "pithapuram",
    "samalkot", "samarlakota", "tuni", "peddapuram", "mandapeta", "ramachandrapuram",
    "kovvur", "nidadavolu", "tanuku", "tadepallegudem", "bhimavaram", "palakollu",
    "narasapuram", "razole", "mummidivaram", "kothapeta", "ravulapalem", "yanam",
    "annavaram", "gollaprolu", "prathipadu", "jaggampeta", "yeleswaram", "narsipatnam",
    "addateegala", "rampachodavaram", "draksharamam", "rajanagaram", "kathipudi",
    "payakaraopeta", "elamanchilli", "chintapalle", "nidadavole",
]


def _find_amounts(q: str) -> list[int]:
    return [int(m) for m in re.findall(r"\b(\d{3,5})\b", q)]


def parse_query(query: str) -> dict[str, Any]:
    """Return structured constraints extracted from a free-text query."""
    q = " " + query.lower().strip() + " "
    q = q.replace("₹", " rs ").replace("k ", "000 ")
    out: dict[str, Any] = {"raw_query": query}

    # ---------------- budget ----------------
    rng = re.search(rf"{_RANGE_WORDS}\s*{_NUM}\s*(?:to|-|and|&)\s*{_NUM}", q)
    if rng:
        lo, hi = sorted((int(rng.group(1)), int(rng.group(2))))
        out["min_fee"], out["max_fee"] = lo, hi
    else:
        m = re.search(rf"{_UNDER_WORDS}\s*{_NUM}", q) or re.search(rf"{_NUM}\s*{_UNDER_WORDS}", q)
        if m:
            out["max_fee"] = int(m.group(1))
        m2 = re.search(rf"{_OVER_WORDS}\s*{_NUM}", q) or re.search(rf"{_NUM}\s*{_OVER_WORDS}", q)
        if m2:
            out["min_fee"] = int(m2.group(1))
        # bare amount + fee/budget word  ->  treat as a ceiling
        if "max_fee" not in out and "min_fee" not in out:
            if re.search(r"(fee|budget|price|cost|rate|charge|month)", q):
                amts = [a for a in _find_amounts(q) if 200 <= a <= 20000]
                if amts:
                    out["max_fee"] = max(amts)

    # ---------------- AC ----------------
    if any(k in q for k in _AC_NO):
        out["is_ac"] = False
    elif any(k in q for k in _AC_YES):
        out["is_ac"] = True

    # ---------------- coach ----------------
    if any(k in q for k in _COACH_INCLUDED):
        out["coach_included"] = True
    if any(k in q for k in _COACH_WANTED):
        out["wants_coach"] = True
    m = re.search(r"(\d{1,2})\+?\s*(?:years?|yrs?)\s*(?:of\s*)?experien", q)
    if m:
        out["min_coach_experience"] = int(m.group(1))

    # ---------------- gym type ----------------
    if any(k in q for k in _LADIES):
        out["gym_type"] = "Ladies Only"
    elif any(k in q for k in _MEN):
        out["gym_type"] = "Men Only"

    # ---------------- boolean amenities ----------------
    if any(k in q for k in _SUPPLEMENTS): out["supplements"] = True
    if any(k in q for k in _TRIAL):       out["trial_available"] = True

    facilities: list[str] = []
    if any(k in q for k in _PARKING): facilities.append("Parking")
    if any(k in q for k in _SHOWER):  facilities.append("Shower")
    if any(k in q for k in _LOCKER):  facilities.append("Locker Facility")
    if any(k in q for k in _YOGA):    facilities.append("Yoga Classes")
    if any(k in q for k in _ZUMBA):   facilities.append("Zumba / Aerobics")
    if any(k in q for k in _SWIM):    facilities.append("Swimming Pool")
    if any(k in q for k in _STEAM):   facilities.append("Steam Bath / Sauna")
    if facilities:
        out["required_facilities"] = facilities

    equipment: list[str] = []
    if any(k in q for k in _CARDIO):   equipment.append("Treadmill")
    if any(k in q for k in _CROSSFIT): equipment.append("Battle Ropes")
    if "smith" in q:                   equipment.append("Smith Machine")
    if "leg press" in q:               equipment.append("Leg Press Machine")
    if "cable" in q:                   equipment.append("Cable Crossover")
    if equipment:
        out["required_equipment"] = equipment

    # ---------------- rating ----------------
    m = re.search(r"(\d(?:\.\d)?)\s*(?:\+|plus|star|rating|above)", q)
    if m:
        v = float(m.group(1))
        if 1 <= v <= 5:
            out["min_rating"] = v

    # ---------------- distance / locality ----------------
    m = re.search(r"within\s*(\d{1,3})\s*(?:km|kilometer|kilometre|k\.?m)", q)
    if m:
        out["max_distance_km"] = float(m.group(1))
    if any(k in q for k in _NEAR_ME):
        out["near_me"] = True
    for loc in KNOWN_LOCALITIES:
        if loc in q:
            out["locality"] = loc.title()
            break

    # ---------------- goal ----------------
    for goal, kws in _GOALS.items():
        if any(k in q for k in kws):
            out["goal"] = goal
            break

    # ---------------- sort intent ----------------
    for s, kws in _SORTS.items():
        if any(k in q for k in kws):
            out["sort"] = s
            break

    return out


def to_chroma_where(p: dict[str, Any]) -> dict[str, Any] | None:
    """Translate parsed constraints into a ChromaDB `where` filter."""
    clauses: list[dict[str, Any]] = [{"status": {"$eq": "active"}}]

    if "max_fee" in p:  clauses.append({"monthly_fee": {"$lte": p["max_fee"]}})
    if "min_fee" in p:  clauses.append({"monthly_fee": {"$gte": p["min_fee"]}})
    if "is_ac" in p:    clauses.append({"is_ac": {"$eq": p["is_ac"]}})
    if p.get("coach_included"):        clauses.append({"coach_included": {"$eq": True}})
    if p.get("supplements"):           clauses.append({"supplements": {"$eq": True}})
    if p.get("trial_available"):       clauses.append({"trial_available": {"$eq": True}})
    if "gym_type" in p:                clauses.append({"gym_type": {"$eq": p["gym_type"]}})
    if "min_rating" in p:              clauses.append({"rating": {"$gte": p["min_rating"]}})
    if "max_distance_km" in p:         clauses.append({"distance_km": {"$lte": p["max_distance_km"]}})
    if "min_coach_experience" in p:    clauses.append({"max_coach_experience": {"$gte": p["min_coach_experience"]}})
    if "locality" in p:                clauses.append({"locality": {"$eq": p["locality"]}})

    if len(clauses) == 1:
        return clauses[0]
    return {"$and": clauses}
