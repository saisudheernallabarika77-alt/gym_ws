"""
Fitora - Public gym discovery.

Search, filter, sort and compare gyms; fetch the pin-to-pin detail page the
spec asks for (contact, trainers with experience, equipment with real photos,
whether the coach fee is included or separate, location, timings).
"""
from __future__ import annotations
import math
from typing import Any, Literal

from fastapi import APIRouter, HTTPException, Query, status
from sqlalchemy import func, or_

from ..db.models import Coach, Equipment, Gym, GymPlan, GymStatus, Review, User
from .deps import DbSession, OptionalUser

router = APIRouter(prefix="/gyms", tags=["gyms"])


def _haversine_km(lat1, lon1, lat2, lon2) -> float:
    R = 6371.0
    dlat, dlon = math.radians(lat2 - lat1), math.radians(lon2 - lon1)
    a = (math.sin(dlat / 2) ** 2
         + math.cos(math.radians(lat1)) * math.cos(math.radians(lat2)) * math.sin(dlon / 2) ** 2)
    return 2 * R * math.asin(math.sqrt(a))


def _card(g: Gym, *, distance_km: float | None = None) -> dict[str, Any]:
    """Compact shape for listing grids."""
    return {
        "id": g.id,
        "gym_code": g.gym_code,
        "name": g.name,
        "slug": g.slug,
        "tier": g.tier,
        "gym_type": g.gym_type,
        "cover_image": g.cover_image,
        "locality": g.locality,
        "district": g.district,
        "address_line": g.address_line,
        "latitude": g.latitude,
        "longitude": g.longitude,
        "distance_km": round(distance_km, 2) if distance_km is not None else None,
        "monthly_fee": g.monthly_fee,
        "coach_included": g.coach_included,
        "coach_fee_separate": g.coach_fee_separate,
        "fee_with_coach": g.monthly_fee + (0 if g.coach_included else g.coach_fee_separate),
        "registration_fee": g.registration_fee,
        "trial_available": g.trial_available,
        "trial_days": g.trial_days,
        "is_air_conditioned": g.is_air_conditioned,
        "ac_status": "AC" if g.is_air_conditioned else "Non-AC",
        "supplements_available": g.supplements_available,
        "rating": g.rating,
        "review_count": g.review_count,
        "member_count": g.member_count,
        "verified": g.verified,
        # Whether this gym's name and location are real, sourced from
        # OpenStreetMap, versus a realistic placeholder generated to fill out
        # the demo dataset. See the gym detail endpoint's `data_source` block
        # for the full explanation shown to the user.
        "data_source": g.data_source,
        "is_real_listing": g.data_source == "openstreetmap",
        "facilities": (g.facilities or [])[:6],
        "timings": f"{g.morning_open}-{g.morning_close}, {g.evening_open}-{g.evening_close}",
    }


@router.get("")
def list_gyms(
    db: DbSession,
    user: OptionalUser,
    q: str | None = Query(None, description="Free-text name / locality search"),
    min_fee: int | None = Query(None, ge=0),
    max_fee: int | None = Query(None, ge=0),
    is_ac: bool | None = None,
    coach_included: bool | None = None,
    gym_type: str | None = None,
    supplements: bool | None = None,
    trial_available: bool | None = None,
    min_rating: float | None = Query(None, ge=0, le=5),
    locality: str | None = None,
    district: str | None = None,
    lat: float | None = None,
    lon: float | None = None,
    max_distance_km: float | None = Query(None, gt=0, le=200),
    sort: Literal["relevance", "price_low", "price_high", "rating",
                  "distance", "popular"] = "relevance",
    page: int = Query(1, ge=1),
    page_size: int = Query(12, ge=1, le=60),
):
    query = db.query(Gym).filter(Gym.status == GymStatus.active)

    if q:
        like = f"%{q.strip()}%"
        query = query.filter(or_(Gym.name.ilike(like),
                                 Gym.locality.ilike(like),
                                 Gym.district.ilike(like),
                                 Gym.address_line.ilike(like)))
    if min_fee is not None:      query = query.filter(Gym.monthly_fee >= min_fee)
    if max_fee is not None:      query = query.filter(Gym.monthly_fee <= max_fee)
    if is_ac is not None:        query = query.filter(Gym.is_air_conditioned == is_ac)
    if coach_included is not None: query = query.filter(Gym.coach_included == coach_included)
    if gym_type:                 query = query.filter(Gym.gym_type == gym_type)
    if supplements is not None:  query = query.filter(Gym.supplements_available == supplements)
    if trial_available is not None: query = query.filter(Gym.trial_available == trial_available)
    if min_rating is not None:   query = query.filter(Gym.rating >= min_rating)
    if locality:                 query = query.filter(Gym.locality.ilike(f"%{locality}%"))
    if district:                 query = query.filter(Gym.district.ilike(f"%{district}%"))

    # fall back to the signed-up address when the browser gives no fix
    if lat is None and user and user.latitude:
        lat, lon = user.latitude, user.longitude

    rows = query.all()

    scored: list[tuple[Gym, float | None]] = []
    for g in rows:
        d = (_haversine_km(lat, lon, g.latitude, g.longitude)
             if lat is not None and lon is not None and g.latitude else None)
        if max_distance_km is not None and (d is None or d > max_distance_km):
            continue
        scored.append((g, d))

    if sort == "price_low":
        scored.sort(key=lambda x: x[0].monthly_fee)
    elif sort == "price_high":
        scored.sort(key=lambda x: -x[0].monthly_fee)
    elif sort == "rating":
        scored.sort(key=lambda x: (-x[0].rating, -x[0].review_count))
    elif sort == "popular":
        scored.sort(key=lambda x: (-x[0].member_count, -x[0].rating))
    elif sort == "distance":
        scored.sort(key=lambda x: (x[1] is None, x[1] if x[1] is not None else 1e9))
    else:  # relevance: verified + rating + a nudge for nearby
        scored.sort(key=lambda x: (
            -(1 if x[0].verified else 0),
            -x[0].rating,
            x[1] if x[1] is not None else 1e9,
        ))

    total = len(scored)
    start = (page - 1) * page_size
    window = scored[start:start + page_size]

    return {
        "total": total,
        "page": page,
        "page_size": page_size,
        "total_pages": max(1, math.ceil(total / page_size)),
        "has_location": lat is not None,
        "results": [_card(g, distance_km=d) for g, d in window],
    }


@router.get("/filters")
def filter_options(db: DbSession):
    """Values the filter sidebar renders - always in sync with real data."""
    active = db.query(Gym).filter(Gym.status == GymStatus.active)
    fee_min, fee_max = db.query(func.min(Gym.monthly_fee), func.max(Gym.monthly_fee)) \
                         .filter(Gym.status == GymStatus.active).first()

    localities = [r[0] for r in db.query(Gym.locality)
                  .filter(Gym.status == GymStatus.active)
                  .group_by(Gym.locality)
                  .order_by(func.count(Gym.id).desc()).limit(40).all() if r[0]]
    districts = [r[0] for r in db.query(Gym.district)
                 .filter(Gym.status == GymStatus.active)
                 .group_by(Gym.district).order_by(Gym.district).all() if r[0]]

    facility_counts: dict[str, int] = {}
    for (fac,) in db.query(Gym.facilities).filter(Gym.status == GymStatus.active).all():
        for f in (fac or []):
            facility_counts[f] = facility_counts.get(f, 0) + 1

    return {
        "fee_range": {"min": fee_min or 0, "max": fee_max or 0},
        "localities": localities,
        "districts": districts,
        "gym_types": [r[0] for r in db.query(Gym.gym_type)
                      .filter(Gym.status == GymStatus.active)
                      .group_by(Gym.gym_type).all() if r[0]],
        "facilities": sorted(facility_counts.items(), key=lambda kv: -kv[1]),
        "total_gyms": active.count(),
        "ac_count": active.filter(Gym.is_air_conditioned.is_(True)).count(),
        "coach_included_count": active.filter(Gym.coach_included.is_(True)).count(),
    }


@router.get("/map/points")
def map_points(db: DbSession):
    """
    Every active gym as a lightweight map pin - deliberately unpaginated
    (there are only a few hundred gyms total) and stripped to just what a
    map marker and its popup need, so this loads fast even on a slow
    connection. Registered before /{gym_code} so "map" is never matched as
    a gym_code path parameter.

    is_real_listing flags the handful of gyms sourced from real OpenStreetMap
    data versus the realistic demo listings that fill out the rest of the
    catalogue - the map marks these differently so nobody mistakes a demo
    pin for a real, physically-visitable gym.
    """
    rows = (db.query(Gym)
            .filter(Gym.status == GymStatus.active,
                    Gym.latitude.isnot(None), Gym.longitude.isnot(None))
            .all())
    return {
        "total": len(rows),
        "real_count": sum(1 for g in rows if g.data_source == "openstreetmap"),
        "points": [{
            "gym_code": g.gym_code,
            "name": g.name,
            "slug": g.slug,
            "latitude": g.latitude,
            "longitude": g.longitude,
            "locality": g.locality,
            "district": g.district,
            "monthly_fee": g.monthly_fee,
            "coach_included": g.coach_included,
            "coach_fee_separate": g.coach_fee_separate,
            "ac_status": "AC" if g.is_air_conditioned else "Non-AC",
            "gym_type": g.gym_type,
            "rating": g.rating,
            "review_count": g.review_count,
            "cover_image": g.cover_image,
            "is_real_listing": g.data_source == "openstreetmap",
        } for g in rows],
    }


@router.get("/{gym_code}")
def gym_detail(gym_code: str, db: DbSession, user: OptionalUser,
               lat: float | None = None, lon: float | None = None):
    """The pin-to-pin detail page."""
    gym = db.query(Gym).filter(Gym.gym_code == gym_code.upper()).first()
    if not gym or gym.status is not GymStatus.active:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Gym not found")

    if lat is None and user and user.latitude:
        lat, lon = user.latitude, user.longitude
    distance = (_haversine_km(lat, lon, gym.latitude, gym.longitude)
                if lat is not None and gym.latitude else None)

    plans = (db.query(GymPlan)
             .filter(GymPlan.gym_id == gym.id, GymPlan.is_active.is_(True))
             .order_by(GymPlan.duration_months).all())
    coaches = (db.query(Coach)
               .filter(Coach.gym_id == gym.id, Coach.is_active.is_(True))
               .order_by(Coach.experience_years.desc()).all())
    equipment = (db.query(Equipment)
                 .filter(Equipment.gym_id == gym.id, Equipment.is_active.is_(True))
                 .order_by(Equipment.category, Equipment.name).all())
    reviews = (db.query(Review, User)
               .join(User, User.id == Review.user_id)
               .filter(Review.gym_id == gym.id, Review.is_hidden.is_(False))
               .order_by(Review.created_at.desc()).limit(20).all())

    by_cat: dict[str, list[dict]] = {}
    for e in equipment:
        by_cat.setdefault(e.category or "Other", []).append({
            "id": e.id, "name": e.name, "quantity": e.quantity,
            "description": e.description, "image_url": e.image_url,
            "condition": e.condition,
        })

    fee_with_coach = gym.monthly_fee + (0 if gym.coach_included else gym.coach_fee_separate)

    return {
        "id": gym.id,
        "gym_code": gym.gym_code,
        "name": gym.name,
        "slug": gym.slug,
        "description": gym.description,
        "tier": gym.tier,
        "gym_type": gym.gym_type,
        "verified": gym.verified,
        "established_year": gym.established_year,

        # Transparency about where this listing came from - see README/PDF
        # "Dataset" section. openstreetmap = a real gym at its real GPS
        # coordinates, pulled from OpenStreetMap's public data. Anything else
        # is a realistic demo listing generated to fill out the catalogue for
        # a region where most small gyms have no public online record at all.
        "data_source": {
            "value": gym.data_source,
            "is_real_listing": gym.data_source == "openstreetmap",
            "label": ("Real gym — verified via OpenStreetMap"
                      if gym.data_source == "openstreetmap"
                      else "Demo listing — generated for this dataset, not a real gym"),
        },

        "media": {"cover_image": gym.cover_image, "gallery": gym.gallery or []},

        "location": {
            "address_line": gym.address_line, "locality": gym.locality,
            "district": gym.district, "state": gym.state, "pincode": gym.pincode,
            "latitude": gym.latitude, "longitude": gym.longitude,
            "google_maps_url": gym.google_maps_url,
            "distance_km": round(distance, 2) if distance is not None else None,
        },

        "contact": {
            "phone": gym.phone, "alt_phone": gym.alt_phone,
            "email": gym.email, "website": gym.website, "instagram": gym.instagram,
        },

        "timings": {
            "morning": f"{gym.morning_open} - {gym.morning_close}",
            "evening": f"{gym.evening_open} - {gym.evening_close}",
            "open_days": gym.open_days, "weekly_off": gym.weekly_off,
            "ladies_timing": gym.ladies_timing,
        },

        # the block the spec singles out as most important
        "pricing": {
            "currency": "INR",
            "monthly_fee": gym.monthly_fee,
            "registration_fee": gym.registration_fee,
            "coach_included": gym.coach_included,
            "coach_fee_separate": gym.coach_fee_separate,
            "membership_without_coach": gym.monthly_fee,
            "membership_with_coach": fee_with_coach,
            "coach_fee_note": (
                "Personal coaching is INCLUDED in the membership fee - no extra charge."
                if gym.coach_included else
                f"Coach fee is SEPARATE: Rs.{gym.coach_fee_separate}/month extra "
                f"on top of the Rs.{gym.monthly_fee} membership."
            ),
            "trial_available": gym.trial_available,
            "trial_days": gym.trial_days,
            "plans": [{
                "id": p.id, "plan_name": p.plan_name,
                "duration_months": p.duration_months, "price": p.price,
                "effective_monthly": p.effective_monthly, "savings": p.savings,
                "coach_included": p.coach_included,
            } for p in plans],
        },

        "amenities": {
            "is_air_conditioned": gym.is_air_conditioned,
            "ac_status": "AC" if gym.is_air_conditioned else "Non-AC",
            "supplements_available": gym.supplements_available,
            "facilities": gym.facilities or [],
        },

        "equipment": {
            "total_items": len(equipment),
            "total_units": sum(e.quantity or 1 for e in equipment),
            "categories": by_cat,
        },

        "coaches": [{
            "id": c.id, "name": c.name, "gender": c.gender,
            "experience_years": c.experience_years,
            "specialisations": c.specialisations or [],
            "certifications": c.certifications or [],
            "bio": c.bio, "photo_url": c.photo_url, "rating": c.rating,
        } for c in coaches],

        "social": {
            "rating": gym.rating,
            "review_count": gym.review_count,
            "member_count": gym.member_count,
            "reviews": [{
                "id": r.id, "rating": r.rating, "title": r.title,
                "comment": r.comment,
                "user_name": u.full_name, "user_photo": u.photo_url,
                "created_at": r.created_at.isoformat(),
            } for r, u in reviews],
        },
    }


@router.get("/compare/side-by-side")
def compare(codes: str = Query(..., description="Comma-separated gym codes, 2-4"),
            db: DbSession = None):
    wanted = [c.strip().upper() for c in codes.split(",") if c.strip()][:4]
    if len(wanted) < 2:
        raise HTTPException(status.HTTP_400_BAD_REQUEST,
                            "Provide at least two gym codes to compare.")

    gyms = db.query(Gym).filter(Gym.gym_code.in_(wanted),
                                Gym.status == GymStatus.active).all()
    if len(gyms) < 2:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Could not find those gyms.")

    order = {c: i for i, c in enumerate(wanted)}
    gyms.sort(key=lambda g: order.get(g.gym_code, 99))

    out = []
    for g in gyms:
        eq_count = db.query(func.count(Equipment.id)).filter(Equipment.gym_id == g.id).scalar()
        coach_count = db.query(func.count(Coach.id)).filter(Coach.gym_id == g.id).scalar()
        top_exp = db.query(func.max(Coach.experience_years)) \
                    .filter(Coach.gym_id == g.id).scalar() or 0
        out.append({
            **_card(g),
            "equipment_count": eq_count,
            "coach_count": coach_count,
            "top_coach_experience": top_exp,
            "all_facilities": g.facilities or [],
            "coach_fee_note": (
                "Included in membership" if g.coach_included
                else f"Rs.{g.coach_fee_separate}/month extra"
            ),
        })

    cheapest = min(out, key=lambda x: x["monthly_fee"])
    best_rated = max(out, key=lambda x: x["rating"])
    most_equipped = max(out, key=lambda x: x["equipment_count"])

    return {
        "gyms": out,
        "highlights": {
            "cheapest": cheapest["gym_code"],
            "best_rated": best_rated["gym_code"],
            "most_equipped": most_equipped["gym_code"],
            "best_value_with_coach": min(out, key=lambda x: x["fee_with_coach"])["gym_code"],
        },
    }
