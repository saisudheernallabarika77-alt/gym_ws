"""
Fitora - seed the database from data/processed/gyms.json.

Creates:
  * one admin account
  * a gym-owner account per gym (login: <slug>@fitora-partner.in / partner123)
  * every gym with its plans, coaches and equipment
  * a handful of demo users, memberships, payments and passes so the admin
    and owner dashboards have something real to show

Idempotent: re-running updates existing rows instead of duplicating them.

Usage:  python -m scripts.seed_db [--reset]
"""
from __future__ import annotations
import json
import random
import sys
from datetime import date, datetime, timedelta
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from app.core.config import settings                                  # noqa: E402
from app.core.security import hash_password, generate_code            # noqa: E402
from app.db.models import (                                           # noqa: E402
    Base, Admin, GymOwner, Gym, GymPlan, Coach, Equipment, User,
    Membership, Payment, EntryPass, DietPlan, Review,
    GymStatus, UserStatus, MembershipStatus, PaymentStatus, FitnessGoal,
)
from app.db.session import SessionLocal, engine                       # noqa: E402
from app.services.payment_service import split_amount, new_payment_ref  # noqa: E402
from app.services.pass_service import new_pass_code, build_qr_payload   # noqa: E402
from app.services.diet_service import build_diet_chart                  # noqa: E402

random.seed(20260918)

GOAL_MAP = {
    "weight_loss": FitnessGoal.weight_loss,
    "muscle_gain": FitnessGoal.muscle_gain,
    "strength": FitnessGoal.strength,
    "general_fitness": FitnessGoal.general_fitness,
    "endurance": FitnessGoal.endurance,
    "rehabilitation": FitnessGoal.rehabilitation,
}

DEMO_FIRST = ["Praveen", "Anusha", "Kiran", "Sravani", "Vamsi", "Divya", "Naveen",
              "Keerthi", "Satish", "Harika", "Rahul", "Meghana", "Teja", "Swathi",
              "Ajay", "Padma", "Chaitanya", "Lavanya", "Bhaskar", "Sirisha"]
DEMO_LAST = ["Kumar", "Reddy", "Naidu", "Rao", "Varma", "Chowdary", "Prasad",
             "Babu", "Murthy", "Raju"]

REVIEW_TEXTS = [
    ("Great equipment", "All machines are well maintained and rarely crowded."),
    ("Good trainers", "The coaches actually correct your form instead of ignoring you."),
    ("Value for money", "Fee is reasonable for what you get. No hidden charges."),
    ("Clean and airy", "Place is kept clean, washrooms are decent."),
    ("Crowded in evening", "Good gym but 7-9 PM gets very crowded."),
    ("Helpful staff", "Staff is friendly and the timings are flexible."),
    ("Needs more cardio machines", "Only two treadmills, always a wait."),
    ("Best in the area", "Been coming here for a year, no complaints."),
]


def _mk_owner_email(slug: str, i: int) -> str:
    base = "".join(c for c in slug if c.isalnum() or c == "-")[:28].strip("-")
    return f"{base or 'gym'}{i}@fitora-partner.in"


def seed(reset: bool = False) -> None:
    if settings.ENV == "production":
        raise SystemExit(
            "Refusing to run seed_db against ENV=production: it creates "
            "publicly-known demo credentials (admin@fitora.in/admin123, "
            "every gym owner on partner123, 40 demo users on user123). "
            "If you genuinely need seed data in production, do it from a "
            "copy of this script with those passwords replaced and the "
            "accounts deleted immediately after."
        )
    if reset:
        print("[*] dropping all tables ...")
        Base.metadata.drop_all(bind=engine)
    Base.metadata.create_all(bind=engine)

    gyms_path = Path(settings.GYMS_JSON)
    gyms_data = json.loads(gyms_path.read_text())
    print(f"[*] loaded {len(gyms_data)} gyms from {gyms_path.name}")

    db = SessionLocal()
    try:
        # ---------------------------------------------------------- admin
        admin = db.query(Admin).filter(Admin.email == "admin@fitora.in").first()
        if not admin:
            admin = Admin(
                full_name="Fitora Administrator",
                email="admin@fitora.in",
                password_hash=hash_password("admin123"),
                role="superadmin",
            )
            db.add(admin)
            db.commit()
        print(f"[+] admin ready: admin@fitora.in / admin123")

        # ------------------------------------------------- owners + gyms
        created_gyms, created_owners = 0, 0
        gym_rows: list[Gym] = []

        for i, g in enumerate(gyms_data, 1):
            loc, pr, tm, ct = g["location"], g["pricing"], g["timings"], g["contact"]

            owner_email = _mk_owner_email(g["slug"], i)
            owner = db.query(GymOwner).filter(GymOwner.email == owner_email).first()
            if not owner:
                owner = GymOwner(
                    full_name=f"{g['name']} Owner",
                    email=owner_email,
                    phone=ct["phone"],
                    password_hash=hash_password("partner123"),
                    business_name=g["name"],
                    bank_account_name=g["name"],
                    bank_account_number=str(random.randint(10**10, 10**11 - 1)),
                    bank_ifsc=f"SBIN000{random.randint(1000, 9999)}",
                    upi_id=f"{g['slug'][:18]}@ybl",
                    email_verified=True,
                    status=UserStatus.active,
                )
                db.add(owner)
                db.flush()
                created_owners += 1

            gym = db.query(Gym).filter(Gym.gym_code == g["gym_id"]).first()
            if not gym:
                gym = Gym(gym_code=g["gym_id"])
                db.add(gym)
                created_gyms += 1

            gym.owner_id = owner.id
            gym.name = g["name"]
            gym.slug = g["slug"]
            gym.description = g["description"]
            gym.tier = g["tier"]
            gym.gym_type = g["gym_type"]
            gym.address_line = loc["address_line"]
            gym.locality = loc["locality"]
            gym.district = loc["district"]
            gym.state = loc["state"]
            gym.pincode = str(loc["pincode"])
            gym.latitude = loc["latitude"]
            gym.longitude = loc["longitude"]
            gym.google_maps_url = loc["google_maps_url"]
            gym.phone = ct["phone"]
            gym.alt_phone = ct.get("alt_phone")
            gym.email = ct["email"]
            gym.website = ct.get("website")
            gym.instagram = ct.get("instagram")
            gym.morning_open = tm["morning_open"]
            gym.morning_close = tm["morning_close"]
            gym.evening_open = tm["evening_open"]
            gym.evening_close = tm["evening_close"]
            gym.open_days = tm["open_days"]
            gym.weekly_off = tm.get("weekly_off")
            gym.ladies_timing = tm.get("ladies_timing")
            gym.monthly_fee = pr["monthly_fee"]
            gym.registration_fee = pr["registration_fee"]
            gym.coach_included = pr["coach_included"]
            gym.coach_fee_separate = pr["coach_fee_separate"]
            gym.trial_available = pr.get("trial_available", False)
            gym.trial_days = pr.get("trial_days", 0)
            gym.is_air_conditioned = g["is_air_conditioned"]
            gym.supplements_available = g["supplements_available"]
            gym.facilities = g["facilities"]
            gym.cover_image = g["cover_image"]
            gym.gallery = g["gallery"]
            gym.rating = g["rating"]
            gym.review_count = g["review_count"]
            gym.member_count = g["member_count"]
            gym.established_year = g["established_year"]
            gym.status = GymStatus.active
            gym.verified = g["verified"]
            gym.data_source = g["data_source"]
            gym.indexed_in_rag = True
            db.flush()
            gym_rows.append(gym)

            # plans / coaches / equipment - rebuild cleanly
            db.query(GymPlan).filter(GymPlan.gym_id == gym.id).delete()
            for p in pr["plans"]:
                db.add(GymPlan(
                    gym_id=gym.id, plan_name=p["plan_name"],
                    duration_months=p["duration_months"], price=p["price"],
                    effective_monthly=p["effective_monthly"], savings=p["savings"],
                    coach_included=p["coach_included"],
                ))

            db.query(Coach).filter(Coach.gym_id == gym.id).delete()
            for c in g["coaches"]:
                db.add(Coach(
                    gym_id=gym.id, name=c["name"], gender=c["gender"],
                    experience_years=c["experience_years"],
                    specialisations=c["specialisations"],
                    certifications=c["certifications"],
                    bio=c["bio"], photo_url=c["photo_url"], rating=c["rating"],
                ))

            db.query(Equipment).filter(Equipment.gym_id == gym.id).delete()
            for e in g["equipment"]:
                db.add(Equipment(
                    gym_id=gym.id, name=e["name"], category=e["category"],
                    quantity=e["quantity"], description=e["description"],
                    image_url=e["image_url"], condition=e["condition"],
                ))

            if i % 50 == 0:
                db.commit()
                print(f"    ... {i}/{len(gyms_data)} gyms")

        db.commit()
        print(f"[+] gyms: {created_gyms} created, {len(gyms_data) - created_gyms} updated")
        print(f"[+] gym owners: {created_owners} created")

        # -------------------------------------------------- demo members
        if db.query(User).count() < 30:
            print("[*] creating demo users, memberships, payments and passes ...")
            today = date.today()

            for n in range(1, 41):
                first = random.choice(DEMO_FIRST)
                last = random.choice(DEMO_LAST)
                email = f"{first.lower()}.{last.lower()}{n}@example.com"
                if db.query(User).filter(User.email == email).first():
                    continue

                goal_key = random.choice(list(GOAL_MAP))
                weight = round(random.uniform(48, 98), 1)
                height = round(random.uniform(150, 186), 1)
                gender = "Female" if first in ("Anusha","Sravani","Divya","Keerthi","Harika",
                                               "Meghana","Swathi","Padma","Lavanya","Sirisha") else "Male"
                gym = random.choice(gym_rows)

                user = User(
                    full_name=f"{first} {last}",
                    email=email,
                    phone=f"+91 9{random.randint(100000000, 999999999)}",
                    password_hash=hash_password("user123"),
                    address=f"{random.choice(['Main Road','Bazaar Street','Gandhi Nagar'])}, {gym.locality}",
                    locality=gym.locality, district=gym.district,
                    state="Andhra Pradesh", pincode=gym.pincode,
                    latitude=gym.latitude + random.uniform(-0.02, 0.02),
                    longitude=gym.longitude + random.uniform(-0.02, 0.02),
                    date_of_birth=date(random.randint(1985, 2006),
                                       random.randint(1, 12), random.randint(1, 28)),
                    gender=gender, height_cm=height, weight_kg=weight,
                    fitness_goal=GOAL_MAP[goal_key],
                    emergency_contact_name=f"{random.choice(DEMO_FIRST)} {last}",
                    emergency_contact_phone=f"+91 9{random.randint(100000000, 999999999)}",
                    photo_url=f"/members/member-{random.randint(1, 30)}.jpg",
                    status=UserStatus.active, email_verified=True,
                )
                db.add(user)
                db.flush()

                plan = (db.query(GymPlan)
                        .filter(GymPlan.gym_id == gym.id)
                        .order_by(GymPlan.duration_months).first())
                if not plan:
                    continue

                with_coach = gym.coach_included or random.random() < 0.4
                coach_fee = 0 if gym.coach_included else (gym.coach_fee_separate if with_coach else 0)
                base_fee = plan.price
                reg_fee = gym.registration_fee
                total = base_fee + coach_fee + reg_fee

                # spread joins over the last 5 months so dues states vary
                start = today - timedelta(days=random.randint(5, 150))
                end = start + timedelta(days=30 * plan.duration_months)
                next_due = end

                if next_due < today - timedelta(days=12):
                    status = MembershipStatus.overdue
                elif next_due < today:
                    status = MembershipStatus.due
                else:
                    status = MembershipStatus.active

                coach = (db.query(Coach).filter(Coach.gym_id == gym.id)
                         .order_by(Coach.experience_years.desc()).first()) if with_coach else None

                ms = Membership(
                    membership_code=generate_code("FTM", 9),
                    user_id=user.id, gym_id=gym.id, plan_id=plan.id,
                    goal=GOAL_MAP[goal_key], weight_kg=weight, height_cm=height,
                    target_weight_kg=round(weight + (-6 if goal_key == "weight_loss" else 5), 1),
                    with_coach=with_coach,
                    assigned_coach_id=coach.id if coach else None,
                    base_fee=base_fee, coach_fee=coach_fee, registration_fee=reg_fee,
                    total_amount=total, duration_months=plan.duration_months,
                    start_date=start, end_date=end, next_due_date=next_due,
                    grace_days=settings.DEFAULT_GRACE_DAYS,
                    status=status,
                )
                db.add(ms)
                db.flush()

                sp = split_amount(total, gym.commission_percent)
                db.add(Payment(
                    payment_ref=new_payment_ref(),
                    user_id=user.id, membership_id=ms.id, gym_id=gym.id,
                    amount=total,
                    platform_commission=sp["platform_commission"],
                    gym_share=sp["gym_share"],
                    method="UPI", upi_id=f"{first.lower()}@ybl",
                    gateway="mock",
                    gateway_txn_id=f"MOCKTXN{random.randint(10**9, 10**10)}",
                    status=PaymentStatus.success,
                    completed_at=datetime.combine(start, datetime.min.time()),
                ))

                pass_code = new_pass_code()
                payload = build_qr_payload(
                    pass_code=pass_code, membership_code=ms.membership_code,
                    user_id=user.id, user_name=user.full_name,
                    gym_code=gym.gym_code, gym_name=gym.name,
                    goal=goal_key, plan_name=plan.plan_name,
                    with_coach=with_coach, valid_from=start, valid_until=end,
                )
                db.add(EntryPass(
                    pass_code=pass_code, membership_id=ms.id,
                    qr_payload=payload, photo_url=user.photo_url,
                    valid_from=start, valid_until=end,
                    is_active=status is not MembershipStatus.removed,
                    scan_count=random.randint(0, 60),
                ))

                age = today.year - user.date_of_birth.year
                dc = build_diet_chart(weight, height, age, gender, goal_key,
                                      target_weight_kg=ms.target_weight_kg)
                db.add(DietPlan(
                    membership_id=ms.id, goal=GOAL_MAP[goal_key],
                    bmr=dc["bmr"], tdee=dc["tdee"],
                    target_calories=dc["target_calories"],
                    protein_g=dc["protein_g"], carbs_g=dc["carbs_g"],
                    fats_g=dc["fats_g"], water_litres=dc["water_litres"],
                    chart=dc["chart"],
                    notes=f"{dc['goal_label']} plan. BMI {dc['bmi']} ({dc['bmi_band']}).",
                ))

                if random.random() < 0.55:
                    title, comment = random.choice(REVIEW_TEXTS)
                    exists = (db.query(Review)
                              .filter(Review.user_id == user.id, Review.gym_id == gym.id)
                              .first())
                    if not exists:
                        db.add(Review(
                            user_id=user.id, gym_id=gym.id,
                            rating=random.choices([5, 4, 3, 2], weights=[45, 35, 15, 5])[0],
                            title=title, comment=comment,
                            created_at=datetime.combine(
                                start + timedelta(days=random.randint(10, 40)),
                                datetime.min.time()),
                        ))

            db.commit()

        # ------------------------------------------------------- summary
        print("\n" + "=" * 58)
        print("  SEED COMPLETE")
        print("=" * 58)
        print(f"  Admins       : {db.query(Admin).count()}")
        print(f"  Gym owners   : {db.query(GymOwner).count()}")
        print(f"  Gyms         : {db.query(Gym).count()}")
        print(f"  Plans        : {db.query(GymPlan).count()}")
        print(f"  Coaches      : {db.query(Coach).count()}")
        print(f"  Equipment    : {db.query(Equipment).count()}")
        print(f"  Users        : {db.query(User).count()}")
        print(f"  Memberships  : {db.query(Membership).count()}")
        print(f"     active    : {db.query(Membership).filter(Membership.status == MembershipStatus.active).count()}")
        print(f"     due       : {db.query(Membership).filter(Membership.status == MembershipStatus.due).count()}")
        print(f"     overdue   : {db.query(Membership).filter(Membership.status == MembershipStatus.overdue).count()}")
        print(f"  Payments     : {db.query(Payment).count()}")
        print(f"  Entry passes : {db.query(EntryPass).count()}")
        print(f"  Diet plans   : {db.query(DietPlan).count()}")
        print(f"  Reviews      : {db.query(Review).count()}")
        print("=" * 58)
        print("  LOGINS")
        print("    admin  : admin@fitora.in / admin123")
        sample_owner = db.query(GymOwner).first()
        if sample_owner:
            print(f"    partner: {sample_owner.email} / partner123")
        sample_user = db.query(User).first()
        if sample_user:
            print(f"    user   : {sample_user.email} / user123")
        print("=" * 58)
    finally:
        db.close()


if __name__ == "__main__":
    seed(reset="--reset" in sys.argv)
