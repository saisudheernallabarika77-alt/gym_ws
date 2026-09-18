"""
Fitora - Step 1: Fetch REAL gym data from OpenStreetMap Overpass API
Region: Kakinada, Andhra Pradesh - 100 km radius

Source: OpenStreetMap (ODbL license, free, no API key)
Fetches: name, exact lat/lon, address, phone, website, opening_hours
"""
import json, time, sys, os
from pathlib import Path
import urllib.request
import urllib.error

# Kakinada city center coordinates
KAKINADA_LAT = 16.9891
KAKINADA_LON = 82.2475
RADIUS_M = 100_000  # 100 km

RAW_DIR = Path(__file__).resolve().parents[1] / "raw"
RAW_DIR.mkdir(parents=True, exist_ok=True)

ENDPOINTS = [
    "https://overpass-api.de/api/interpreter",
    "https://overpass.kumi.systems/api/interpreter",
    "https://overpass.osm.ch/api/interpreter",
]

# Gyms tagged multiple ways in OSM
QUERY = f"""
[out:json][timeout:180];
(
  node["leisure"="fitness_centre"](around:{RADIUS_M},{KAKINADA_LAT},{KAKINADA_LON});
  way["leisure"="fitness_centre"](around:{RADIUS_M},{KAKINADA_LAT},{KAKINADA_LON});
  node["amenity"="gym"](around:{RADIUS_M},{KAKINADA_LAT},{KAKINADA_LON});
  way["amenity"="gym"](around:{RADIUS_M},{KAKINADA_LAT},{KAKINADA_LON});
  node["sport"="fitness"](around:{RADIUS_M},{KAKINADA_LAT},{KAKINADA_LON});
  way["sport"="fitness"](around:{RADIUS_M},{KAKINADA_LAT},{KAKINADA_LON});
  node["leisure"="sports_centre"]["sport"~"fitness|gym|multi"](around:{RADIUS_M},{KAKINADA_LAT},{KAKINADA_LON});
  way["leisure"="sports_centre"]["sport"~"fitness|gym|multi"](around:{RADIUS_M},{KAKINADA_LAT},{KAKINADA_LON});
  node["name"~"[Gg]ym|GYM|[Ff]itness|FITNESS"](around:{RADIUS_M},{KAKINADA_LAT},{KAKINADA_LON});
  way["name"~"[Gg]ym|GYM|[Ff]itness|FITNESS"](around:{RADIUS_M},{KAKINADA_LAT},{KAKINADA_LON});
);
out center tags;
"""


def fetch(endpoint, query, attempt=1):
    data = urllib.parse.urlencode({"data": query}).encode()
    req = urllib.request.Request(
        endpoint, data=data,
        headers={"User-Agent": "Fitora-Research/1.0 (academic gym discovery project)"}
    )
    with urllib.request.urlopen(req, timeout=200) as resp:
        return json.loads(resp.read().decode())


def main():
    result = None
    for ep in ENDPOINTS:
        for attempt in range(1, 3):
            try:
                print(f"[*] Querying {ep} (attempt {attempt})...", flush=True)
                result = fetch(ep, QUERY)
                print(f"[+] Success: {len(result.get('elements', []))} raw elements", flush=True)
                break
            except urllib.error.HTTPError as e:
                print(f"[!] HTTP {e.code} from {ep}", flush=True)
                time.sleep(8)
            except Exception as e:
                print(f"[!] {type(e).__name__}: {e}", flush=True)
                time.sleep(8)
        if result:
            break

    if not result:
        print("[X] All Overpass endpoints failed.", file=sys.stderr)
        sys.exit(1)

    out = RAW_DIR / "osm_gyms_raw.json"
    out.write_text(json.dumps(result, ensure_ascii=False, indent=2))
    print(f"[+] Saved raw -> {out}")

    # Quick summary
    els = result.get("elements", [])
    named = [e for e in els if e.get("tags", {}).get("name")]
    print(f"[=] Total elements : {len(els)}")
    print(f"[=] With a name    : {len(named)}")
    print("\n--- Sample (first 15 named) ---")
    for e in named[:15]:
        t = e.get("tags", {})
        lat = e.get("lat") or e.get("center", {}).get("lat")
        lon = e.get("lon") or e.get("center", {}).get("lon")
        print(f"  {t.get('name'):<45} {lat},{lon}  [{t.get('leisure') or t.get('amenity') or t.get('sport')}]")


if __name__ == "__main__":
    import urllib.parse
    main()
