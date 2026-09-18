"""
Fitora - end-to-end smoke test across all three portals.

Exercises the real flows a user, a gym owner and the admin go through:
signup -> OTP -> login -> chat -> gym detail -> join -> pay -> entry pass ->
diet chart -> QR scan, plus the owner dashboard and the admin dues/payout path.

Usage:  python -m scripts.e2e_test [--api http://127.0.0.1:8000]
"""
from __future__ import annotations
import json
import re
import sys
import time
import urllib.error
import urllib.request
from pathlib import Path

API = "http://127.0.0.1:8000"
LOG_PATH = None
PASSED, FAILED = [], []


# ------------------------------------------------------------------- http
def call(method: str, path: str, body: dict | None = None,
         token: str | None = None) -> tuple[int, dict]:
    url = f"{API}/api/v1{path}"
    headers = {"Content-Type": "application/json"}
    if token:
        headers["Authorization"] = f"Bearer {token}"
    data = json.dumps(body).encode() if body is not None else None
    req = urllib.request.Request(url, data=data, headers=headers, method=method)
    try:
        with urllib.request.urlopen(req, timeout=120) as r:
            return r.status, json.loads(r.read().decode() or "{}")
    except urllib.error.HTTPError as e:
        raw = e.read().decode()
        try:
            return e.code, json.loads(raw)
        except Exception:
            return e.code, {"detail": raw[:300]}


def check(name: str, ok: bool, detail: str = "") -> bool:
    (PASSED if ok else FAILED).append(name)
    print(f"  {'PASS' if ok else 'FAIL'}  {name}" + (f"  -  {detail}" if detail else ""))
    return ok


def section(title: str) -> None:
    print(f"\n{'=' * 68}\n  {title}\n{'=' * 68}")


def find_otp(email: str) -> str | None:
    """Read the OTP the dev-mode mailer printed to the server log."""
    if not LOG_PATH or not Path(LOG_PATH).exists():
        return None
    text = Path(LOG_PATH).read_text(errors="ignore")
    blocks = text.split("FITORA OTP")
    for block in reversed(blocks[1:]):
        if email in block:
            m = re.search(r"CODE:\s*(\d{4,8})", block)
            if m:
                return m.group(1)
    return None


# -------------------------------------------------------------------- main
def main() -> int:
    global API, LOG_PATH
    for i, a in enumerate(sys.argv):
        if a == "--api" and i + 1 < len(sys.argv):
            API = sys.argv[i + 1]
        if a == "--log" and i + 1 < len(sys.argv):
            LOG_PATH = sys.argv[i + 1]

    stamp = int(time.time())
    email = f"e2e.{stamp}@example.com"
    # Phone must be unique too - the API enforces one account per number.
    phone = f"9{stamp % 1000000000:09d}"
    password = "testpass123"

    # ================================================== USER PORTAL
    section("USER PORTAL")

    st, r = call("POST", "/auth/signup", {
        "full_name": "E2E Test User", "email": email, "phone": phone,
        "address": "Main Road, Kakinada", "locality": "Kakinada",
        "district": "Kakinada", "pincode": "533001",
        "latitude": 16.9891, "longitude": 82.2475,
        "password": password, "confirm_password": password,
    })
    check("signup creates pending account", st == 201, r.get("message", "")[:70])

    otp = find_otp(email)
    if not check("OTP issued and readable", bool(otp), f"code={otp}"):
        print("\n  Cannot continue without the OTP. Pass --log <server log path>.")
        return 1

    st, r = call("POST", "/auth/verify-otp", {"email": email, "code": otp})
    check("OTP verification activates account", st == 200 and r.get("success"))

    st, r = call("POST", "/auth/verify-otp", {"email": email, "code": "000000"})
    check("used OTP cannot be replayed", st == 200 and "Already verified" in r.get("message", ""))

    st, r = call("POST", "/auth/login", {"email": email, "password": "wrongpass"})
    check("wrong password is rejected", st == 401)

    st, r = call("POST", "/auth/login", {"email": email, "password": password})
    token = r.get("access_token", "")
    check("login returns a token", st == 200 and bool(token))
    check("login returns the profile", bool(r.get("profile", {}).get("email") == email))

    st, me = call("GET", "/auth/me", token=token)
    check("profile carries the signup coordinates",
          me.get("latitude") == 16.9891, f"{me.get('latitude')},{me.get('longitude')}")

    # ---- chatbot ----
    section("RAG CHATBOT")

    st, c = call("POST", "/chat",
                 {"message": "AC gym below 1500 near me with personal trainer",
                  "top_k": 3}, token=token)
    check("chat responds", st == 200 and bool(c.get("answer")))
    check("query constraints are parsed",
          "Under Rs.1500/month" in c["interpretation"]["understood"]
          and "AC gym" in c["interpretation"]["understood"],
          str(c["interpretation"]["understood"]))
    check("chat returns gym cards", len(c.get("gyms", [])) > 0,
          f"{len(c.get('gyms', []))} cards")
    check("saved location is used for distance",
          c.get("used_location") is True
          and c["gyms"][0].get("distance_km") is not None,
          f"nearest {c['gyms'][0].get('distance_km')} km")

    over_budget = [g for g in c["gyms"] if g["monthly_fee"] > 1500]
    check("budget ceiling is respected", not over_budget,
          f"{len(over_budget)} over budget")
    non_ac = [g for g in c["gyms"] if g["ac_status"] != "AC"]
    check("AC filter is respected", not non_ac, f"{len(non_ac)} non-AC")

    st, c2 = call("POST", "/chat", {"message": "1000 lopu cheap gym kavali",
                                    "top_k": 3}, token=token)
    check("Telugu-English query is parsed",
          st == 200 and all(g["monthly_fee"] <= 1000 for g in c2.get("gyms", [])),
          str(c2["interpretation"]["understood"]))

    gym_code = c["gyms"][0]["gym_code"]

    # ---- gym detail ----
    section("GYM DETAIL")

    st, g = call("GET", f"/gyms/{gym_code}", token=token)
    check("gym detail loads", st == 200 and g.get("name"))
    check("contact details present", bool(g["contact"]["phone"]))
    check("location has coordinates and maps link",
          bool(g["location"]["latitude"] and g["location"]["google_maps_url"]))
    check("coach fee is stated explicitly",
          "INCLUDED" in g["pricing"]["coach_fee_note"]
          or "SEPARATE" in g["pricing"]["coach_fee_note"],
          g["pricing"]["coach_fee_note"][:60])
    check("plans are listed", len(g["pricing"]["plans"]) >= 4,
          f"{len(g['pricing']['plans'])} plans")
    check("equipment inventory present", g["equipment"]["total_items"] > 0,
          f"{g['equipment']['total_items']} items")
    check("coaches have experience listed",
          len(g["coaches"]) > 0 and g["coaches"][0]["experience_years"] >= 0,
          f"{len(g['coaches'])} coaches, top {g['coaches'][0]['experience_years']} yrs")

    st, cmp_ = call("GET", f"/gyms/compare/side-by-side?codes={gym_code},"
                           f"{c['gyms'][1]['gym_code']}", token=token)
    check("side-by-side comparison works",
          st == 200 and len(cmp_.get("gyms", [])) == 2
          and "cheapest" in cmp_.get("highlights", {}))

    # ---- join ----
    section("JOIN + PAYMENT + ENTRY PASS")

    st, pre = call("GET", f"/join/{gym_code}/prefill", token=token)
    check("join form pre-fills from the profile",
          st == 200 and pre["prefill"]["full_name"] == "E2E Test User")
    check("plans and goals offered on the form",
          len(pre["plans"]) > 0 and len(pre["goals"]) > 0)

    plan_id = pre["plans"][0]["id"]
    st, join = call("POST", f"/join/{gym_code}", {
        "plan_id": plan_id, "with_coach": True,
        "weight_kg": 78.5, "height_cm": 175.0, "target_weight_kg": 72.0,
        "goal": "weight_loss", "activity_level": "moderate",
        "medical_notes": "None",
        "emergency_contact_name": "Test Contact",
        "emergency_contact_phone": "9876500000",
    }, token=token)
    check("membership created", st == 201 and join.get("membership_code"))
    check("fee breakdown returned",
          "total" in join.get("breakdown", {}),
          f"total Rs.{join['breakdown']['total']}")
    check("UPI order with a scannable QR",
          bool(join["payment"].get("upi_uri"))
          and join["payment"].get("qr_data_uri", "").startswith("data:image/png"))

    membership_code = join["membership_code"]
    pay_ref = join["payment"]["ref"]

    # Re-submitting the join form before paying is a retry, not an error:
    # it must supersede the unpaid attempt cleanly, never 500.
    st, dup = call("POST", f"/join/{gym_code}", {
        "plan_id": plan_id, "with_coach": False,
        "weight_kg": 78.5, "height_cm": 175.0, "goal": "weight_loss",
    }, token=token)
    check("unpaid join can be retried without error", st == 201, f"HTTP {st}")
    if st == 201:
        membership_code = dup["membership_code"]
        pay_ref = dup["payment"]["ref"]

    st, bad = call("POST", f"/pay/{pay_ref}", {"upi_id": "not-a-upi-id"}, token=token)
    check("invalid UPI id is rejected", st == 402, bad.get("detail", "")[:50])

    st, paid = call("POST", f"/pay/{pay_ref}", {"upi_id": "e2etest@ybl"}, token=token)
    check("payment succeeds", st == 200 and paid.get("success"),
          f"txn {paid.get('gateway_txn_id')}")
    check("pass issued on payment", bool(paid.get("pass_code")))

    st, again = call("POST", f"/pay/{pay_ref}", {"upi_id": "e2etest@ybl"}, token=token)
    check("payment cannot be replayed", again and st == 409)

    st, ep = call("GET", f"/pass/{membership_code}", token=token)
    check("entry pass loads", st == 200 and ep.get("pass_code"))
    check("pass carries a QR image",
          ep.get("qr_data_uri", "").startswith("data:image/png"))
    check("pass shows member, gym and goal",
          bool(ep["member"]["name"] and ep["gym"]["name"] and ep["member"]["goal"]),
          f"{ep['member']['name']} @ {ep['gym']['name']} ({ep['member']['goal']})")
    check("pass states validity",
          ep["membership"]["days_remaining"] > 0,
          f"{ep['membership']['days_remaining']} days left")

    st, diet = call("GET", f"/diet/{membership_code}", token=token)
    check("diet chart generated", st == 200 and diet.get("targets"))
    check("calorie target suits weight loss",
          diet["targets"]["calories"] < diet["targets"]["tdee"],
          f"{diet['targets']['calories']} kcal vs TDEE {diet['targets']['tdee']}")
    check("macros and meal slots present",
          diet["targets"]["protein_g"] > 0 and len(diet["chart"]) >= 5,
          f"{diet['targets']['protein_g']}g protein, {len(diet['chart'])} meals")

    # ---- gate scan ----
    section("ENTRY PASS SCAN (gym gate)")

    st, mine = call("GET", "/my/memberships", token=token)
    check("membership list loads", st == 200 and mine["total"] >= 1)

    qr_payload = None
    from app.db.models import EntryPass, Membership
    from app.db.session import SessionLocal
    db = SessionLocal()
    try:
        m = (db.query(Membership)
             .filter(Membership.membership_code == membership_code).first())
        if m:
            row = db.query(EntryPass).filter(EntryPass.membership_id == m.id).first()
            qr_payload = row.qr_payload if row else None
    finally:
        db.close()

    if qr_payload:
        st, scan = call("POST", "/scan", {"qr_payload": qr_payload})
        check("valid pass scans OK", st == 200 and scan.get("valid"),
              scan.get("message", "")[:60])
        st, bad_scan = call("POST", "/scan", {"qr_payload": qr_payload[:-4] + "0000"})
        check("tampered QR is rejected",
              st == 200 and not bad_scan.get("valid"),
              bad_scan.get("reason"))
    else:
        check("QR payload retrievable", False)

    # ================================================== OWNER PORTAL
    section("GYM OWNER PORTAL")

    from app.db.models import Gym, GymOwner
    db = SessionLocal()
    try:
        gym_row = db.query(Gym).filter(Gym.gym_code == gym_code).first()
        owner_row = db.get(GymOwner, gym_row.owner_id) if gym_row else None
        owner_email = owner_row.email if owner_row else None
    finally:
        db.close()

    owner_token = ""
    if owner_email:
        st, r = call("POST", "/auth/owner/login",
                     {"email": owner_email, "password": "partner123"})
        owner_token = r.get("access_token", "")
        check("gym owner can log in", st == 200 and bool(owner_token), owner_email)

    if owner_token:
        st, d = call("GET", "/owner/dashboard", token=owner_token)
        check("owner dashboard loads", st == 200 and d.get("gym"))
        check("owner sees member and money stats",
              "total_members" in d["stats"] and "lifetime_share" in d["earnings"],
              f"{d['stats']['total_members']} members, "
              f"Rs.{d['earnings']['lifetime_share']} lifetime share")
        check("new member appears for the owner",
              any(m["membership_code"] == membership_code
                  for m in d.get("recent_members", [])))

        st, dues = call("GET", "/owner/dues", token=owner_token)
        check("owner dues list loads", st == 200)
        check("owner cannot remove members",
              dues["permissions"]["can_remove_member"] is False
              and dues["permissions"]["can_view"] is True)

        st, eq = call("GET", "/owner/equipment", token=owner_token)
        check("owner equipment inventory loads",
              st == 200 and eq["total_items"] > 0, f"{eq['total_items']} items")

        st, add = call("POST", "/owner/equipment", {
            "name": "E2E Test Treadmill", "category": "Cardio", "quantity": 2,
            "description": "Added by the e2e test",
            "image_url": "/equipment/test.jpg", "condition": "New",
        }, token=owner_token)
        check("owner can add equipment", st == 201 and add.get("success"))
        if add.get("equipment_id"):
            st, _ = call("DELETE", f"/owner/equipment/{add['equipment_id']}",
                         token=owner_token)
            check("owner can remove equipment", st == 200)

        st, earn = call("GET", "/owner/earnings", token=owner_token)
        check("owner earnings show the platform split",
              st == 200 and "awaiting_payout" in earn["totals"],
              f"Rs.{earn['totals']['awaiting_payout']} awaiting payout")

        st, forbidden = call("GET", "/admin/dashboard", token=owner_token)
        check("owner cannot reach the admin portal", forbidden and st == 403)

    # ================================================== ADMIN PORTAL
    section("ADMIN PORTAL")

    st, r = call("POST", "/auth/admin/login",
                 {"email": "admin@fitora.in", "password": "admin123"})
    admin_token = r.get("access_token", "")
    check("admin can log in", st == 200 and bool(admin_token))

    if admin_token:
        st, d = call("GET", "/admin/dashboard", token=admin_token)
        check("admin dashboard loads", st == 200 and d.get("counts"))
        check("admin sees platform-wide money",
              d["money"]["total_collected"] > 0
              and d["money"]["platform_commission"] > 0,
              f"Rs.{d['money']['total_collected']} collected, "
              f"Rs.{d['money']['platform_commission']} commission")
        check("admin sees overdue members",
              d["counts"]["overdue_memberships"] >= 0,
              f"{d['counts']['overdue_memberships']} overdue")

        st, dues = call("GET", "/admin/dues", token=admin_token)
        check("admin dues list spans all gyms", st == 200 and dues["total"] > 0,
              f"{dues['total']} dues, Rs.{dues['total_pending_amount']} pending")
        check("admin may act on dues",
              dues["permissions"]["can_remove_member"] is True
              and dues["permissions"]["can_extend_grace"] is True)

        if dues["dues"]:
            target = dues["dues"][0]
            st, ext = call("POST",
                           f"/admin/dues/{target['membership_id']}/extend-grace",
                           {"extra_days": 7, "reason": "e2e test"},
                           token=admin_token)
            check("admin can extend a grace period", st == 200 and ext.get("success"),
                  f"grace now {ext.get('grace_days')} days")

        st, users = call("GET", "/admin/users?page_size=5", token=admin_token)
        check("admin can list users", st == 200 and users["total"] > 0,
              f"{users['total']} users")

        e2e_user_id = None
        st, found = call("GET", f"/admin/users?q={email}", token=admin_token)
        if found.get("users"):
            e2e_user_id = found["users"][0]["id"]

        if e2e_user_id:
            st, b = call("POST", f"/admin/users/{e2e_user_id}/block",
                         {"reason": "e2e test block"}, token=admin_token)
            check("admin can block a user", st == 200 and b.get("success"))

            st, blocked = call("GET", "/auth/me", token=token)
            check("blocked user loses API access", st == 403,
                  str(blocked.get("detail", ""))[:50])

            st, _ = call("POST", f"/admin/users/{e2e_user_id}/unblock",
                         token=admin_token)
            check("admin can unblock a user", st == 200)

            st, ok = call("GET", "/auth/me", token=token)
            check("unblocked user regains access", st == 200)

        st, pend = call("GET", "/admin/payouts/pending", token=admin_token)
        check("admin sees pending gym payouts", st == 200,
              f"{pend['totals']['gym_count']} gyms, "
              f"Rs.{pend['totals']['net_payable']} payable")

        if pend.get("gyms"):
            target_gym = pend["gyms"][0]
            now = time.gmtime()
            st, po = call("POST", "/admin/payouts", {
                "gym_id": target_gym["gym_id"],
                "period_month": now.tm_mon, "period_year": now.tm_year,
            }, token=admin_token)
            check("admin can create a payout", st == 201 and po.get("success"),
                  f"{po.get('payout_ref')} net Rs.{po.get('net_payable')}")

            st, lst = call("GET", "/admin/payouts", token=admin_token)
            payout_id = next((p["id"] for p in lst.get("payouts", [])
                              if p["payout_ref"] == po.get("payout_ref")), None)
            if payout_id:
                st, rel = call("POST", f"/admin/payouts/{payout_id}/release",
                               {"notes": "e2e test release"}, token=admin_token)
                check("admin can release a payout to the gym",
                      st == 200 and rel.get("status") == "paid",
                      f"ref {rel.get('transfer_ref')}")

        st, gadd = call("POST", "/admin/gyms", {
            "name": "E2E Village Fitness Centre",
            "description": "Added manually by admin for a village with no partner yet",
            "gym_type": "Unisex",
            "address_line": "Main Road, Test Village",
            "locality": "Yeleswaram", "district": "Kakinada",
            "pincode": "533429", "latitude": 17.2873, "longitude": 82.1052,
            "phone": "+91 9000000001",
            "monthly_fee": 900, "registration_fee": 200,
            "coach_included": False, "coach_fee_separate": 700,
            "is_air_conditioned": False, "supplements_available": False,
            "facilities": ["Changing Room", "Drinking Water / RO", "Parking"],
            "publish": True,
        }, token=admin_token)
        check("admin can add a gym manually",
              st == 201 and gadd.get("success"), gadd.get("gym_code"))
        check("admin-added gym enters the RAG index",
              gadd.get("indexed_in_rag") is True)

        if gadd.get("gym_code"):
            time.sleep(1)
            st, find = call("POST", "/chat",
                            {"message": "gym in Yeleswaram under 1000", "top_k": 5})
            found_new = any(g["gym_code"] == gadd["gym_code"]
                            for g in find.get("gyms", []))
            check("admin-added gym is discoverable in chat", found_new,
                  f"{len(find.get('gyms', []))} results")

        st, rag = call("GET", "/admin/rag/status", token=admin_token)
        check("RAG index is in sync with the database",
              st == 200 and rag.get("in_sync") is True,
              f"{rag.get('indexed_gyms')} indexed vs "
              f"{rag.get('active_gyms_in_db')} active")

        st, sweep = call("POST", "/admin/dues/run-sweep?send_warnings=false",
                         token=admin_token)
        check("dues sweep runs", st == 200 and sweep.get("success"),
              f"checked {sweep.get('checked')}, "
              f"due {sweep.get('marked_due')}, overdue {sweep.get('marked_overdue')}")

        st, logs = call("GET", "/admin/audit-logs?page_size=5", token=admin_token)
        check("admin actions are audit-logged", st == 200 and logs["total"] > 0,
              f"{logs['total']} entries")

    # ================================================== ACCESS CONTROL
    section("ACCESS CONTROL")

    st, r = call("GET", "/admin/dashboard", token=token)
    check("user cannot reach the admin portal", st == 403)
    st, r = call("GET", "/owner/dashboard", token=token)
    check("user cannot reach the owner portal", st == 403)
    st, r = call("GET", "/auth/me")
    check("unauthenticated request is rejected", st == 401)
    st, r = call("GET", "/auth/me", token="garbage.token.value")
    check("invalid token is rejected", st == 401)

    # ================================================== SUMMARY
    section("SUMMARY")
    total = len(PASSED) + len(FAILED)
    print(f"  passed : {len(PASSED)}/{total}")
    if FAILED:
        print(f"  failed : {len(FAILED)}")
        for f in FAILED:
            print(f"     - {f}")
    print()
    return 1 if FAILED else 0


if __name__ == "__main__":
    sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
    sys.exit(main())
