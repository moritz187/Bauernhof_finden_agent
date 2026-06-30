"""
Scraper für schlossseiten.at

Einzige reine Schloss/Burg-Plattform Österreichs.
Struktur: <a href="/immobilien/slug"><h3>Titel</h3></a>
Wahrscheinlich wenige Listings auf einer Seite.
"""

import re, time, requests, urllib3
from bs4 import BeautifulSoup
urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)

PLATFORM = "schlossseiten.at"
BASE = "https://www.schlossseiten.at"

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

def scrape():
    results, seen = [], set()
    page = 1
    while True:
        url = BASE + "/immobilien" + (f"?page={page}" if page > 1 else "")
        try:
            r = requests.get(url, headers=HEADERS, timeout=15, verify=False)
            if r.status_code != 200: break
            soup = BeautifulSoup(r.text, "lxml")

            links = soup.find_all("a", href=re.compile(r"/immobilien/\w"))
            if not links: break

            new_on_page = 0
            for a in links:
                href = a["href"].split("?")[0].split("#")[0].rstrip("/")
                full_url = BASE + href if href.startswith("/") else href
                if full_url in seen or full_url == BASE + "/immobilien": continue
                seen.add(full_url)
                new_on_page += 1

                parent = a.find_parent(["div","li","article"]) or a
                text = parent.get_text(" ", strip=True)
                title_el = parent.find(["h2","h3","h4"]) or a
                title = title_el.get_text(strip=True)

                price_str = None
                pm = re.search(r"€\s*([\d.,]+)", text)
                if pm: price_str = "€ " + pm.group(1)

                size_m2 = None
                sm = re.search(r"([\d.,]+)\s*m²", text)
                if sm: size_m2 = _num(sm.group(1))

                location = ""
                lm = re.search(r"(\d{4}\s+[A-ZÄÖÜa-zäöüß][^\d,€\n]{2,30}?)(?:\s*[,|·]|\s+\d|$)", text)
                if lm: location = lm.group(1).strip()

                lat, lon = geocode(location) if location else (None, None)

                results.append({"name": title[:150], "price_eur": price_str, "size_m2": size_m2,
                    "plot_size_m2": None, "rooms": None, "location": location,
                    "postcode": location[:4] if location and location[:4].isdigit() else None,
                    "lat": lat, "lon": lon, "url": full_url,
                    "platform": PLATFORM, "property_type": "Schloss/Burg", "description": ""})

            if new_on_page == 0: break
            if not soup.find("a", href=re.compile(r"page=\d+")): break
            page += 1
            time.sleep(0.8)
        except Exception as e:
            print(f"  [schlossseiten] Fehler S.{page}: {e}"); break

    print(f"  schlossseiten.at: {len(results)} Treffer")
    return results
