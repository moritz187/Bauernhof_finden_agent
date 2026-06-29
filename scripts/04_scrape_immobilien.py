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
import pandas as pd
from pathlib import Path
from shapely.geometry import Point, shape

sys.path.insert(0, str(Path(__file__).parent.parent))
sys.path.insert(0, str(Path(__file__).parent))
from scrapers import willhaben, immoscout, landwirt, hofnachfolge
from config import MIN_LIVING_AREA_M2, MIN_PLOT_SIZE_M2

ISOCHRONES_PATH = Path("output/isochrones.geojson")
OUTPUT_CSV = Path("output/immobilien.csv")
MANUAL_CSV = Path("output/manual_check.csv")


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
    print(f"\nGesamt: {len(results)} Einträge von allen Plattformen.")

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

    print(f"\nErgebnis:")
    print(f"  {len(in_zone)} Objekte innerhalb Isochrone -> {OUTPUT_CSV}")
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
