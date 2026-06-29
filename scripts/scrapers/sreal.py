"""
Scraper für sreal.at (S Real Sparkasse Immobilien)

Sparkasse-eigene Immobilienplattform, kein Aggregator — exklusive Listings.
Sehr starke Präsenz in NÖ (55+) und OÖ (76+) für Landwirtschaft/Bauernhöfe.

URL-Muster: /en/agricultural-land-purchase-{bundesland}/offer/{count}
  — die Zahl am Ende ist nur die Anzeige-Anzahl, nicht Pagination
  Pagination über: ?page=N oder separaten Parameter

Seitenstruktur wird per Fetch ermittelt.
"""

import re
import time
import requests
import urllib3
from bs4 import BeautifulSoup

urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)

PLATFORM = "sreal.at"
BASE = "https://www.sreal.at"

SEARCH_PATHS = [
    ("/en/agricultural-land-purchase-lower-austria", "Landwirtschaft NÖ"),
    ("/en/agricultural-land-purchase-upper-austria", "Landwirtschaft OÖ"),
    ("/en/agricultural-land-purchase-styria",        "Landwirtschaft Steiermark"),
    ("/en/agricultural-land-purchase",               "Landwirtschaft AT gesamt"),
]

HEADERS = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36",
    "Accept-Language": "de-AT,de;q=0.9",
    "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
}

_geocode_cache = {}


def geocode(address: str) -> tuple[float | None, float | None]:
    if address in _geocode_cache:
        return _geocode_cache[address]
    try:
        r = requests.get(
            "https://nominatim.openstreetmap.org/search",
            params={"q": address + ", Österreich", "format": "json", "limit": 1},
            headers={"User-Agent": "BauernhofFinder/1.0 moritz95meyer@gmail.com"},
            timeout=10, verify=False,
        )
        data = r.json()
        if data:
            lat, lon = float(data[0]["lat"]), float(data[0]["lon"])
            _geocode_cache[address] = (lat, lon)
            time.sleep(1.1)
            return lat, lon
    except Exception:
        pass
    _geocode_cache[address] = (None, None)
    return None, None


def _parse_num(text: str) -> float | None:
    if not text:
        return None
    clean = re.sub(r"[^\d,.]", "", text).replace(".", "").replace(",", ".")
    try:
        v = float(clean)
        return v if v > 0 else None
    except ValueError:
        return None


def scrape_path(path: str, label: str) -> list[dict]:
    results = []
    seen = set()
    page = 1

    while True:
        url = BASE + path
        if page > 1:
            url += f"?page={page}"

        try:
            r = requests.get(url, headers=HEADERS, timeout=15, verify=False)
            if r.status_code != 200:
                break
            soup = BeautifulSoup(r.text, "lxml")

            # Listings — sreal nutzt eigene Detail-URLs
            listing_links = soup.find_all("a", href=re.compile(r"/en/[a-z\-]+-\d{4,}|/de/[a-z\-]+-\d{4,}|/expose/|/objekt/"))
            if not listing_links:
                # Breiter suchen: alle internen Links die wie Immobilien-Detailseiten aussehen
                listing_links = soup.find_all("a", href=re.compile(r"sreal\.at.*\d{5,}|/property/|/immobilie/"))

            # Noch breiter: Links in Karten/Artikel-Containern
            if not listing_links:
                for art in soup.find_all(["article", "li", "div"], class_=re.compile(r"item|card|result|listing", re.I)):
                    a = art.find("a", href=True)
                    if a and "/en/" in a["href"] or "/de/" in a.get("href", ""):
                        listing_links.append(a)

            if not listing_links:
                break

            new_on_page = 0
            for link in listing_links:
                href = link.get("href", "")
                if not href:
                    continue
                full_url = BASE + href if href.startswith("/") else href
                # Nur sreal.at URLs
                if "sreal.at" not in full_url and not href.startswith("/"):
                    continue
                if full_url in seen:
                    continue
                seen.add(full_url)
                new_on_page += 1

                parent = link.find_parent(["article", "li", "div"]) or link
                text = parent.get_text(" ", strip=True)

                title_el = parent.find(["h2", "h3", "h4", "strong"])
                title = title_el.get_text(strip=True) if title_el else link.get_text(strip=True)

                price_str = None
                pm = re.search(r"€\s*([\d.,]+)", text)
                if pm:
                    price_str = "€ " + pm.group(1)

                size_m2 = None
                sm = re.search(r"([\d.,]+)\s*m²", text)
                if sm:
                    size_m2 = _parse_num(sm.group(1))

                location = ""
                lm = re.search(r"(\d{4}\s+[A-ZÄÖÜa-zäöüß][^\d,€\n]{2,30}?)(?:\s*[,|·]|\s+\d|$)", text)
                if lm:
                    location = lm.group(1).strip()

                lat, lon = None, None
                if location:
                    lat, lon = geocode(location)

                results.append({
                    "name": title[:150],
                    "price_eur": price_str,
                    "size_m2": size_m2,
                    "plot_size_m2": None,
                    "rooms": None,
                    "location": location,
                    "postcode": location[:4] if location and location[:4].isdigit() else None,
                    "lat": lat,
                    "lon": lon,
                    "url": full_url,
                    "platform": PLATFORM,
                    "property_type": "Landwirtschaft",
                    "description": "",
                })

            if new_on_page == 0:
                break

            next_btn = soup.find("a", string=re.compile(r"Next|Weiter|»|›|\d+", re.I),
                                 href=re.compile(r"page=\d+"))
            if not next_btn:
                break

            page += 1
            time.sleep(0.8)

        except Exception as e:
            print(f"  [sreal] Fehler {label} Seite {page}: {e}")
            break

    return results


def scrape() -> list[dict]:
    all_results = []
    seen_urls = set()

    for path, label in SEARCH_PATHS:
        print(f"  sreal.at: {label} ...")
        hits = scrape_path(path, label)
        new = [h for h in hits if h["url"] not in seen_urls]
        seen_urls.update(h["url"] for h in new)
        all_results.extend(new)
        print(f"    -> {len(hits)} Treffer, {len(new)} neu ({len(all_results)} gesamt)")
        time.sleep(1)

    return all_results
