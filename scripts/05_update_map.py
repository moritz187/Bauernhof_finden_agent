"""
Schritt 5: Karte mit Immobilien-Pins aktualisieren

Liest die bestehende Kartenbasis (Bahnhöfe + Isochrone) und fügt
Immobilien-Marker als eigenen toggle-baren Layer hinzu.

Pin-Farben nach Plattform:
  willhaben.at    → blau
  immoscout24.at  → lila
  landwirt.com    → braun
  hofnachfolge.at → orange

Tooltip zeigt: Name, Preis, Größe, nächster Bahnhof, Link zur Plattform.
"""

import json
import webbrowser
import pandas as pd
import folium
from pathlib import Path

INPUT_CSV = Path("output/immobilien.csv")
ISOCHRONES_PATH = Path("output/isochrones.geojson")
STATIONS_CSV = Path("output/stations.csv")
OUTPUT_HTML = Path("output/karte.html")


PLATFORM_COLORS = {
    "willhaben.at": "#2980b9",
    "immoscout24.at": "#8e44ad",
    "landwirt.com": "#6d4c41",
    "hofnachfolge.at": "#e67e22",
}


def travel_color(minutes: int) -> str:
    if minutes <= 30: return "#2ecc71"
    elif minutes <= 60: return "#f39c12"
    else: return "#e74c3c"


def build_map():
    stations = pd.read_csv(STATIONS_CSV)
    geojson_data = json.loads(ISOCHRONES_PATH.read_text(encoding="utf-8"))

    m = folium.Map(location=[47.8, 15.5], zoom_start=8, tiles=None)

    folium.TileLayer(
        "https://{s}.tile.opentopomap.org/{z}/{x}/{y}.png",
        attr="© OpenTopoMap",
        name="Topographie",
        max_zoom=17,
    ).add_to(m)
    folium.TileLayer("OpenStreetMap", name="Straßenkarte").add_to(m)

    # Layer 1: Isochrone-Flächen
    iso_layer = folium.FeatureGroup(name="25 Min. Fahrrad-Zone", show=True)
    for feature in geojson_data["features"]:
        props = feature.get("properties", {})
        travel = props.get("min_travel_min", 0)
        c = travel_color(travel)
        folium.GeoJson(
            feature,
            style_function=lambda f, c=c: {
                "fillColor": c, "color": c, "weight": 1, "fillOpacity": 0.12
            },
            tooltip=folium.Tooltip(
                f"{props.get('stop_name','')}<br>🚂 {travel} Min. ab Wien"
            ),
        ).add_to(iso_layer)
    iso_layer.add_to(m)

    # Layer 2: Bahnhöfe
    station_layer = folium.FeatureGroup(name="Bahnhöfe", show=True)
    for _, r in stations.iterrows():
        c = travel_color(int(r["min_travel_min"]))
        folium.CircleMarker(
            location=[r["stop_lat"], r["stop_lon"]],
            radius=5, color=c, fill=True, fill_color=c, fill_opacity=0.9,
            tooltip=folium.Tooltip(
                f"<b>{r['stop_name']}</b><br>🚂 {int(r['min_travel_min'])} Min. ab Wien"
            ),
        ).add_to(station_layer)
    station_layer.add_to(m)

    # Layer 3: Immobilien (wenn CSV vorhanden)
    if INPUT_CSV.exists():
        df = pd.read_csv(INPUT_CSV)
        df = df.dropna(subset=["lat", "lon"])
        immo_layer = folium.FeatureGroup(name="Immobilien", show=True)
        for _, r in df.iterrows():
            color = PLATFORM_COLORS.get(str(r.get("platform", "")), "#333")
            price = f"€ {r['price_eur']}" if pd.notna(r.get("price_eur")) else "Preis auf Anfrage"
            size = f"{r['size_m2']} m²" if pd.notna(r.get("size_m2")) else ""
            station = r.get("nearest_station", "")
            travel = r.get("station_travel_min", "")
            tip = (
                f"<b>{str(r.get('name',''))[:80]}</b><br>"
                f"{price}{' | ' + size if size else ''}<br>"
                f"🚂 {travel} Min. ab Wien via {station}<br>"
                f"<a href='{r.get('url','')}' target='_blank'>→ Inserat öffnen</a>"
            )
            folium.Marker(
                location=[r["lat"], r["lon"]],
                icon=folium.Icon(color="blue", icon="home", prefix="fa"),
                tooltip=folium.Tooltip(tip),
                popup=folium.Popup(tip, max_width=300),
            ).add_to(immo_layer)
        immo_layer.add_to(m)
        print(f"  {len(df)} Immobilien-Pins hinzugefügt.")
    else:
        print(f"  Keine {INPUT_CSV} gefunden — Karte ohne Immobilien-Pins.")

    # Legende
    legend_html = """
    <div style="position:fixed;bottom:30px;left:30px;z-index:1000;background:white;
    padding:12px 16px;border-radius:8px;box-shadow:0 2px 8px rgba(0,0,0,0.3);
    font-family:sans-serif;font-size:13px;">
        <b>Fahrzeit ab Wien</b><br>
        <span style="color:#2ecc71">&#9679;</span> bis 30 Min.<br>
        <span style="color:#f39c12">&#9679;</span> 30–60 Min.<br>
        <span style="color:#e74c3c">&#9679;</span> 60–90 Min.<br>
        <br><b>Immobilien</b><br>
        <span style="color:#2980b9">&#9632;</span> willhaben.at<br>
        <span style="color:#8e44ad">&#9632;</span> immoscout24.at<br>
        <span style="color:#6d4c41">&#9632;</span> landwirt.com<br>
        <span style="color:#e67e22">&#9632;</span> hofnachfolge.at
    </div>
    """
    m.get_root().html.add_child(folium.Element(legend_html))
    folium.LayerControl(collapsed=False).add_to(m)

    OUTPUT_HTML.parent.mkdir(exist_ok=True)
    m.save(str(OUTPUT_HTML))
    print(f"Karte gespeichert: {OUTPUT_HTML.resolve()}")
    webbrowser.open(OUTPUT_HTML.resolve().as_uri())


if __name__ == "__main__":
    build_map()
