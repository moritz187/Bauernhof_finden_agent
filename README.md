# Bauernhof Finder

Ein Python-basierter Agent der geeignete Immobilien für eine Wohngemeinschaft mehrerer Parteien in der Nähe von Wien findet und auf einer interaktiven Karte visualisiert.

## Idee

Wir suchen einen Bauernhof / Landhaus / Schloss für **2–5 Pärchen (Anfang 30)** zum gemeinsamen Kauf — mit direkter Zuganbindung nach Wien.

**Kriterien:**

| Kriterium | Wert |
|---|---|
| Zugverbindung | Max. 90 Min. Direktzug ab Wien (kein Umsteigen) |
| Rad vom Bahnhof | Max. 25 Min. (reale Fahrradrouten) |
| Lage | Außerhalb Wien, Österreich |
| Wohnfläche | ab 175 m² |
| Grundstück | ab 4.000 m² |
| Objekttyp | Bauernhof, Landhaus, Schloss, Weingut, Reiterhof |
| Budget | Offen |
| Zustand | Schlüsselfertig bis Vollrenovierung |

## Features

- **Interaktive Karte** mit Leaflet.js — Topographie + Straßenkarte
- **Isochrone-Flächen** — reale 25-Min-Fahrrad-Zonen um jeden Bahnhof (OpenRouteService)
- **Immobilien-Sidebar** mit Live-Filtern (Fahrzeit, Wohnfläche, Preis, Grundstück, Plattform, Typ)
- **Favoriten-System** — ⭐ Objekte markieren, bleibt nach Schließen gespeichert (localStorage)
- **Favoriten-Marker** auf der Karte gold hervorgehoben
- **Direktlinks** zu Inseraten auf willhaben, landwirt.com, immobilien.net, immokralle.com

## Projektstruktur

```
Bauernhof_finden_agent/
├── config.py                    # Alle Suchkriterien zentral
├── requirements.txt
├── data/
│   └── gtfs.zip                 # ÖBB Fahrplandaten (auto-download)
├── output/
│   ├── stations.csv             # 229 Bahnhöfe mit Direktzug ab Wien
│   ├── isochrones.geojson       # 25-Min-Fahrrad-Polygone
│   ├── immobilien.csv           # Gefundene Immobilien (innerhalb Isochrone)
│   ├── manual_check.csv         # Treffer ohne Koordinaten (manuell prüfen)
│   └── karte_advanced.html      # Finale interaktive Karte
└── scripts/
    ├── 01_filter_gtfs.py        # GTFS auswerten → stations.csv
    ├── 02_get_isochrones.py     # ORS API → isochrones.geojson
    ├── 03_build_map.py          # Einfache Karte (Bahnhöfe + Isochrone)
    ├── 04_scrape_immobilien.py  # Alle Scraper ausführen + filtern
    ├── 05_update_map.py         # Karte mit Immobilien-Pins updaten
    ├── 06_build_advanced_map.py # Erweiterte Karte mit Sidebar + Favoriten
    └── scrapers/
        ├── willhaben.py         # willhaben.at (via __NEXT_DATA__ JSON)
        ├── immoscout.py         # immobilien.net + immokralle.com
        ├── landwirt.py          # landwirt.com (Agrarimmobilien)
        └── hofnachfolge.py      # hofnachfolge.at (Hofübergaben)
```

## Setup

```bash
pip install -r requirements.txt
```

Für Schritt 2 (Isochrone) wird ein kostenloser API-Key von [openrouteservice.org](https://openrouteservice.org/dev/#/signup) benötigt:

```
# .env Datei anlegen:
ORS_API_KEY=dein_key
```

## Ausführen

```bash
# 1. Bahnhöfe mit Direktzug ab Wien finden
python scripts/01_filter_gtfs.py

# 2. 25-Min-Fahrrad-Isochrone berechnen (~10 Min, braucht ORS Key)
python scripts/02_get_isochrones.py

# 3. Immobilien scrapen (willhaben, landwirt.com, immobilien.net, immokralle)
python scripts/04_scrape_immobilien.py

# 4. Finale Karte mit Sidebar + Favoriten bauen
python scripts/06_build_advanced_map.py
```

## Datenquellen

| Quelle | Verwendung |
|---|---|
| [ÖBB GTFS](https://data.oebb.at/de/datensaetze~soll-fahrplan-gtfs~) | Fahrplandaten für Direktzug-Filter |
| [OpenRouteService](https://openrouteservice.org) | Fahrrad-Isochrone (reale Routen) |
| [OpenStreetMap / Nominatim](https://nominatim.openstreetmap.org) | Geocodierung von Adressen |
| [willhaben.at](https://www.willhaben.at) | Immobilien-Inserate |
| [landwirt.com](https://www.landwirt.com) | Agrarimmobilien |
| [immobilien.net](https://www.immobilien.net) | Immobilien-Aggregator |
| [immokralle.com](https://www.immokralle.com) | Immobilien-Aggregator |
| [hofnachfolge.at](https://www.hofnachfolge.at) | Hofübergaben Österreich |

## Nächste Schritte

- [ ] Gewässer / Seen / Naturpark-Layer auf der Karte
- [ ] Automatischer Re-Scraper (neue Inserate täglich updaten)
- [ ] Export der Favoriten als PDF / Sharelink
- [ ] Preishistorie und Marktanalyse
