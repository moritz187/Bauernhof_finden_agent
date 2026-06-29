"""
Schritt 6: Erweiterte Karte mit Immobilien-Sidebar

Baut eine vollständige HTML-Anwendung:
  - Leaflet-Map (links, 65% Breite) mit Bahnhöfen + Isochrone
  - Sidebar (rechts, 35% Breite) mit Immobilien-Liste + Live-Filter

Filter in der Sidebar:
  - Fahrzeit ab Wien (Slider)
  - Wohnfläche mindestens (m²)
  - Preis maximal (€)
  - Plattform (Checkboxen)
  - Objekttyp (Checkboxen)

Interaktion:
  - Klick auf Inserat in Sidebar → Karte springt zum Marker + Popup öffnet
  - Klick auf Marker → Inserat in Sidebar wird hervorgehoben
  - Filter ändern → Karte + Liste aktualisieren sich live

Output: output/karte_advanced.html
"""

import json
import webbrowser
import pandas as pd
from pathlib import Path

STATIONS_CSV = Path("output/stations.csv")
ISOCHRONES_PATH = Path("output/isochrones.geojson")
IMMOBILIEN_CSV = Path("output/immobilien.csv")
OUTPUT_HTML = Path("output/karte_advanced.html")


def load_data():
    stations = pd.read_csv(STATIONS_CSV).to_dict("records")
    isochrones = json.loads(ISOCHRONES_PATH.read_text(encoding="utf-8"))

    properties = []
    if IMMOBILIEN_CSV.exists():
        df = pd.read_csv(IMMOBILIEN_CSV)
        df = df.where(pd.notna(df), None)
        properties = df.to_dict("records")

    return stations, isochrones, properties


def build_html(stations, isochrones, properties):
    stations_json = json.dumps(stations, ensure_ascii=False)
    isochrones_json = json.dumps(isochrones, ensure_ascii=False)
    properties_json = json.dumps(properties, ensure_ascii=False)

    html = f"""<!DOCTYPE html>
<html lang="de">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1.0">
<title>Bauernhof Finder</title>
<link rel="stylesheet" href="https://unpkg.com/leaflet@1.9.4/dist/leaflet.css"/>
<script src="https://unpkg.com/leaflet@1.9.4/dist/leaflet.js"></script>
<style>
  * {{ box-sizing: border-box; margin: 0; padding: 0; }}
  body {{ font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', sans-serif; display: flex; height: 100vh; overflow: hidden; background: #f5f5f5; }}

  #map {{ flex: 1; height: 100vh; }}

  #sidebar {{ width: 400px; min-width: 340px; height: 100vh; display: flex; flex-direction: column; background: #fff; border-left: 1px solid #ddd; box-shadow: -2px 0 8px rgba(0,0,0,0.1); }}

  #sidebar-header {{ padding: 14px 16px; background: #2c3e50; color: white; display: flex; justify-content: space-between; align-items: center; }}
  #sidebar-header h1 {{ font-size: 15px; font-weight: 600; }}
  #sidebar-header p {{ font-size: 11px; opacity: 0.6; margin-top: 2px; }}

  #filters {{ padding: 12px 16px; border-bottom: 1px solid #eee; background: #fafafa; }}
  .filter-row {{ margin-bottom: 10px; }}
  .filter-label {{ font-size: 11px; font-weight: 600; color: #555; text-transform: uppercase; letter-spacing: 0.5px; margin-bottom: 4px; display: flex; justify-content: space-between; }}
  .filter-label span {{ font-weight: 400; color: #2980b9; }}
  input[type=range] {{ width: 100%; accent-color: #2980b9; }}
  .checkboxes {{ display: flex; flex-wrap: wrap; gap: 4px; }}
  .cb-label {{ font-size: 11px; background: #eef2f7; border: 1px solid #d0d9e8; border-radius: 12px; padding: 3px 8px; cursor: pointer; user-select: none; }}
  .cb-label:has(input:checked) {{ background: #2980b9; color: white; border-color: #2980b9; }}
  .cb-label input {{ display: none; }}
  #filter-reset {{ font-size: 11px; color: #999; cursor: pointer; text-decoration: underline; float: right; margin-top: -2px; }}
  #filter-reset:hover {{ color: #e74c3c; }}

  #results-header {{ padding: 8px 12px; font-size: 12px; color: #666; border-bottom: 1px solid #eee; display: flex; justify-content: space-between; align-items: center; gap: 6px; }}
  #result-count {{ font-weight: 600; color: #2c3e50; white-space: nowrap; }}

  /* FAVORITES TOGGLE */
  #fav-toggle {{ font-size: 11px; padding: 3px 10px; border-radius: 12px; border: 1.5px solid #f1c40f; background: #fff; color: #b7950b; cursor: pointer; font-weight: 600; white-space: nowrap; transition: all 0.15s; }}
  #fav-toggle:hover {{ background: #fef9e7; }}
  #fav-toggle.active {{ background: #f1c40f; color: #5d4c00; border-color: #f1c40f; }}
  #fav-count {{ display: inline-block; background: #e74c3c; color: white; border-radius: 8px; font-size: 10px; padding: 0 5px; margin-left: 3px; }}

  #results-list {{ flex: 1; overflow-y: auto; }}

  /* PROPERTY CARD */
  .property-card {{ padding: 11px 14px; border-bottom: 1px solid #f0f0f0; cursor: pointer; transition: background 0.15s; position: relative; }}
  .property-card:hover {{ background: #f0f7ff; }}
  .property-card.active {{ background: #e8f4fd; border-left: 3px solid #2980b9; padding-left: 11px; }}
  .property-card.favorited {{ border-left: 3px solid #f1c40f; padding-left: 11px; }}
  .property-card.favorited.active {{ border-left: 3px solid #2980b9; }}

  .card-top {{ display: flex; justify-content: space-between; align-items: flex-start; gap: 6px; }}
  .card-platform {{ font-size: 10px; font-weight: 600; text-transform: uppercase; letter-spacing: 0.5px; margin-bottom: 3px; }}
  .card-title {{ font-size: 13px; font-weight: 600; color: #2c3e50; margin-bottom: 5px; line-height: 1.3; flex: 1; }}
  .fav-btn {{ background: none; border: none; font-size: 16px; cursor: pointer; padding: 0 2px; line-height: 1; flex-shrink: 0; opacity: 0.3; transition: opacity 0.15s, transform 0.15s; }}
  .fav-btn:hover {{ opacity: 0.7; transform: scale(1.2); }}
  .fav-btn.on {{ opacity: 1; }}

  .card-meta {{ display: flex; flex-wrap: wrap; gap: 5px; margin-bottom: 5px; }}
  .tag {{ font-size: 11px; background: #f0f0f0; border-radius: 4px; padding: 2px 6px; color: #555; }}
  .tag.price {{ background: #e8f8f0; color: #27ae60; font-weight: 600; }}
  .tag.travel {{ background: #fef9e7; color: #e67e22; }}
  .card-location {{ font-size: 11px; color: #888; margin-bottom: 4px; }}
  .card-link {{ font-size: 11px; color: #2980b9; text-decoration: none; }}
  .card-link:hover {{ text-decoration: underline; }}

  .no-results {{ padding: 40px 20px; text-align: center; color: #aaa; }}
  .no-results .icon {{ font-size: 36px; margin-bottom: 8px; }}

  .legend {{ padding: 8px 16px; border-top: 1px solid #eee; background: #fafafa; }}
  .legend-title {{ font-size: 10px; font-weight: 600; color: #888; text-transform: uppercase; margin-bottom: 5px; }}
  .legend-items {{ display: flex; gap: 12px; flex-wrap: wrap; font-size: 11px; }}
  .legend-dot {{ width: 9px; height: 9px; border-radius: 50%; display: inline-block; margin-right: 3px; }}
</style>
</head>
<body>
<div id="map"></div>
<div id="sidebar">
  <div id="sidebar-header">
    <div>
      <h1>Bauernhof Finder</h1>
      <p>Direktzug ab Wien · 25 Min. Rad vom Bahnhof</p>
    </div>
  </div>

  <div id="filters">
    <div class="filter-row">
      <div class="filter-label">Fahrzeit ab Wien <span id="travel-val">90 Min.</span></div>
      <input type="range" id="f-travel" min="15" max="90" value="90" step="5">
    </div>
    <div class="filter-row">
      <div class="filter-label">Wohnfläche mind. <span id="size-val">175 m²</span></div>
      <input type="range" id="f-size" min="0" max="800" value="175" step="25">
    </div>
    <div class="filter-row">
      <div class="filter-label">Preis max. <span id="price-val">kein Limit</span></div>
      <input type="range" id="f-price" min="0" max="3000000" value="3000000" step="50000">
    </div>
    <div class="filter-row">
      <div class="filter-label">Grundstück mind. <span id="plot-val">4.000 m²</span></div>
      <input type="range" id="f-plot" min="0" max="50000" value="4000" step="500">
    </div>
    <div class="filter-row">
      <div class="filter-label">Plattform</div>
      <div class="checkboxes" id="platform-filters"></div>
    </div>
    <div class="filter-row">
      <div class="filter-label">Objekttyp</div>
      <div class="checkboxes" id="type-filters"></div>
    </div>
    <span id="filter-reset">Filter zurücksetzen</span>
  </div>

  <div id="results-header">
    <span id="result-count">0 Objekte</span>
    <button id="fav-toggle">★ Favoriten <span id="fav-count">0</span></button>
    <span style="font-size:11px;color:#ccc">Klick→Karte</span>
  </div>

  <div id="results-list"></div>

  <div class="legend">
    <div class="legend-title">Fahrzeit ab Wien</div>
    <div class="legend-items">
      <span><span class="legend-dot" style="background:#2ecc71"></span>bis 30 Min.</span>
      <span><span class="legend-dot" style="background:#f39c12"></span>30–60 Min.</span>
      <span><span class="legend-dot" style="background:#e74c3c"></span>60–90 Min.</span>
      <span><span class="legend-dot" style="background:#f1c40f;border:1px solid #ccc"></span>Favorit</span>
    </div>
  </div>
</div>

<script>
const STATIONS = {stations_json};
const ISOCHRONES = {isochrones_json};
const PROPERTIES = {properties_json};

// ── FAVORITES (localStorage) ───────────────────────────────────
const FAV_KEY = 'bauernhof_favorites';
let favorites = new Set(JSON.parse(localStorage.getItem(FAV_KEY) || '[]'));
let showOnlyFavs = false;

function saveFavorites() {{
  localStorage.setItem(FAV_KEY, JSON.stringify([...favorites]));
}}

function toggleFav(index, e) {{
  e.stopPropagation();
  if (favorites.has(index)) {{
    favorites.delete(index);
  }} else {{
    favorites.add(index);
  }}
  saveFavorites();
  updateFavCount();
  updateMarkerStyle(index);
  renderList();
}}

function updateFavCount() {{
  document.getElementById('fav-count').textContent = favorites.size;
}}

// ── MAP INIT ──────────────────────────────────────────────────
const map = L.map('map').setView([47.8, 15.5], 8);
L.tileLayer('https://{{s}}.tile.opentopomap.org/{{z}}/{{x}}/{{y}}.png', {{
  attribution: '© OpenTopoMap', maxZoom: 17
}}).addTo(map);

function travelColor(min) {{
  if (min <= 30) return '#2ecc71';
  if (min <= 60) return '#f39c12';
  return '#e74c3c';
}}
function platformColor(p) {{
  const c = {{'willhaben.at':'#2980b9','immobilien.net':'#8e44ad','immokralle.com':'#16a085','landwirt.com':'#6d4c41','hofnachfolge.at':'#e67e22'}};
  return c[p] || '#555';
}}
function parseNum(v) {{
  if (v === null || v === undefined) return null;
  const n = parseFloat(String(v).replace(/[^0-9.,]/g,'').replace(',','.'));
  return isNaN(n) ? null : n;
}}

// Isochrone
ISOCHRONES.features.forEach(f => {{
  const c = travelColor(f.properties.min_travel_min || 0);
  L.geoJSON(f, {{ style: {{ fillColor: c, color: c, weight: 1, fillOpacity: 0.12 }} }}).addTo(map);
}});

// Bahnhöfe
STATIONS.forEach(s => {{
  const c = travelColor(s.min_travel_min);
  L.circleMarker([s.stop_lat, s.stop_lon], {{ radius: 4, color: c, fillColor: c, fillOpacity: 0.8, weight: 1 }})
    .bindTooltip(`<b>${{s.stop_name}}</b><br>🚂 ${{s.min_travel_min}} Min. ab Wien`).addTo(map);
}});

// ── PROPERTY MARKERS ──────────────────────────────────────────
const propMarkers = [];
const propLayerGroup = L.layerGroup().addTo(map);

PROPERTIES.forEach((p, i) => {{
  if (!p.lat || !p.lon) return;
  const marker = L.circleMarker([p.lat, p.lon], markerStyle(i, p));
  const price = p.price_eur ? `€ ${{p.price_eur}}` : 'Preis auf Anfrage';
  const size = p.size_m2 ? `${{p.size_m2}} m²` : '';
  marker.bindPopup(`
    <b>${{(p.name||'').substring(0,80)}}</b><br>
    ${{price}}${{size ? ' · ' + size : ''}}<br>
    🚂 ${{p.station_travel_min||'?'}} Min. via ${{p.nearest_station||''}}<br>
    <a href="${{p.url}}" target="_blank">→ Inserat öffnen</a>
  `, {{maxWidth: 280}});
  marker.on('click', () => highlightCard(i));
  propMarkers.push({{ marker, data: p, index: i, visible: true }});
}});

function markerStyle(i, p) {{
  const isFav = favorites.has(i);
  return {{
    radius: isFav ? 10 : 8,
    color: isFav ? '#5d4c00' : '#fff',
    fillColor: isFav ? '#f1c40f' : platformColor(p.platform),
    fillOpacity: 0.95,
    weight: isFav ? 2 : 2,
  }};
}}

function updateMarkerStyle(i) {{
  const pm = propMarkers[i];
  if (pm) pm.marker.setStyle(markerStyle(i, pm.data));
}}

function highlightCard(i) {{
  document.querySelectorAll('.property-card').forEach(c => c.classList.remove('active'));
  const card = document.querySelector(`.property-card[data-index="${{i}}"]`);
  if (card) {{ card.classList.add('active'); card.scrollIntoView({{ behavior: 'smooth', block: 'nearest' }}); }}
}}

// ── FILTERS ───────────────────────────────────────────────────
const platforms = [...new Set(PROPERTIES.map(p => p.platform).filter(Boolean))];
platforms.forEach(pl => {{
  const l = document.createElement('label'); l.className = 'cb-label';
  l.innerHTML = `<input type="checkbox" value="${{pl}}" checked> ${{pl}}`;
  document.getElementById('platform-filters').appendChild(l);
}});

const types = [...new Set(PROPERTIES.map(p => p.property_type).filter(Boolean))];
types.forEach(t => {{
  const l = document.createElement('label'); l.className = 'cb-label';
  l.innerHTML = `<input type="checkbox" value="${{t}}" checked> ${{t}}`;
  document.getElementById('type-filters').appendChild(l);
}});

const fTravel = document.getElementById('f-travel');
const fSize   = document.getElementById('f-size');
const fPrice  = document.getElementById('f-price');
const fPlot   = document.getElementById('f-plot');

fTravel.oninput = () => {{ document.getElementById('travel-val').textContent = fTravel.value + ' Min.'; applyFilters(); }};
fSize.oninput   = () => {{ document.getElementById('size-val').textContent = fSize.value + ' m²'; applyFilters(); }};
fPrice.oninput  = () => {{
  const v = parseInt(fPrice.value);
  document.getElementById('price-val').textContent = v >= 3000000 ? 'kein Limit' : '€ ' + v.toLocaleString('de-AT');
  applyFilters();
}};
fPlot.oninput = () => {{
  const v = parseInt(fPlot.value);
  document.getElementById('plot-val').textContent = v === 0 ? 'kein Limit' : v.toLocaleString('de-AT') + ' m²';
  applyFilters();
}};

document.querySelectorAll('#platform-filters input, #type-filters input').forEach(cb => cb.onchange = applyFilters);

// Reset → zurück zu Standard-Defaults
document.getElementById('filter-reset').onclick = () => {{
  fTravel.value = 90; document.getElementById('travel-val').textContent = '90 Min.';
  fSize.value = 175;  document.getElementById('size-val').textContent = '175 m²';
  fPrice.value = 3000000; document.getElementById('price-val').textContent = 'kein Limit';
  fPlot.value = 4000; document.getElementById('plot-val').textContent = '4.000 m²';
  document.querySelectorAll('#platform-filters input, #type-filters input').forEach(cb => cb.checked = true);
  showOnlyFavs = false;
  document.getElementById('fav-toggle').classList.remove('active');
  applyFilters();
}};

// Favorites toggle
document.getElementById('fav-toggle').onclick = () => {{
  showOnlyFavs = !showOnlyFavs;
  document.getElementById('fav-toggle').classList.toggle('active', showOnlyFavs);
  applyFilters();
}};

// ── APPLY FILTERS ─────────────────────────────────────────────
function applyFilters() {{
  const maxTravel = parseInt(fTravel.value);
  const minSize   = parseInt(fSize.value);
  const maxPrice  = parseInt(fPrice.value);
  const minPlot   = parseInt(fPlot.value);
  const activePlatforms = new Set([...document.querySelectorAll('#platform-filters input:checked')].map(c => c.value));
  const activeTypes     = new Set([...document.querySelectorAll('#type-filters input:checked')].map(c => c.value));

  propLayerGroup.clearLayers();
  let visible = 0;

  propMarkers.forEach(pm => {{
    const p = pm.data;
    if (showOnlyFavs && !favorites.has(pm.index)) {{ pm.visible = false; return; }}
    const travel   = parseNum(p.station_travel_min);
    const size     = parseNum(p.size_m2);
    const plot     = parseNum(p.plot_size_m2);
    const priceRaw = parseNum(String(p.price_eur || '').replace(/[^0-9]/g,''));
    const ok = (
      (!travel || travel <= maxTravel) &&
      (minSize === 0 || !size || size >= minSize) &&
      (maxPrice >= 3000000 || !priceRaw || priceRaw <= maxPrice) &&
      (minPlot === 0 || !plot || plot >= minPlot) &&
      activePlatforms.has(p.platform) &&
      activeTypes.has(p.property_type)
    );
    pm.visible = ok;
    if (ok) {{ propLayerGroup.addLayer(pm.marker); visible++; }}
  }});

  renderList();
  document.getElementById('result-count').textContent = visible + ' Objekte';
}}

// ── RENDER LIST ───────────────────────────────────────────────
function renderList() {{
  const list = document.getElementById('results-list');
  const visible = propMarkers.filter(pm => pm.visible);

  if (visible.length === 0) {{
    const msg = showOnlyFavs ? '⭐ Noch keine Favoriten.' : 'Keine Objekte gefunden.';
    list.innerHTML = `<div class="no-results"><div class="icon">🏚</div>${{msg}}<br><small>Filter anpassen</small></div>`;
    return;
  }}

  // Favoriten zuerst
  const sorted = [...visible].sort((a, b) => (favorites.has(b.index) ? 1 : 0) - (favorites.has(a.index) ? 1 : 0));

  list.innerHTML = sorted.map(pm => {{
    const p = pm.data;
    const isFav = favorites.has(pm.index);
    const price  = p.price_eur ? `€ ${{p.price_eur}}` : null;
    const size   = p.size_m2   ? `${{p.size_m2}} m²`   : null;
    const travel = p.station_travel_min ? `🚂 ${{p.station_travel_min}} Min.` : null;
    const c = platformColor(p.platform);
    return `
      <div class="property-card${{isFav ? ' favorited' : ''}}" data-index="${{pm.index}}" onclick="cardClick(${{pm.index}}, ${{p.lat}}, ${{p.lon}})">
        <div class="card-top">
          <div style="flex:1">
            <div class="card-platform" style="color:${{c}}">${{p.platform || ''}}</div>
            <div class="card-title">${{(p.name || 'Objekt ohne Titel').substring(0,90)}}</div>
          </div>
          <button class="fav-btn${{isFav ? ' on' : ''}}" onclick="toggleFav(${{pm.index}}, event)" title="Zu Favoriten">⭐</button>
        </div>
        <div class="card-meta">
          ${{price  ? `<span class="tag price">${{price}}</span>` : ''}}
          ${{size   ? `<span class="tag">${{size}}</span>` : ''}}
          ${{travel ? `<span class="tag travel">${{travel}}</span>` : ''}}
          ${{p.property_type ? `<span class="tag">${{p.property_type}}</span>` : ''}}
        </div>
        ${{p.nearest_station || p.location ? `<div class="card-location">📍 ${{p.nearest_station||''}}${{p.location ? ' · '+p.location : ''}}</div>` : ''}}
        ${{p.url ? `<a class="card-link" href="${{p.url}}" target="_blank" onclick="event.stopPropagation()">Inserat öffnen →</a>` : ''}}
      </div>`;
  }}).join('');
}}

function cardClick(i, lat, lon) {{
  highlightCard(i);
  if (lat && lon) {{ map.setView([lat, lon], 13, {{animate: true}}); propMarkers[i].marker.openPopup(); }}
}}

// ── INIT ─────────────────────────────────────────────────────
updateFavCount();
applyFilters();
</script>
</body>
</html>"""
    return html


def main():
    print("Lade Daten ...")
    stations, isochrones, properties = load_data()
    print(f"  {len(stations)} Bahnhöfe, {len(isochrones['features'])} Isochrone, {len(properties)} Immobilien")

    html = build_html(stations, isochrones, properties)
    OUTPUT_HTML.parent.mkdir(exist_ok=True)
    OUTPUT_HTML.write_text(html, encoding="utf-8")
    print(f"Karte gespeichert: {OUTPUT_HTML.resolve()}")
    webbrowser.open(OUTPUT_HTML.resolve().as_uri())


if __name__ == "__main__":
    main()
