"""
Scraper für muhr-immobilien.com

Spezialmakler für Waldviertel, Weinviertel, NÖ.
Struktur: <a href="/de/objekte/ID/"><h2>Titel</h2><p>Wohnfläche: X m²</p></a>
Wenige, hochwertige Listings auf wenigen Seiten.
"""

import re, time, requests, urllib3
from bs4 import BeautifulSoup
urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)

PLATFORM = "muhr-immobilien.com"
BASE = "https://www.muhr-immobilien.com"

SEARCH_PATHS = [
    ("/de/immobilien/bauernhaeuser-landwirtschaft/niederoesterreich", "Bauernhaus NÖ"),
    ("/de/immobilien/bauernhaeuser-landwirtschaft/oberoesterreich",   "Bauernhaus OÖ"),
    ("/de/immobilien/schloesser-herrenhaueser",                       "Schloss/Herrenhaus"),
    ("/de/immobilien/landwirtschaft-forstwirtschaft",                 "Landwirtschaft"),
]

HEADERS = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36",
    "Accept-Language": "de-AT,de;q=0.9",
}

_geocode_cache = {}

def geocode(address):
    if address in _geocode_cache:
        return _geocode_cache[address]
    try:
        r = requests.get("https://nominatim.openstreetmap.org/search",
            params={"q": address + ", Österreich", "format": "json", "limit": 1},
            headers={"User-Agent": "BauernhofFinder/1.0 moritz95meyer@gmail.com"},
            timeout=10, verify=False)
        d = r.json()
        if d:
            lat, lon = float(d[0]["lat"]), float(d[0]["lon"])
            _geocode_cache[address] = (lat, lon)
            time.sleep(1.1)
            return lat, lon
    except Exception:
        pass
    _geocode_cache[address] = (None, None)
    return None, None

def _num(text):
    if not text: return None
    clean = re.sub(r"[^\d,.]", "", text).replace(".", "").replace(",", ".")
    try: return float(clean)
    except: return None

def scrape_path(path, ptype):
    results, seen = [], set()
    page = 1
    while True:
        url = BASE + path + (f"?page={page}" if page > 1 else "")
        try:
            r = requests.get(url, headers=HEADERS, timeout=15, verify=False)
            if r.status_code != 200: break
            soup = BeautifulSoup(r.text, "lxml")

            # Links auf Objekt-Detailseiten
            obj_links = soup.find_all("a", href=re.compile(r"/de/objekte/\d+"))
            if not obj_links: break

            new_on_page = 0
            for a in obj_links:
                href = a["href"]
                full_url = BASE + href if href.startswith("/") else href
                if full_url in seen: continue
                seen.add(full_url)
                new_on_page += 1

                parent = a.find_parent(["div","li","article"]) or a
                text = parent.get_text(" ", strip=True)

                # Struktur: <h3>Ort</h3><h2>Titel</h2>
                h2 = parent.find("h2")
                h3 = parent.find("h3")
                title = h2.get_text(strip=True) if h2 else a.get_text(strip=True)
                location_from_h3 = h3.get_text(strip=True) if h3 else ""

                # <p> Tags mit Labels
                price_str = None
                size_m2 = None
                plot_m2 = None
                rooms = None

                for p in parent.find_all("p"):
                    t = p.get_text(strip=True)
                    if "Kaufpreis" in t or "Preis" in t:
                        pm = re.search(r"€\s*([\d.,]+)", t)
                        if pm: price_str = "€ " + pm.group(1)
                    elif "Wohnfl" in t or "Nutzfl" in t:
                        size_m2 = _num(re.sub(r"[^\d,.]", "", t.split(":")[-1]))
                    elif "Grundfl" in t or "Grundst" in t:
                        plot_m2 = _num(re.sub(r"[^\d,.]", "", t.split(":")[-1]))
                    elif "Zimmer" in t:
                        rooms = _num(re.sub(r"[^\d,.]", "", t.split(":")[-1]))

                # Ort aus h3 oder Regex
                location = location_from_h3
                if not location or not re.match(r"\d{4}", location):
                    lm = re.search(r"(\d{4}\s+[A-ZÄÖÜa-zäöüß][^\d,€\n]{2,30}?)(?:\s*[,|·]|$)", text)
                    if lm: location = lm.group(1).strip()

                lat, lon = geocode(location) if location else (None, None)

                results.append({"name": title[:150], "price_eur": price_str, "size_m2": size_m2,
                    "plot_size_m2": plot_m2, "rooms": rooms, "location": location,
                    "postcode": location[:4] if location and location[:4].isdigit() else None,
                    "lat": lat, "lon": lon, "url": full_url,
                    "platform": PLATFORM, "property_type": ptype, "description": ""})

            if new_on_page == 0: break
            if not soup.find("a", href=re.compile(r"page=\d+")): break
            page += 1
            time.sleep(0.8)
        except Exception as e:
            print(f"  [muhr] Fehler {path} S.{page}: {e}"); break
    return results

def scrape():
    all_results, seen_urls = [], set()
    for path, ptype in SEARCH_PATHS:
        print(f"  muhr-immobilien.com: {ptype} ...")
        hits = scrape_path(path, ptype)
        new = [h for h in hits if h["url"] not in seen_urls]
        seen_urls.update(h["url"] for h in new)
        all_results.extend(new)
        print(f"    -> {len(hits)} Treffer, {len(new)} neu ({len(all_results)} gesamt)")
        time.sleep(1)
    return all_results
