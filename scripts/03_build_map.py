"""
Schritt 3: Interaktive Österreich-Karte
Visualisiert Bahnhöfe + 25-Min-Fahrrad-Isochrone auf einer Folium-Karte.
Output: output/karte.html
"""

import json
import webbrowser
import pandas as pd
import folium
from folium.plugins import MarkerCluster
from pathlib import Path

INPUT_CSV = Path("output/stations.csv")
INPUT_GEOJSON = Path("output/isochrones.geojson")
OUTPUT_HTML = Path("output/karte.html")


def travel_color(minutes: int) -> str:
    """Farbe nach Fahrzeit ab Wien."""
    if minutes <= 30:
        return "#2ecc71"   # grün — nah
    elif minutes <= 60:
        return "#f39c12"   # orange — mittel
    else:
        return "#e74c3c"   # rot — weit


def build_map():
    stations = pd.read_csv(INPUT_CSV)
    geojson_data = json.loads(INPUT_GEOJSON.read_text(encoding="utf-8"))

    # Karte zentriert auf Österreich
    m = folium.Map(
        location=[47.8, 15.5],
        zoom_start=8,
        tiles=None,
    )

    # Basis-Layer
    folium.TileLayer(
        tiles="https://{s}.tile.opentopomap.org/{z}/{x}/{y}.png",
        attr="© OpenTopoMap contributors",
        name="Topographie",
        max_zoom=17,
    ).add_to(m)

    folium.TileLayer(
        tiles="OpenStreetMap",
        name="Straßenkarte",
    ).add_to(m)

    # Layer: Isochrone (25-Min-Rad-Flächen)
    iso_layer = folium.FeatureGroup(name="25 Min. Fahrrad", show=True)
    for feature in geojson_data["features"]:
        props = feature.get("properties", {})
        name = props.get("stop_name", "")
        travel = props.get("min_travel_min", 0)
        color = travel_color(travel)
        folium.GeoJson(
            feature,
            style_function=lambda f, c=color: {
                "fillColor": c,
                "color": c,
                "weight": 1,
                "fillOpacity": 0.15,
            },
            tooltip=folium.Tooltip(f"{name}<br>{travel} Min. ab Wien"),
        ).add_to(iso_layer)
    iso_layer.add_to(m)

    # Layer: Bahnhof-Marker
    station_layer = folium.FeatureGroup(name="Bahnhöfe", show=True)
    for _, row in stations.iterrows():
        color = travel_color(int(row["min_travel_min"]))
        folium.CircleMarker(
            location=[row["stop_lat"], row["stop_lon"]],
            radius=6,
            color=color,
            fill=True,
            fill_color=color,
            fill_opacity=0.9,
            tooltip=folium.Tooltip(
                f"<b>{row['stop_name']}</b><br>"
                f"🚂 {int(row['min_travel_min'])} Min. Direktzug ab Wien<br>"
                f"🚲 25 Min. Rad-Radius"
            ),
        ).add_to(station_layer)
    station_layer.add_to(m)

    # Legende
    legend_html = """
    <div style="position:fixed; bottom:30px; left:30px; z-index:1000;
                background:white; padding:12px 16px; border-radius:8px;
                box-shadow:0 2px 8px rgba(0,0,0,0.3); font-family:sans-serif; font-size:13px;">
        <b>Fahrzeit ab Wien</b><br>
        <span style="color:#2ecc71">&#9679;</span> bis 30 Min.<br>
        <span style="color:#f39c12">&#9679;</span> 30–60 Min.<br>
        <span style="color:#e74c3c">&#9679;</span> 60–90 Min.<br>
        <br>
        <span style="opacity:0.5">&#9632;</span> = 25 Min. Fahrrad-Zone
    </div>
    """
    m.get_root().html.add_child(folium.Element(legend_html))

    folium.LayerControl(collapsed=False).add_to(m)

    OUTPUT_HTML.parent.mkdir(exist_ok=True)
    m.save(str(OUTPUT_HTML))
    print(f"\nKarte gespeichert: {OUTPUT_HTML.resolve()}")
    webbrowser.open(OUTPUT_HTML.resolve().as_uri())


if __name__ == "__main__":
    build_map()
