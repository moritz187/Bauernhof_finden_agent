"""
Schritt 4: Immobilien-Scraper Orchestrator

Führt alle Scraper aus, filtert Ergebnisse auf unsere Isochrone-Flächen
und speichert die Treffer als CSV.

Suchkriterien (aus config.py):
  Typ:         Bauernhof, Landhaus, Schloss, Weingut, Reiterhof, ...
  Wohnfläche:  ab 200 m²
  Grundstück:  ab 2.500 m²
  Parteien:    2-5 (Pärchen Anfang 30, Kinderwunsch)
  Budget:      offen
  Zustand:     schlüsselfertig bis Vollrenovierung

Filterlogik:
  1. Größenfilter: Wohnfläche >= MIN_LIVING_AREA_M2 (wenn Daten vorhanden)
  2. Grundstücksfilter: Grundstück >= MIN_PLOT_SIZE_M2 (wenn Daten vorhanden)
  3. Geo-Filter: Point-in-Polygon gegen Isochrone-Flächen (25-Min-Rad-Zone)

  Objekte ohne Koordinaten -> manual_check.csv (manuell prüfen)
  Objekte ohne Größenangaben behalten wir — lieber zu viel als zu wenig

Output:
  output/immobilien.csv       — Treffer innerhalb Isochrone
  output/manual_check.csv     — Treffer ohne Koordinaten zur manuellen Prüfung
"""

import json
import sys
import time as _time
import requests
import pandas as pd
from pathlib import Path
from shapely.geometry import Point, shape
import urllib3
urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)

sys.path.insert(0, str(Path(__file__).parent.parent))
sys.path.insert(0, str(Path(__file__).parent))
from scrapers import willhaben, immoscout, landwirt, hofnachfolge, raiffeisen, immmo, immowelt, sreal, immo_trend, my_landimmo, schlossseiten, muhr
from config import MIN_LIVING_AREA_M2, MIN_PLOT_SIZE_M2

ISOCHRONES_PATH = Path("output/isochrones.geojson")
OUTPUT_CSV = Path("output/immobilien.csv")
MANUAL_CSV = Path("output/manual_check.csv")

FOREIGN_KEYWORDS = ["ungarn", "kroatien", "italien", "slowakei", "tschechien", "deutschland", "schweiz", "slowenien", "frankreich"]
STREET_KEYWORDS = ["straße", "gasse", "weg", "allee", "platz", "ring", "zeile", "str."]
_geocode_cache: dict = {}

def _nominatim_geocode(address: str):
    """Nominatim geocoding mit Cache."""
    if address in _geocode_cache:
        return _geocode_cache[address]
    try:
        r = requests.get("https://nominatim.openstreetmap.org/search",
            params={"q": address + ", Österreich", "format": "json", "limit": 1},
            headers={"User-Agent": "BauernhofFinder/1.0 moritz95meyer@gmail.com"},
            timeout=10, verify=False)
        d = r.json()
        if d:
            result = float(d[0]["lat"]), float(d[0]["lon"])
            _geocode_cache[address] = result
            _time.sleep(1.1)
            return result
    except Exception:
        pass
    _geocode_cache[address] = (None, None)
    return None, None


def _to_float(val) -> float | None:
    """Konvertiert Strings wie '1.200 m²' oder '1200' zu float, gibt None bei Fehler."""
    if val is None:
        return None
    try:
        return float(str(val).replace(".", "").replace(",", ".").replace("m²", "").strip())
    except ValueError:
        return None


def load_isochrone_shapes():
    """Lädt alle Isochrone-Polygone als Shapely-Objekte."""
    data = json.loads(ISOCHRONES_PATH.read_text(encoding="utf-8"))
    shapes = []
    for feature in data["features"]:
        props = feature["properties"]
        shapes.append({
            "polygon": shape(feature["geometry"]),
            "stop_name": props.get("stop_name", ""),
            "min_travel_min": props.get("min_travel_min", 0),
        })
    return shapes


def find_matching_station(lat: float, lon: float, iso_shapes: list) -> dict | None:
    """Gibt den nächsten Bahnhof zurück wenn der Punkt in einer Isochrone liegt."""
    point = Point(lon, lat)
    for iso in iso_shapes:
        if iso["polygon"].contains(point):
            return iso
    return None


def run_all_scrapers() -> list[dict]:
    """Alle Scraper sequentiell ausführen."""
    all_results = []
    scraper_modules = [
        ("willhaben.at", willhaben),
        ("immoscout24.at", immoscout),
        ("landwirt.com", landwirt),
        ("hofnachfolge.at", hofnachfolge),
        ("raiffeisen-immobilien.at", raiffeisen),
        ("immmo.at", immmo),
        ("immowelt.at", immowelt),
        ("sreal.at", sreal),
        ("immo.trend.at", immo_trend),
        ("my-landimmo.de", my_landimmo),
        ("schlossseiten.at", schlossseiten),
        ("muhr-immobilien.com", muhr),
    ]
    for name, module in scraper_modules:
        print(f"\n[{name}] starte Scraper ...")
        try:
            results = module.scrape()
            all_results.extend(results)
            print(f"[{name}] {len(results)} Einträge gefunden.")
        except Exception as e:
            print(f"[{name}] Fehler: {e}")
    return all_results


def main():
    print("Lade Isochrone-Flächen ...")
    iso_shapes = load_isochrone_shapes()
    print(f"{len(iso_shapes)} Isochrone-Polygone geladen.\n")

    results = run_all_scrapers()
    print(f"\nGesamt (roh): {len(results)} Einträge von allen Plattformen.")

    # Duplikaten-Filter: gleiche URL über Plattformen hinweg (Aggregatoren zeigen oft auf selbe Inserate)
    seen_urls: set[str] = set()
    deduped = []
    for r in results:
        url = r.get("url", "")
        if url and url in seen_urls:
            continue
        if url:
            seen_urls.add(url)
        deduped.append(r)
    print(f"Duplikaten-Filter: {len(results) - len(deduped)} entfernt -> {len(deduped)} verbleiben")
    results = deduped

    # Grundstücks-Filter: reine Baugrundstücke ohne Gebäude ausschließen
    GRUNDSTUECK_KEYWORDS = ["baugrundstück", "baugrund", "waldgrundstück", "agrarfläche", "weingartenparzelle"]
    before_gs = len(results)
    results = [
        r for r in results
        if not any(kw in (r.get("name") or "").lower() for kw in GRUNDSTUECK_KEYWORDS)
        or (r.get("size_m2") and _to_float(r.get("size_m2", 0)) > 0)
    ]
    print(f"Grundstücks-Filter: {before_gs - len(results)} reine Grundstücke entfernt")

    # Größenfilter (nur wenn Daten vorhanden — lieber behalten als verlieren)
    before = len(results)
    size_filtered = []
    for r in results:
        living = _to_float(r.get("size_m2"))
        plot = _to_float(r.get("plot_size_m2"))
        # Ablehnen nur wenn Wert vorhanden UND unter Minimum
        if living is not None and living < MIN_LIVING_AREA_M2:
            continue
        if plot is not None and plot < MIN_PLOT_SIZE_M2:
            continue
        size_filtered.append(r)
    print(f"\nGrößenfilter: {before - len(size_filtered)} verworfen "
          f"(< {MIN_LIVING_AREA_M2}m² Wohnfl. oder < {MIN_PLOT_SIZE_M2}m² Grund)")

    # Geo-Filter: Isochrone Point-in-Polygon
    in_zone = []
    no_coords = []
    outside = 0

    for r in size_filtered:
        if r.get("lat") and r.get("lon"):
            match = find_matching_station(r["lat"], r["lon"], iso_shapes)
            if match:
                r["nearest_station"] = match["stop_name"]
                r["station_travel_min"] = match["min_travel_min"]
                in_zone.append(r)
            else:
                outside += 1
        else:
            no_coords.append(r)

    # location_approximate: True wenn nur PLZ/Ort, keine Straße
    for r in in_zone:
        loc = (r.get("location") or "").lower()
        r.setdefault("location_approximate", not any(k in loc for k in STREET_KEYWORDS))

    # Retry geocoding für österreichische manual_check-Einträge mit Location-Text
    retry_candidates = [
        r for r in no_coords
        if r.get("location") and str(r["location"]).strip()
        and not any(kw in str(r["location"]).lower() for kw in FOREIGN_KEYWORDS)
    ]
    remaining_no_coords = [r for r in no_coords if r not in retry_candidates]
    retry_added = 0
    if retry_candidates:
        print(f"\nRetry geocoding: {len(retry_candidates)} österreichische Einträge ohne Koordinaten ...")
        for r in retry_candidates:
            lat, lon = _nominatim_geocode(str(r["location"]))
            if lat and lon:
                r["lat"] = lat
                r["lon"] = lon
                r["location_approximate"] = True
                match = find_matching_station(lat, lon, iso_shapes)
                if match:
                    r["nearest_station"] = match["stop_name"]
                    r["station_travel_min"] = match["min_travel_min"]
                    in_zone.append(r)
                    retry_added += 1
                else:
                    remaining_no_coords.append(r)
            else:
                remaining_no_coords.append(r)
        no_coords = remaining_no_coords
        print(f"  -> {retry_added} neue Objekte mit '?' Standort in Zone gefunden")

    print(f"\nErgebnis:")
    print(f"  {len(in_zone)} Objekte innerhalb Isochrone (davon {retry_added} mit ? Standort) -> {OUTPUT_CSV}")
    print(f"  {len(no_coords)} Objekte ohne Koordinaten -> {MANUAL_CSV}")
    print(f"  {outside} Objekte außerhalb Isochrone (verworfen)")

    OUTPUT_CSV.parent.mkdir(exist_ok=True)
    if in_zone:
        pd.DataFrame(in_zone).to_csv(OUTPUT_CSV, index=False)
    if no_coords:
        pd.DataFrame(no_coords).to_csv(MANUAL_CSV, index=False)

    print(f"\nFertig! Nächster Schritt: python scripts/05_update_map.py")


if __name__ == "__main__":
    main()
