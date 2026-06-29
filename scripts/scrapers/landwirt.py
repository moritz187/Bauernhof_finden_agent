"""
Scraper für landwirt.com

Parst die Kleinanzeigen-Listings für Österreich.
Koordinaten werden via Nominatim aus PLZ/Ort geocodiert.

URL-Struktur:
  https://www.landwirt.com/kleinanzeigen/realitaeten-immobilien/{kategorie}/land-oesterreich
  Paginierung: ?page=2
"""

import re
import time
import requests
import urllib3
from bs4 import BeautifulSoup

urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)

PLATFORM = "landwirt.com"
BASE = "https://www.landwirt.com/kleinanzeigen/realitaeten-immobilien"

CATEGORIES = [
    "bauernhoefe",
    "landhaeuser",
    "schloesser-herrenhhaeuser",
    "reiterhof",
    "weingueter",
]

HEADERS = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36",
    "Accept-Language": "de-AT,de;q=0.9",
}


def geocode(ort: str) -> tuple[float | None, float | None]:
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


def scrape_category(cat: str, max_pages: int = 10) -> list[dict]:
    results = []
    for page in range(1, max_pages + 1):
        url = f"{BASE}/{cat}/land-oesterreich" + (f"?page={page}" if page > 1 else "")
        try:
            r = requests.get(url, headers=HEADERS, timeout=15, verify=False)
            if r.status_code == 404:
                break
            soup = BeautifulSoup(r.text, "html.parser")

            # Listings erkennen — landwirt.com nutzt article oder li Tags
            items = (
                soup.select("article.listing, li.listing, div.ad-item, div[class*='listing']")
                or soup.select("a[href*='/kleinanzeigen/']")
            )
            if not items:
                break

            for item in items:
                a = item.find("a") if item.name != "a" else item
                href = a.get("href", "") if a else ""
                if not href:
                    continue
                if not href.startswith("http"):
                    href = "https://www.landwirt.com" + href
                text = item.get_text(" ", strip=True)

                # PLZ + Ort extrahieren
                plz_match = re.search(r"\b(\d{4})\s+([A-Za-zÄÖÜäöü\-\s]{3,30})", text)
                ort = plz_match.group(0).strip() if plz_match else ""
                lat, lon = geocode(ort) if ort else (None, None)

                price_match = re.search(r"([\d\.,]+)\s*€|€\s*([\d\.,]+)", text)
                price = (price_match.group(1) or price_match.group(2)) if price_match else None

                size_match = re.search(r"([\d\.,]+)\s*m[²2]", text)
                size = size_match.group(1) if size_match else None

                title_el = item.find(["h2", "h3", "h4", "strong"])
                title = title_el.get_text(strip=True) if title_el else text[:100]

                results.append({
                    "name": title[:150],
                    "price_eur": price,
                    "size_m2": size,
                    "plot_size_m2": None,
                    "rooms": None,
                    "location": ort,
                    "postcode": plz_match.group(1) if plz_match else "",
                    "lat": lat,
                    "lon": lon,
                    "url": href,
                    "platform": PLATFORM,
                    "property_type": cat,
                    "description": text[:300],
                })
                time.sleep(0.3)  # Nominatim Rate-Limit
            time.sleep(1)
        except Exception as e:
            print(f"  [landwirt] Fehler '{cat}' Seite {page}: {e}")
            break
    return results


def scrape() -> list[dict]:
    all_results = []
    seen_urls = set()
    for cat in CATEGORIES:
        print(f"  landwirt.com: '{cat}' ...")
        hits = scrape_category(cat)
        new = [h for h in hits if h["url"] not in seen_urls]
        seen_urls.update(h["url"] for h in new)
        all_results.extend(new)
        print(f"    -> {len(hits)} Treffer, {len(new)} neu ({len(all_results)} gesamt)")
    return all_results
