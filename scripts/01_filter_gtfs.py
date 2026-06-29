"""
Schritt 1: GTFS-Feed auswerten
Findet alle Bahnhöfe mit Direktzug von Wien, Fahrzeit <= 90 Minuten.
Output: output/stations.csv
"""

import zipfile
import warnings
import pandas as pd
import requests
import urllib3
from pathlib import Path
from tqdm import tqdm

urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)

GTFS_ZIP = Path("data/gtfs.zip")
OUTPUT_CSV = Path("output/stations.csv")
MAX_MINUTES = 90

# ÖBB veröffentlicht jährlich neue GTFS-Dateien — erste URL versuchen, dann fallback
GTFS_URLS = [
    "https://static.web.oebb.at/open-data/soll-fahrplan-gtfs/GTFS_OP_2026_obb.zip",
    "https://static.web.oebb.at/open-data/soll-fahrplan-gtfs/GTFS_OP_2025_obb.zip",
]

# Alle relevanten Wiener Abfahrtsbahnhöfe (Direktzüge)
WIEN_KEYWORDS = [
    "Wien Hbf",
    "Wien Hauptbahnhof",
    "Wien Meidling",
    "Wien Floridsdorf",
    "Wien Praterstern",
    "Wien Westbahnhof",
    "Wien Nordbahnhof",
]


def parse_time_to_minutes(t: str) -> int:
    """GTFS-Zeit -> Minuten (unterstützt >24:00 für Nachtfahrten)"""
    h, m, _ = t.strip().split(":")
    return int(h) * 60 + int(m)


def download_gtfs():
    """Lädt GTFS-ZIP automatisch herunter falls nicht vorhanden."""
    GTFS_ZIP.parent.mkdir(exist_ok=True)
    for url in GTFS_URLS:
        print(f"Versuche Download: {url}")
        try:
            r = requests.get(url, stream=True, timeout=30, verify=False)
            if r.status_code == 200:
                total = int(r.headers.get("content-length", 0))
                with open(GTFS_ZIP, "wb") as f, tqdm(
                    total=total, unit="B", unit_scale=True, desc="Download"
                ) as bar:
                    for chunk in r.iter_content(chunk_size=8192):
                        f.write(chunk)
                        bar.update(len(chunk))
                print(f"Download erfolgreich: {GTFS_ZIP}")
                return
            else:
                print(f"  HTTP {r.status_code} — versuche nächste URL")
        except Exception as e:
            print(f"  Fehler: {e} — versuche nächste URL")
    raise RuntimeError("Kein GTFS-Download erfolgreich. Bitte manuell unter data/gtfs.zip ablegen.")


def load_gtfs(zip_path: Path) -> tuple[pd.DataFrame, pd.DataFrame]:
    print("Lade GTFS stops.txt ...")
    with zipfile.ZipFile(zip_path) as z:
        stops = pd.read_csv(
            z.open("stops.txt"),
            usecols=["stop_id", "stop_name", "stop_lat", "stop_lon"],
            dtype={"stop_id": str},
        )
        print("Lade GTFS stop_times.txt (kann gross sein, bitte warten) ...")
        stop_times = pd.read_csv(
            z.open("stop_times.txt"),
            usecols=["trip_id", "arrival_time", "departure_time", "stop_id", "stop_sequence"],
            dtype={"trip_id": str, "stop_id": str},
        )
    return stops, stop_times


def find_direct_connections(stops: pd.DataFrame, stop_times: pd.DataFrame) -> pd.DataFrame:
    # Wien-Stops identifizieren
    pattern = "|".join(WIEN_KEYWORDS)
    wien_ids = set(
        stops[stops["stop_name"].str.contains(pattern, case=False, na=False)]["stop_id"]
    )
    print(f"Wien-Bahnhöfe gefunden: {len(wien_ids)} Haltepunkte")

    # Alle stop_times an Wien-Stops -> erste Wien-Haltestelle pro Trip
    wien_st = stop_times[stop_times["stop_id"].isin(wien_ids)].copy()
    wien_st["dep_min"] = wien_st["departure_time"].apply(parse_time_to_minutes)

    # Früheste Wien-Abfahrt pro Trip (Zug fährt in Wien ein, wir nehmen ersten Wien-Stop)
    wien_dep = (
        wien_st.sort_values("stop_sequence")
        .groupby("trip_id")
        .first()[["stop_id", "dep_min", "stop_sequence"]]
        .reset_index()
        .rename(columns={
            "stop_id": "wien_stop_id",
            "dep_min": "wien_dep_min",
            "stop_sequence": "wien_seq",
        })
    )

    print(f"Trips durch Wien: {len(wien_dep)}")

    # Alle Stops nach dem Wien-Stop auf denselben Trips
    merged = stop_times.merge(wien_dep, on="trip_id")
    after_wien = merged[merged["stop_sequence"] > merged["wien_seq"]].copy()
    after_wien["arr_min"] = after_wien["arrival_time"].apply(parse_time_to_minutes)
    after_wien["travel_min"] = after_wien["arr_min"] - after_wien["wien_dep_min"]

    # Filter: 0 < Fahrzeit <= 90 Min
    in_range = after_wien[
        (after_wien["travel_min"] > 0) & (after_wien["travel_min"] <= MAX_MINUTES)
    ]

    # Pro Ziel-Stop: kürzeste Fahrzeit (direktester Zug)
    best = (
        in_range.groupby("stop_id")["travel_min"]
        .min()
        .reset_index()
        .rename(columns={"travel_min": "min_travel_min"})
    )

    # Wien-Stops selbst rausfiltern + alle Stops mit "Wien" im Namen
    best = best[~best["stop_id"].isin(wien_ids)]
    best = best.merge(
        stops[["stop_id", "stop_name", "stop_lat", "stop_lon"]], on="stop_id"
    )
    best = best[~best["stop_name"].str.contains("Wien", case=False, na=False)]

    # Duplikate: pro Stop-Name nur kürzeste Fahrzeit behalten
    result = (
        best.sort_values("min_travel_min")
        .drop_duplicates("stop_name")
        .reset_index(drop=True)
    )
    return result


def main():
    if not GTFS_ZIP.exists():
        download_gtfs()

    stops, stop_times = load_gtfs(GTFS_ZIP)
    result = find_direct_connections(stops, stop_times)

    OUTPUT_CSV.parent.mkdir(exist_ok=True)
    result.to_csv(OUTPUT_CSV, index=False)

    print(f"\nFertig! {len(result)} Bahnhöfe in Reichweite.")
    print(f"Output: {OUTPUT_CSV}\n")
    print(result[["stop_name", "min_travel_min", "stop_lat", "stop_lon"]].head(20).to_string())


if __name__ == "__main__":
    main()
