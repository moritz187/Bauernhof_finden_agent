"""
Scraper für hofnachfolge.at — österreichische Plattform für Hofübergaben.

Strategie:
  Kleinere, spezialisierte Plattform mit einfachem HTML-Aufbau.
  Listet aktiv angebotene Höfe zur Übergabe/zum Verkauf auf.
  Koordinaten werden via PLZ/Ort geocodiert.

Besonderheit:
  Angebote hier sind oft nicht öffentlich inseriert — kann einzigartige
  Objekte enthalten die auf willhaben/immoscout nicht auftauchen.
"""

import time
import re
import requests
import urllib3
from bs4 import BeautifulSoup

urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)

PLATFORM = "hofnachfolge.at"
BASE_URL = "https://www.hofnachfolge.at"
SEARCH_URL = f"{BASE_URL}/betriebe"

HEADERS = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36",
    "Accept-Language": "de-AT,de;q=0.9",
}


def geocode_ort(ort: str) -> tuple[float | None, float | None]:
    try:
        r = requests.get(
            "https://nominatim.openstreetmap.org/search",
            params={"q": ort + ", Österreich", "format": "json", "limit": 1},
            headers={"User-Agent": "BauernhofFinder/1.0"},
            timeout=10,
            verify=False,
        )
        data = r.json()
        if data:
            return float(data[0]["lat"]), float(data[0]["lon"])
    except Exception:
        pass
    return None, None


def scrape(max_pages: int = 10) -> list[dict]:
    results = []
    seen_urls = set()
    print(f"  hofnachfolge.at: suche Hofübergaben ...")
    for page in range(1, max_pages + 1):
        url = SEARCH_URL + (f"?page={page}" if page > 1 else "")
        try:
            r = requests.get(url, headers=HEADERS, timeout=15, verify=False)
            if r.status_code != 200:
                break
            soup = BeautifulSoup(r.text, "html.parser")
            # Listings — verschiedene mögliche Strukturen
            items = (
                soup.select("div.betrieb, article.betrieb, div.listing, div[class*='offer']")
                or soup.select("a[href*='/betrieb/'], a[href*='/inserat/']")
            )
            if not items:
                break
            for item in items:
                link = item.get("href", "") or (item.select_one("a") or {}).get("href", "")
                if link and not link.startswith("http"):
                    link = BASE_URL + link
                if link in seen_urls:
                    continue
                seen_urls.add(link)
                text = item.get_text(" ", strip=True)
                ort_match = re.search(r"\d{4}\s+[A-Za-zÄÖÜäöü\s]+", text)
                ort = ort_match.group(0).strip() if ort_match else ""
                lat, lon = (geocode_ort(ort) if ort else (None, None))
                price_match = re.search(r"[\d\.,]+\s*€", text)
                results.append({
                    "name": text[:150],
                    "price_eur": price_match.group(0) if price_match else None,
                    "size_m2": None,
                    "lat": lat,
                    "lon": lon,
                    "url": link,
                    "platform": PLATFORM,
                    "property_type": "Hofübergabe",
                    "description": text[:300],
                })
            time.sleep(1)
        except Exception as e:
            print(f"  [hofnachfolge] Fehler Seite {page}: {e}")
            break
    print(f"    -> {len(results)} Treffer")
    return results
