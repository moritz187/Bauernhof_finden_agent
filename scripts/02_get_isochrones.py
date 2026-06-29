"""
Schritt 2: Fahrrad-Isochrone berechnen
Pro Bahnhof aus stations.csv: 25-Min-Fahrrad-Polygon via OpenRouteService API.
Output: output/isochrones.geojson

API-Key kostenlos unter: https://openrouteservice.org/dev/#/signup
-> .env Datei anlegen: ORS_API_KEY=dein_key
"""

import json
import time
import requests
import urllib3
import pandas as pd
from pathlib import Path
from tqdm import tqdm

urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)

INPUT_CSV = Path("output/stations.csv")
OUTPUT_GEOJSON = Path("output/isochrones.geojson")
ENV_FILE = Path(".env")

ORS_URL = "https://api.openrouteservice.org/v2/isochrones/cycling-regular"
BIKE_MINUTES = 25


def load_api_key() -> str:
    if ENV_FILE.exists():
        for line in ENV_FILE.read_text().splitlines():
            if line.startswith("ORS_API_KEY="):
                return line.split("=", 1)[1].strip()
    import os
    key = os.environ.get("ORS_API_KEY", "")
    if not key:
        raise RuntimeError(
            "\n[!] Kein ORS API-Key gefunden.\n"
            "    1. Kostenlos registrieren: https://openrouteservice.org/dev/#/signup\n"
            "    2. .env Datei anlegen mit: ORS_API_KEY=dein_key\n"
        )
    return key


def get_isochrone(lon: float, lat: float, api_key: str) -> dict | None:
    headers = {"Authorization": api_key, "Content-Type": "application/json"}
    body = {
        "locations": [[lon, lat]],
        "range": [BIKE_MINUTES * 60],
        "range_type": "time",
        "profile": "cycling-regular",
    }
    try:
        r = requests.post(ORS_URL, json=body, headers=headers, timeout=15, verify=False)
        if r.status_code == 200:
            return r.json()
        elif r.status_code == 429:
            print("\n  [Rate limit] Warte 60s ...")
            time.sleep(60)
            return get_isochrone(lon, lat, api_key)
        else:
            print(f"\n  [HTTP {r.status_code}] {r.text[:100]}")
            return None
    except Exception as e:
        print(f"\n  [Fehler] {e}")
        return None


def main():
    api_key = load_api_key()
    stations = pd.read_csv(INPUT_CSV)
    print(f"{len(stations)} Bahnhöfe geladen.")

    features = []
    failed = []

    for _, row in tqdm(stations.iterrows(), total=len(stations), desc="Isochrone"):
        result = get_isochrone(row["stop_lon"], row["stop_lat"], api_key)
        if result and "features" in result:
            feature = result["features"][0]
            feature["properties"].update({
                "stop_name": row["stop_name"],
                "min_travel_min": int(row["min_travel_min"]),
                "stop_lat": row["stop_lat"],
                "stop_lon": row["stop_lon"],
            })
            features.append(feature)
        else:
            failed.append(row["stop_name"])
        time.sleep(0.5)  # Rate-Limit schonen (40 req/min im Free-Tier)

    geojson = {"type": "FeatureCollection", "features": features}
    OUTPUT_GEOJSON.parent.mkdir(exist_ok=True)
    OUTPUT_GEOJSON.write_text(json.dumps(geojson, ensure_ascii=False), encoding="utf-8")

    print(f"\nFertig! {len(features)} Isochrone gespeichert -> {OUTPUT_GEOJSON}")
    if failed:
        print(f"Fehlgeschlagen ({len(failed)}): {', '.join(failed[:10])}")


if __name__ == "__main__":
    main()
