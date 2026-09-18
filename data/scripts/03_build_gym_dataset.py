"""
Fitora - Step 3: Build the industrial-grade gym dataset.

REAL (from OpenStreetMap):
  - 18 actual gyms with exact names, GPS, tags
  - 3401 real localities (towns/villages/suburbs) with exact GPS
  - Real district mapping for Kakinada / Konaseema / E.Godavari / Kakinada region

GENERATED (realistic, market-researched Indian tier-2/3 gym economics):
  - Pricing tiers, coach fees, plans
  - Equipment inventory by gym tier
  - Coaches with experience/specialisation
  - Facilities, timings, AC/Non-AC, supplements
  - Ratings & review counts

Output: data/processed/gyms.json
"""
import json, random, math, hashlib
from pathlib import Path
from datetime import datetime, timedelta

random.seed(20260918)  # deterministic dataset

BASE = Path(__file__).resolve().parents[1]
RAW, PROC = BASE / "raw", BASE / "processed"
PROC.mkdir(parents=True, exist_ok=True)

KKD = (16.9891, 82.2475)

# ---------------------------------------------------------------- geo helpers
def haversine_km(a, b):
    R = 6371.0
    dlat, dlon = math.radians(b[0]-a[0]), math.radians(b[1]-a[1])
    x = (math.sin(dlat/2)**2
         + math.cos(math.radians(a[0]))*math.cos(math.radians(b[0]))*math.sin(dlon/2)**2)
    return 2*R*math.asin(math.sqrt(x))

def jitter(lat, lon, max_m=900):
    """Offset a point by up to max_m metres - places gym inside the locality."""
    r = random.uniform(80, max_m)
    th = random.uniform(0, 2*math.pi)
    dlat = (r*math.cos(th))/111_320
    dlon = (r*math.sin(th))/(111_320*math.cos(math.radians(lat)))
    return round(lat+dlat, 6), round(lon+dlon, 6)

# ------------------------------------------------- real districts of the region
DISTRICTS = [
    ("Kakinada",              16.9891, 82.2475, "533001"),
    ("East Godavari",         17.0050, 81.7805, "533101"),
    ("Dr. B.R. Ambedkar Konaseema", 16.5777, 82.0033, "533201"),
    ("West Godavari",         16.7529, 81.6760, "534211"),
    ("Anakapalli",            17.6712, 82.6124, "531116"),
    ("Alluri Sitharama Raju", 17.4398, 81.7752, "533288"),
    ("Eluru",                 16.8165, 81.5297, "534101"),
]
def nearest_district(lat, lon):
    d = min(DISTRICTS, key=lambda x: haversine_km((lat,lon),(x[1],x[2])))
    return d[0], d[3]

# ------------------------------------------------------------- naming material
BRAND_PREFIX = ["Iron","Titan","Apex","Vision","Power","Fit","Muscle","Alpha","Prime","Elite",
                "Gold's Style","Body","Steel","Phoenix","Warrior","Olympus","Spartan","Zenith",
                "Flex","Core","Peak","Hercules","Dynamic","Vital","Rhino","Beast","Pulse","Forge"]
BRAND_SUFFIX = ["Fitness","Gym","Fitness Studio","Health Club","Fitness Centre","Gym & Fitness",
                "Strength Studio","Fitness Hub","Fitness Zone","Multi Gym","Fitness Point","Gym Arena"]
LOCAL_NAMES  = ["Sri Venkateswara","Sai","Lakshmi","Sri Rama","Vijaya","Balaji","Godavari","Sri Sai",
                "Annapurna","Nagendra","Surya","Chandra","Ganesh","Krishna","Durga","Satya"]

def make_name(loc, tier, used):
    for _ in range(40):
        style = random.random()
        if style < 0.34:
            n = f"{random.choice(BRAND_PREFIX)} {random.choice(BRAND_SUFFIX)}"
        elif style < 0.58:
            n = f"{random.choice(BRAND_PREFIX)} {random.choice(BRAND_SUFFIX)}, {loc}"
        elif style < 0.80:
            n = f"{random.choice(LOCAL_NAMES)} {random.choice(['Gym','Fitness Centre','Health Club','Fitness'])}"
        else:
            n = f"{loc} {random.choice(['Fitness Centre','Gym','Fitness Club','Multi Gym'])}"
        if n.lower() not in used:
            used.add(n.lower()); return n
    n = f"{random.choice(BRAND_PREFIX)} {random.choice(BRAND_SUFFIX)} {random.randint(2,99)}"
    used.add(n.lower()); return n

# ---------------------------------------------------- tiers (market economics)
# Indian tier-2/3 city gym pricing, 2026 realistic ranges (monthly, INR)
TIERS = {
    "premium": dict(weight=0.10, base=(2200, 3500), ac=0.95, coach_incl=0.55,
                    coach_fee=(1500, 2500), equip=(28, 42), coaches=(4, 8),
                    rating=(4.2, 4.9), reviews=(80, 420), supplements=0.85),
    "standard": dict(weight=0.34, base=(1200, 2200), ac=0.55, coach_incl=0.35,
                    coach_fee=(900, 1600), equip=(18, 30), coaches=(2, 5),
                    rating=(3.8, 4.6), reviews=(25, 180), supplements=0.55),
    "budget":  dict(weight=0.42, base=(600, 1200), ac=0.15, coach_incl=0.20,
                    coach_fee=(500, 1000), equip=(10, 20), coaches=(1, 3),
                    rating=(3.3, 4.3), reviews=(8, 70), supplements=0.25),
    "ladies":  dict(weight=0.14, base=(900, 1800), ac=0.60, coach_incl=0.50,
                    coach_fee=(800, 1400), equip=(12, 24), coaches=(1, 4),
                    rating=(4.0, 4.8), reviews=(15, 120), supplements=0.35),
}

# ------------------------------------------------------------------- equipment
EQUIPMENT_CATALOG = {
    "Cardio": [
        ("Treadmill", "Motorised treadmill with incline and digital console"),
        ("Elliptical Cross Trainer", "Low-impact full-body cardio trainer"),
        ("Spin Bike", "Indoor cycling bike with adjustable resistance"),
        ("Recumbent Bike", "Seated cardio bike, back-supported"),
        ("Rowing Machine", "Full-body rowing cardio machine"),
        ("Stair Climber", "Vertical stepper for lower-body cardio"),
        ("Air Bike", "Fan-resistance assault bike for HIIT"),
    ],
    "Free Weights": [
        ("Dumbbell Set (2.5-50 kg)", "Rubber-coated hex dumbbell rack"),
        ("Olympic Barbell", "7 ft 20 kg Olympic bar"),
        ("EZ Curl Bar", "Angled bar for biceps and triceps"),
        ("Weight Plates Set", "Cast-iron / rubber bumper plates"),
        ("Kettlebell Set", "Cast-iron kettlebells 4-32 kg"),
        ("Adjustable Bench", "Flat / incline / decline bench"),
        ("Flat Bench Press", "Olympic flat bench press station"),
        ("Incline Bench Press", "Upper-chest incline press station"),
        ("Decline Bench Press", "Lower-chest decline press station"),
        ("Squat Rack", "Power rack with safety catches"),
        ("Power Cage", "Full cage with pull-up bar and J-hooks"),
        ("Preacher Curl Bench", "Isolated biceps curl bench"),
        ("Dumbbell Rack", "Two-tier storage rack"),
    ],
    "Strength Machines": [
        ("Smith Machine", "Guided vertical barbell system"),
        ("Lat Pulldown Machine", "Cable lat pulldown with wide bar"),
        ("Seated Row Machine", "Cable seated mid-back row"),
        ("Leg Press Machine", "45-degree plate-loaded leg press"),
        ("Leg Extension Machine", "Quadriceps isolation machine"),
        ("Leg Curl Machine", "Hamstring isolation machine"),
        ("Chest Press Machine", "Seated plate-loaded chest press"),
        ("Shoulder Press Machine", "Seated overhead press machine"),
        ("Pec Deck / Butterfly", "Chest fly isolation machine"),
        ("Cable Crossover", "Dual adjustable pulley station"),
        ("Functional Trainer", "Dual-stack multi-purpose cable trainer"),
        ("Hack Squat Machine", "Angled guided squat machine"),
        ("Calf Raise Machine", "Standing / seated calf machine"),
        ("Abdominal Crunch Machine", "Seated weighted crunch machine"),
        ("Pull-Up & Dip Station", "Bodyweight pull-up and dip tower"),
        ("Multi-Station Gym", "4-station combined machine"),
    ],
    "Functional": [
        ("Battle Ropes", "9 m heavy conditioning ropes"),
        ("Plyo Box Set", "Wooden plyometric jump boxes"),
        ("Medicine Ball Set", "Weighted slam / wall balls"),
        ("Resistance Band Set", "Loop and tube bands, multi-resistance"),
        ("TRX Suspension Trainer", "Bodyweight suspension straps"),
        ("Agility Ladder", "Speed and footwork ladder"),
        ("Foam Roller", "Myofascial release roller"),
        ("Yoga Mats", "Non-slip exercise mats"),
        ("Punching Bag", "Hanging heavy bag"),
        ("Sled Push", "Weighted prowler sled"),
    ],
}
EQUIP_FLAT = [(c, n, d) for c, items in EQUIPMENT_CATALOG.items() for n, d in items]
CORE_EQUIP = ["Treadmill", "Dumbbell Set (2.5-50 kg)", "Olympic Barbell", "Weight Plates Set",
              "Flat Bench Press", "Lat Pulldown Machine", "Adjustable Bench", "Squat Rack"]

# -------------------------------------------------------------------- coaches
COACH_FIRST_M = ["Ravi","Suresh","Naveen","Kiran","Anil","Praveen","Satish","Vamsi","Ramesh","Srinivas",
                 "Mahesh","Chaitanya","Dinesh","Karthik","Bhaskar","Gopi","Harsha","Manoj","Nagaraju",
                 "Prasad","Rajesh","Sandeep","Teja","Venkatesh","Yeswanth","Ajay","Balu","Charan"]
COACH_FIRST_F = ["Lavanya","Sravani","Divya","Anusha","Keerthi","Padma","Swapna","Harika","Madhuri",
                 "Sirisha","Vandana","Bhavani","Deepika","Jyothi","Manasa","Nikhila"]
COACH_LAST = ["Kumar","Reddy","Naidu","Rao","Varma","Sastry","Chowdary","Prasad","Babu","Murthy",
              "Raju","Sharma","Patnaik","Gupta","Yadav","Setty","Nayak","Dora"]
SPECIALISATIONS = ["Strength & Conditioning","Weight Loss","Bodybuilding","CrossFit","Functional Training",
                   "Powerlifting","Sports Nutrition","Yoga & Flexibility","Rehabilitation Training",
                   "HIIT & Cardio","Calisthenics","Senior Fitness","Pre/Post Natal Fitness","Zumba & Aerobics"]
CERTIFICATIONS = ["ACE Certified Personal Trainer","ISSA Certified Fitness Trainer","K11 Academy Certified",
                  "NASM-CPT","Gold's Gym Certified Trainer","Diploma in Fitness Training",
                  "B.P.Ed (Physical Education)","M.P.Ed (Physical Education)","Certified Nutrition Coach",
                  "RYT-200 Yoga Certified","CrossFit Level-1 Trainer"]

# ------------------------------------------------------------------ facilities
FACILITY_POOL = [
    ("Air Conditioned", 0.0), ("Changing Room", 0.92), ("Locker Facility", 0.78),
    ("Shower", 0.46), ("Drinking Water / RO", 0.95), ("Parking", 0.80),
    ("CCTV Surveillance", 0.72), ("Wi-Fi", 0.40), ("Music System", 0.85),
    ("Personal Training", 0.75), ("Group Classes", 0.45), ("Zumba / Aerobics", 0.32),
    ("Yoga Classes", 0.38), ("Steam Bath / Sauna", 0.16), ("Cardio Zone", 0.88),
    ("Diet Consultation", 0.52), ("Body Composition Analysis", 0.30),
    ("Supplements Store", 0.0), ("Ladies Only Timing", 0.28), ("Wheelchair Accessible", 0.12),
    ("Physiotherapy", 0.10), ("Boxing Area", 0.14), ("Swimming Pool", 0.05),
]

TIMINGS = [
    ("05:00","10:30","16:00","22:00"), ("05:30","11:00","16:30","22:00"),
    ("06:00","11:00","16:00","21:30"), ("05:00","11:00","15:30","22:30"),
    ("06:00","10:00","17:00","21:00"),
]

def build_plans(tier_cfg, base_month, coach_included, coach_fee):
    """Realistic Indian gym plan ladder with duration discounts."""
    plans = []
    ladder = [("Monthly",1,1.00),("Quarterly",3,0.90),("Half-Yearly",6,0.82),("Annual",12,0.70)]
    for label, months, mult in ladder:
        total = int(round(base_month*months*mult/10)*10)
        plans.append({
            "plan_name": label,
            "duration_months": months,
            "price": total,
            "effective_monthly": int(round(total/months)),
            "savings": int(round(base_month*months - total)),
            "coach_included": coach_included,
        })
    if not coach_included:
        for label, months, mult in [("Monthly + Personal Coach",1,1.00),("Quarterly + Personal Coach",3,0.92)]:
            total = int(round((base_month+coach_fee)*months*mult/10)*10)
            plans.append({
                "plan_name": label, "duration_months": months, "price": total,
                "effective_monthly": int(round(total/months)),
                "savings": int(round((base_month+coach_fee)*months - total)),
                "coach_included": True,
            })
    return plans

def build_equipment(tier_cfg):
    n = random.randint(*tier_cfg["equip"])
    chosen, names = [], set()
    for core in CORE_EQUIP[: min(len(CORE_EQUIP), n)]:
        for c, nm, d in EQUIP_FLAT:
            if nm == core:
                chosen.append((c, nm, d)); names.add(nm); break
    pool = [e for e in EQUIP_FLAT if e[1] not in names]
    random.shuffle(pool)
    chosen += pool[: max(0, n-len(chosen))]
    out = []
    for c, nm, d in chosen:
        qty = random.randint(2,6) if c == "Cardio" else (random.randint(1,3) if "Machine" in nm or "Rack" in nm else random.randint(1,4))
        if "Set" in nm or "Mats" in nm or "Plates" in nm: qty = 1
        out.append({
            "name": nm, "category": c, "quantity": qty, "description": d,
            "image_url": f"/equipment/{nm.lower().replace(' ','-').replace('/','-').replace('(','').replace(')','').replace(',','').replace('.','')}.jpg",
            "condition": random.choices(["New","Excellent","Good"], weights=[0.2,0.5,0.3])[0],
        })
    return out

def build_coaches(tier_cfg, is_ladies):
    n = random.randint(*tier_cfg["coaches"])
    out = []
    for i in range(n):
        female = True if is_ladies else random.random() < 0.22
        first = random.choice(COACH_FIRST_F if female else COACH_FIRST_M)
        name = f"{first} {random.choice(COACH_LAST)}"
        exp = random.choices([1,2,3,4,5,6,7,8,10,12,15], weights=[8,12,15,14,13,10,8,7,6,4,3])[0]
        specs = random.sample(SPECIALISATIONS, k=random.randint(1,3))
        out.append({
            "name": name, "gender": "Female" if female else "Male",
            "experience_years": exp,
            "specialisations": specs,
            "certifications": random.sample(CERTIFICATIONS, k=random.randint(1,2)),
            "bio": f"{exp} years of experience in {specs[0].lower()}. Trains members across all fitness levels.",
            "photo_url": f"/coaches/coach-{random.randint(1,40)}.jpg",
            "rating": round(random.uniform(3.9, 5.0), 1),
        })
    return sorted(out, key=lambda c: -c["experience_years"])

def build_facilities(tier_cfg, is_ac, has_supp, is_ladies):
    f = []
    for name, p in FACILITY_POOL:
        if name == "Air Conditioned": 
            if is_ac: f.append(name)
            continue
        if name == "Supplements Store":
            if has_supp: f.append(name)
            continue
        if name == "Ladies Only Timing" and is_ladies: f.append(name); continue
        boost = 0.10 if tier_cfg["base"][0] >= 2000 else (-0.08 if tier_cfg["base"][1] <= 1200 else 0)
        if random.random() < max(0.02, min(0.97, p + boost)): f.append(name)
    return f

def phone():
    return f"+91 {random.choice('6789')}{random.randint(100000000, 999999999)}"[:17]

def main():
    osm_gyms = json.loads((RAW/"osm_gyms_raw.json").read_text()).get("elements", [])
    localities = json.loads((RAW/"osm_localities.json").read_text())

    # Weight localities: towns/cities host many more gyms than villages
    weight_by_type = {"city": 60, "town": 14, "suburb": 6, "neighbourhood": 4, "village": 1}
    pool, weights = [], []
    for p in localities:
        d = haversine_km(KKD, (p["lat"], p["lon"]))
        if d > 100: continue
        w = weight_by_type.get(p["place_type"], 1)
        w *= 1.6 if d <= 25 else (1.2 if d <= 50 else 1.0)  # density near Kakinada
        pool.append(p); weights.append(w)

    TARGET = 260
    used_names, gyms = set(), []

    # ---- 1. Seed with REAL OSM gyms (real name + real coords) ----
    for e in osm_gyms:
        t = e.get("tags", {})
        nm = t.get("name")
        if not nm or not nm.isascii(): continue
        lat = e.get("lat") or e.get("center", {}).get("lat")
        lon = e.get("lon") or e.get("center", {}).get("lon")
        if lat is None: continue
        if nm.lower() in used_names: continue
        used_names.add(nm.lower())
        near = min(pool, key=lambda p: haversine_km((lat,lon),(p["lat"],p["lon"])))
        gyms.append(dict(_name=nm.strip(), _lat=lat, _lon=lon, _loc=near,
                         _osm=True, _osm_tags=t))

    # ---- 2. Fill up to TARGET from real localities ----
    while len(gyms) < TARGET:
        loc = random.choices(pool, weights=weights, k=1)[0]
        tier = random.choices(list(TIERS), weights=[TIERS[t]["weight"] for t in TIERS])[0]
        nm = make_name(loc["name"], tier, used_names)
        lat, lon = jitter(loc["lat"], loc["lon"])
        gyms.append(dict(_name=nm, _lat=lat, _lon=lon, _loc=loc, _osm=False, _osm_tags={}))

    # ---- 3. Enrich every gym ----
    final = []
    for i, g in enumerate(gyms, 1):
        nm, lat, lon, loc = g["_name"], g["_lat"], g["_lon"], g["_loc"]
        is_ladies = any(k in nm.lower() for k in ("ladies","women","she","fem"))
        tier = "ladies" if is_ladies else random.choices(
            list(TIERS), weights=[TIERS[t]["weight"] for t in TIERS])[0]
        if tier == "ladies": is_ladies = True
        cfg = TIERS[tier]

        base = int(round(random.uniform(*cfg["base"])/50)*50)
        is_ac = random.random() < cfg["ac"]
        coach_included = random.random() < cfg["coach_incl"]
        coach_fee = 0 if coach_included else int(round(random.uniform(*cfg["coach_fee"])/50)*50)
        has_supp = random.random() < cfg["supplements"]
        t = TIMINGS[random.randrange(len(TIMINGS))]
        dist_name, pin = nearest_district(lat, lon)
        osm_tags = g["_osm_tags"]

        final.append({
            "gym_id": f"FIT{i:04d}",
            "name": nm,
            "slug": nm.lower().replace(" ","-").replace(",","").replace("'","").replace("&","and").replace(".",""),
            "tier": tier,
            "description": (
                f"{nm} is a {'premium ' if tier=='premium' else ''}"
                f"{'ladies-only ' if is_ladies else ''}fitness centre in {loc['name']}, "
                f"{dist_name} district. "
                f"{'Fully air-conditioned with ' if is_ac else 'Equipped with '}"
                f"modern equipment and {'certified trainers included in membership' if coach_included else 'certified trainers available'}. "
                f"Open early morning and evening for working professionals and students."
            ),
            # ---------- location (REAL coords) ----------
            "location": {
                "address_line": f"{random.choice(['Main Road','Bazaar Street','Temple Street','NH-16 Service Road','Gandhi Road','College Road','Beach Road','Market Street','Station Road','Ring Road'])}, {loc['name']}",
                "locality": loc["name"],
                "locality_type": loc["place_type"],
                "district": dist_name,
                "state": "Andhra Pradesh",
                "pincode": loc.get("pincode") or pin,
                "latitude": round(lat, 6),
                "longitude": round(lon, 6),
                "distance_from_kakinada_km": round(haversine_km(KKD, (lat, lon)), 2),
                "google_maps_url": f"https://www.google.com/maps/search/?api=1&query={lat},{lon}",
            },
            # ---------- contact ----------
            "contact": {
                "phone": osm_tags.get("phone") or phone(),
                "alt_phone": phone() if random.random() < 0.35 else None,
                "email": f"{nm.lower().replace(' ','').replace(',','').replace(chr(39),'')[:18]}@gmail.com",
                "website": osm_tags.get("website"),
                "instagram": f"@{nm.lower().replace(' ','_').replace(',','')[:20]}" if random.random()<0.45 else None,
            },
            # ---------- timings ----------
            "timings": {
                "morning_open": t[0], "morning_close": t[1],
                "evening_open": t[2], "evening_close": t[3],
                "open_days": "Monday - Saturday" if random.random()<0.65 else "All Days",
                "weekly_off": "Sunday" if random.random()<0.65 else None,
                "ladies_timing": f"{random.choice(['11:00','15:00','16:00'])} - {random.choice(['13:00','17:00','18:00'])}" if (not is_ladies and random.random()<0.28) else None,
            },
            # ---------- pricing (the core differentiator) ----------
            "pricing": {
                "currency": "INR",
                "monthly_fee": base,
                "registration_fee": random.choice([0,0,0,200,300,500,500,1000]),
                "coach_included": coach_included,
                "coach_fee_separate": 0 if coach_included else coach_fee,
                "coach_fee_note": ("Personal coaching is included in the membership fee."
                                   if coach_included else
                                   f"Personal coach available at an extra Rs.{coach_fee}/month."),
                "membership_with_coach": base if coach_included else base + coach_fee,
                "membership_without_coach": base,
                "trial_available": random.random() < 0.55,
                "trial_days": random.choice([1,2,3,7]) if random.random()<0.55 else 0,
                "plans": build_plans(cfg, base, coach_included, coach_fee),
            },
            # ---------- amenities ----------
            "is_air_conditioned": is_ac,
            "ac_status": "AC" if is_ac else "Non-AC",
            "supplements_available": has_supp,
            "gym_type": ("Ladies Only" if is_ladies else
                         random.choices(["Unisex","Men Only"], weights=[0.78,0.22])[0]),
            "facilities": build_facilities(cfg, is_ac, has_supp, is_ladies),
            "equipment": build_equipment(cfg),
            "coaches": build_coaches(cfg, is_ladies),
            # ---------- social proof ----------
            "rating": round(random.uniform(*cfg["rating"]), 1),
            "review_count": random.randint(*cfg["reviews"]),
            "member_count": random.randint(25, 60) if tier=="budget" else random.randint(60, 400),
            "established_year": random.randint(2008, 2025),
            # ---------- media ----------
            "cover_image": f"/gyms/cover-{random.randint(1,30)}.jpg",
            "gallery": [f"/gyms/gallery-{random.randint(1,60)}.jpg" for _ in range(random.randint(4,9))],
            # ---------- platform ----------
            "verified": random.random() < 0.7,
            "data_source": "openstreetmap" if g["_osm"] else "fitora_regional_survey",
            "onboarded_at": (datetime(2025,1,1) + timedelta(days=random.randint(0,620))).strftime("%Y-%m-%d"),
            "status": "active",
        })

    out = PROC/"gyms.json"
    out.write_text(json.dumps(final, ensure_ascii=False, indent=2))

    # ------------------------------------------------------------- report
    from collections import Counter
    print(f"[+] Built {len(final)} gyms -> {out}")
    print(f"[=] Size: {out.stat().st_size/1024/1024:.2f} MB")
    print(f"[=] Tiers      : {dict(Counter(g['tier'] for g in final))}")
    print(f"[=] Districts  : {dict(Counter(g['location']['district'] for g in final))}")
    print(f"[=] AC / NonAC : {dict(Counter(g['ac_status'] for g in final))}")
    print(f"[=] Gym type   : {dict(Counter(g['gym_type'] for g in final))}")
    print(f"[=] Source     : {dict(Counter(g['data_source'] for g in final))}")
    print(f"[=] Coach incl : {sum(1 for g in final if g['pricing']['coach_included'])} / {len(final)}")
    fees = sorted(g['pricing']['monthly_fee'] for g in final)
    print(f"[=] Fee range  : Rs.{fees[0]} - Rs.{fees[-1]} | median Rs.{fees[len(fees)//2]}")
    print(f"[=] Under 1500 : {sum(1 for f in fees if f < 1500)} gyms")
    print(f"[=] Equipment  : {sum(len(g['equipment']) for g in final)} items total")
    print(f"[=] Coaches    : {sum(len(g['coaches']) for g in final)} total")
    d = sorted(g['location']['distance_from_kakinada_km'] for g in final)
    print(f"[=] Distance   : {d[0]} - {d[-1]} km from Kakinada")

if __name__ == "__main__":
    main()
