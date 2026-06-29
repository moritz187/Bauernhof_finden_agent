"""
Scraper für my-landimmo.de

DACH-Spezialist für Bauernhöfe, Landhäuser, Schlösser.
Deckt explizit Österreich ab. Links: expose/ID/slug.html
Details in <strong>Label:</strong> Value Format. Pagination: ?pg=N
"""

import re, time, requests, urllib3
from bs4 import BeautifulSoup
urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)

PLATFORM = "my-landimmo.de"
BASE = "https://www.my-landimmo.de"

SEARCH_URLS = [
    ("/bauernhaus-kaufen-niederoesterreich.html",    "Bauernhaus NÖ"),
    ("/bauernhaus-kaufen-oberoesterreich.html",      "Bauernhaus OÖ"),
    ("/bauernhaus-kaufen-steiermark.html",           "Bauernhaus Steiermark"),
    ("/schloss-oder-burg-kaufen-oesterreich.html",   "Schloss/Burg AT"),
    ("/landhaus-kaufen-oesterreich.html",            "Landhaus AT"),
    ("/reiterhof-kaufen-oesterreich.html",           "Reiterhof AT"),
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

def _strong_val(soup_el, label):
    """Findet <strong>Label</strong> Value Muster."""
    for strong in soup_el.find_all("strong"):
        if label.lower() in strong.get_text().lower():
            # Wert steht direkt nach dem <strong> Tag als Text
            next_text = strong.next_sibling
            if next_text:
                return str(next_text).strip().strip(":")
    return None

def scrape_path(path, ptype):
    results, seen = [], set()
    page = 1
    while True:
        url = BASE + path + (f"?pg={page}" if page > 1 else "")
        try:
            r = requests.get(url, headers=HEADERS, timeout=15, verify=False)
            if r.status_code != 200: break
            soup = BeautifulSoup(r.text, "lxml")

            # Links auf Expose-Seiten
            expose_links = soup.find_all("a", href=re.compile(r"expose/\d+"))
            if not expose_links: break

            new_on_page = 0
            processed = set()

            for a in expose_links:
                href = a["href"]
                full_url = BASE + "/" + href.lstrip("/") if not href.startswith("http") else href
                if full_url in seen or full_url in processed: continue
                processed.add(full_url)
                seen.add(full_url)
                new_on_page += 1

                # Container des Links
                parent = a.find_parent(["div", "li", "article", "section"])
                if not parent:
                    parent = a

                text = parent.get_text(" ", strip=True)
                title_el = parent.find(["h2","h3","h4"])
                title = title_el.get_text(strip=True) if title_el else a.get_text(strip=True)

                # <strong>Label:</strong> Value Struktur
                location = _strong_val(parent, "Ort") or _strong_val(parent, "Standort") or ""
                size_str = _strong_val(parent, "Wohnfl") or _strong_val(parent, "Nutzfl") or ""
                price_str_raw = _strong_val(parent, "Kaufpreis") or _strong_val(parent, "Preis") or ""

                size_m2 = _num(size_str)
                price_str = ("€ " + price_str_raw.replace("€","").strip()) if price_str_raw else None

                # Fallback per Regex
                if not location:
                    lm = re.search(r"(\d{4}\s+[A-ZÄÖÜa-zäöüß][^\d,€\n]{2,30}?)(?:\s*[,|·]|\s+\d|$)", text)
                    if lm: location = lm.group(1).strip()
                if not price_str:
                    pm = re.search(r"€\s*([\d.,]+)", text)
                    if pm: price_str = "€ " + pm.group(1)
                if not size_m2:
                    sm = re.search(r"([\d.,]+)\s*m²", text)
                    if sm: size_m2 = _num(sm.group(1))

                lat, lon = geocode(location) if location else (None, None)

                results.append({"name": title[:150], "price_eur": price_str, "size_m2": size_m2,
                    "plot_size_m2": None, "rooms": None, "location": location,
                    "postcode": location[:4] if location and location[:4].isdigit() else None,
                    "lat": lat, "lon": lon, "url": full_url,
                    "platform": PLATFORM, "property_type": ptype, "description": ""})

            if new_on_page == 0: break
            if not soup.find("a", href=re.compile(r"\?pg=\d+")):
                break
            page += 1
            time.sleep(0.8)
        except Exception as e:
            print(f"  [my-landimmo] Fehler {path} S.{page}: {e}"); break
    return results

def scrape():
    all_results, seen_urls = [], set()
    for path, ptype in SEARCH_URLS:
        print(f"  my-landimmo.de: {ptype} ...")
        hits = scrape_path(path, ptype)
        new = [h for h in hits if h["url"] not in seen_urls]
        seen_urls.update(h["url"] for h in new)
        all_results.extend(new)
        print(f"    -> {len(hits)} Treffer, {len(new)} neu ({len(all_results)} gesamt)")
        time.sleep(1)
    return all_results
