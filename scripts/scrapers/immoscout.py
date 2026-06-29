"""
Scraper für immobilien.net (Austria) + immokralle.com

immobilien.net ist Österreichs spezialisierte Immobilien-Suchmaschine
und aggregiert Angebote aus mehreren Quellen inkl. Bauernhäuser/Höfe.
immokralle.com ist ein weiterer österreichischer Aggregator.

Beide nutzen HTML-Listings mit strukturierten Datenattributen.
"""

import re
import time
import requests
import urllib3
from bs4 import BeautifulSoup

urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)

HEADERS = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36",
    "Accept-Language": "de-AT,de;q=0.9",
}

# immobilien.net Kategorien
IMMONET_URLS = [
    ("https://www.immobilien.net/bauernhoefe-kaufen/oesterreich", "Bauernhof"),
    ("https://www.immobilien.net/bauernhaeuser-kaufen/oesterreich", "Bauernhaus"),
    ("https://www.immobilien.net/landhaeuser-kaufen/oesterreich", "Landhaus"),
    ("https://www.immobilien.net/schloesser-kaufen/oesterreich", "Schloss"),
]

IMMOKRALLE_URLS = [
    ("https://www.immokralle.com/immobilien/at/bauernhof", "Bauernhof"),
    ("https://www.immokralle.com/immobilien/at/landhaus", "Landhaus"),
]


def geocode(ort: str) -> tuple[float | None, float | None]:
    if not ort:
        return None, None
    try:
        r = requests.get(
            "https://nominatim.openstreetmap.org/search",
            params={"q": ort + ", Österreich", "format": "json", "limit": 1},
            headers={"User-Agent": "BauernhofFinder/1.0"},
            timeout=8, verify=False,
        )
        d = r.json()
        if d:
            return float(d[0]["lat"]), float(d[0]["lon"])
    except Exception:
        pass
    return None, None


def parse_price(text: str) -> str | None:
    m = re.search(r"([\d\.,]+)\s*€|€\s*([\d\.,]+)", text)
    return (m.group(1) or m.group(2)) if m else None


def parse_size(text: str) -> str | None:
    m = re.search(r"([\d\.,]+)\s*m[²2]", text)
    return m.group(1) if m else None


def scrape_immonet(max_pages: int = 10) -> list[dict]:
    results = []
    seen = set()
    for base_url, prop_type in IMMONET_URLS:
        print(f"  immobilien.net: '{prop_type}' ...")
        for page in range(1, max_pages + 1):
            url = base_url + (f"?page={page}" if page > 1 else "")
            try:
                r = requests.get(url, headers=HEADERS, timeout=15, verify=False)
                if r.status_code == 404:
                    break
                soup = BeautifulSoup(r.text, "html.parser")
                items = soup.select("article, div[class*='property'], div[class*='listing'], li[class*='result']")
                if not items:
                    break
                for item in items:
                    a = item.find("a", href=True)
                    href = a["href"] if a else ""
                    if not href:
                        continue
                    if not href.startswith("http"):
                        href = "https://www.immobilien.net" + href
                    if href in seen:
                        continue
                    seen.add(href)
                    text = item.get_text(" ", strip=True)
                    plz_m = re.search(r"\b(\d{4})\s+([A-Za-zÄÖÜäöü\-\s]{3,25})", text)
                    ort = plz_m.group(0).strip() if plz_m else ""
                    lat, lon = geocode(ort)
                    title_el = item.find(["h2", "h3", "h4"])
                    title = title_el.get_text(strip=True) if title_el else text[:100]
                    results.append({
                        "name": title[:150],
                        "price_eur": parse_price(text),
                        "size_m2": parse_size(text),
                        "plot_size_m2": None,
                        "rooms": None,
                        "location": ort,
                        "postcode": plz_m.group(1) if plz_m else "",
                        "lat": lat,
                        "lon": lon,
                        "url": href,
                        "platform": "immobilien.net",
                        "property_type": prop_type,
                        "description": text[:300],
                    })
                    time.sleep(0.3)
                time.sleep(1)
            except Exception as e:
                print(f"  [immobilien.net] Fehler Seite {page}: {e}")
                break
        print(f"    -> {len([x for x in results if x['property_type'] == prop_type])} Treffer")
    return results


def scrape_immokralle(max_pages: int = 5) -> list[dict]:
    results = []
    seen = set()
    for base_url, prop_type in IMMOKRALLE_URLS:
        print(f"  immokralle.com: '{prop_type}' ...")
        for page in range(1, max_pages + 1):
            url = base_url + (f"?page={page}" if page > 1 else "")
            try:
                r = requests.get(url, headers=HEADERS, timeout=15, verify=False)
                if r.status_code == 404:
                    break
                soup = BeautifulSoup(r.text, "html.parser")
                items = soup.select("article, div[class*='property'], div[class*='result']")
                if not items:
                    break
                for item in items:
                    a = item.find("a", href=True)
                    href = a["href"] if a else ""
                    if not href or href in seen:
                        continue
                    if not href.startswith("http"):
                        href = "https://www.immokralle.com" + href
                    seen.add(href)
                    text = item.get_text(" ", strip=True)
                    plz_m = re.search(r"\b(\d{4})\s+([A-Za-zÄÖÜäöü\-\s]{3,25})", text)
                    ort = plz_m.group(0).strip() if plz_m else ""
                    lat, lon = geocode(ort)
                    title_el = item.find(["h2", "h3", "h4"])
                    title = title_el.get_text(strip=True) if title_el else text[:100]
                    results.append({
                        "name": title[:150],
                        "price_eur": parse_price(text),
                        "size_m2": parse_size(text),
                        "plot_size_m2": None,
                        "rooms": None,
                        "location": ort,
                        "postcode": plz_m.group(1) if plz_m else "",
                        "lat": lat,
                        "lon": lon,
                        "url": href,
                        "platform": "immokralle.com",
                        "property_type": prop_type,
                        "description": text[:300],
                    })
                    time.sleep(0.3)
                time.sleep(1)
            except Exception as e:
                print(f"  [immokralle] Fehler Seite {page}: {e}")
                break
        print(f"    -> Treffer gesammelt")
    return results


def scrape() -> list[dict]:
    return scrape_immonet() + scrape_immokralle()
