"""
Scraper für immo.trend.at (Wirtschaftsmagazin trend.at)

~140 Bauernhäuser + ~23 Bauernhöfe AT. Eigene Listings, kein Aggregator.
Pagination: ?p=N
"""

import re, time, requests, urllib3
from bs4 import BeautifulSoup
urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)

PLATFORM = "immo.trend.at"
BASE = "https://immo.trend.at"

SEARCH_URLS = [
    ("/de/lp-11971/bauernhaus-kauf", "Bauernhaus"),
    ("/de/lp-12340/bauernhof-kauf",  "Bauernhof"),
    ("/de/lp-17968/bauernhof-kauf-oberoesterreich", "Bauernhof OÖ"),
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
        url = BASE + path + (f"?p={page}" if page > 1 else "")
        try:
            r = requests.get(url, headers=HEADERS, timeout=15, verify=False)
            if r.status_code != 200: break
            soup = BeautifulSoup(r.text, "lxml")

            cards = soup.find_all(["div", "article"], class_=re.compile(r"property|listing|result|item", re.I))
            if not cards:
                # Fallback: alle internen Links die auf Detailseiten zeigen
                cards = [a.find_parent(["div","li"]) for a in soup.find_all("a", href=re.compile(r"/de/\w.*\d"))]
                cards = [c for c in cards if c]

            if not cards: break
            new_on_page = 0

            for card in cards:
                a = card.find("a", href=True)
                if not a: continue
                href = a["href"]
                full_url = BASE + href if href.startswith("/") else href
                if full_url in seen: continue
                seen.add(full_url)
                new_on_page += 1

                text = card.get_text(" ", strip=True)
                title_el = card.find(["h2","h3","h4","h5"])
                title = title_el.get_text(strip=True) if title_el else text[:80]

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
                    "platform": PLATFORM, "property_type": ptype, "description": ""})

            if new_on_page == 0: break
            if not soup.find("a", string=re.compile(r"vor|next|»|›|\d+", re.I)): break
            page += 1
            time.sleep(0.8)
        except Exception as e:
            print(f"  [immo.trend] Fehler {path} S.{page}: {e}"); break
    return results

def scrape():
    all_results, seen_urls = [], set()
    for path, ptype in SEARCH_URLS:
        print(f"  immo.trend.at: {ptype} ...")
        hits = scrape_path(path, ptype)
        new = [h for h in hits if h["url"] not in seen_urls]
        seen_urls.update(h["url"] for h in new)
        all_results.extend(new)
        print(f"    -> {len(hits)} Treffer, {len(new)} neu ({len(all_results)} gesamt)")
        time.sleep(1)
    return all_results
