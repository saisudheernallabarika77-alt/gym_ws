"""
Fitora - Step 2: Fetch REAL towns/villages/suburbs within 100km of Kakinada.
These give us REAL place names + REAL GPS coordinates + REAL pincodes
to anchor the gym dataset geographically.
"""
import json, time, sys
from pathlib import Path
import urllib.request, urllib.parse

KAKINADA_LAT, KAKINADA_LON, RADIUS_M = 16.9891, 82.2475, 100_000
RAW_DIR = Path(__file__).resolve().parents[1] / "raw"
RAW_DIR.mkdir(parents=True, exist_ok=True)

ENDPOINTS = [
    "https://overpass-api.de/api/interpreter",
    "https://overpass.kumi.systems/api/interpreter",
]

QUERY = f"""
[out:json][timeout:180];
(
  node["place"~"^(city|town|suburb|village|neighbourhood)$"](around:{RADIUS_M},{KAKINADA_LAT},{KAKINADA_LON});
);
out tags center;
"""

def fetch(ep, q):
    data = urllib.parse.urlencode({"data": q}).encode()
    req = urllib.request.Request(ep, data=data,
        headers={"User-Agent": "Fitora-Research/1.0 (academic project)"})
    with urllib.request.urlopen(req, timeout=200) as r:
        return json.loads(r.read().decode())

def main():
    res = None
    for ep in ENDPOINTS:
        try:
            print(f"[*] Querying {ep} ...", flush=True)
            res = fetch(ep, QUERY); break
        except Exception as e:
            print(f"[!] {type(e).__name__}: {e}", flush=True); time.sleep(8)
    if not res:
        print("[X] failed", file=sys.stderr); sys.exit(1)

    places = []
    for e in res.get("elements", []):
        t = e.get("tags", {})
        name = t.get("name:en") or t.get("name")
        if not name or not name.isascii():
            name = t.get("name:en")
        if not name:
            continue
        lat, lon = e.get("lat"), e.get("lon")
        if lat is None:
            continue
        places.append({
            "name": name.strip(),
            "place_type": t.get("place"),
            "lat": lat, "lon": lon,
            "district": t.get("addr:district") or t.get("is_in:district"),
            "state": t.get("addr:state") or "Andhra Pradesh",
            "pincode": t.get("addr:postcode"),
            "population": t.get("population"),
        })

    # de-dupe by (name, rounded coords)
    seen, uniq = set(), []
    for p in places:
        k = (p["name"].lower(), round(p["lat"], 3), round(p["lon"], 3))
        if k in seen: continue
        seen.add(k); uniq.append(p)

    out = RAW_DIR / "osm_localities.json"
    out.write_text(json.dumps(uniq, ensure_ascii=False, indent=2))
    print(f"[+] Saved {len(uniq)} localities -> {out}")

    from collections import Counter
    c = Counter(p["place_type"] for p in uniq)
    print("[=] By type:", dict(c))
    print("\n--- Cities & Towns ---")
    for p in sorted([x for x in uniq if x["place_type"] in ("city","town")], key=lambda x: x["name"]):
        print(f"  {p['name']:<28} {p['lat']:.4f},{p['lon']:.4f}  ({p['place_type']})")

if __name__ == "__main__":
    main()
