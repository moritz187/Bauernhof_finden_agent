"""
Scraper für willhaben.at

Liest Suchergebnisse aus dem __NEXT_DATA__ JSON das willhaben
direkt in die HTML-Seite einbettet. Keine inoffizielle API nötig.

Felder:
  COORDINATES              → lat,lon
  ESTATE_SIZE/LIVING_AREA  → Wohnfläche m²
  FREE_AREA/FREE_AREA_AREA_TOTAL → Freifläche/Garten m²
  PRICE_FOR_DISPLAY        → Preis als String
  SEO_URL                  → saubere URL zum Inserat
"""

import time
import re
import json
import requests
import urllib3
from bs4 import BeautifulSoup

urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)

PLATFORM = "willhaben.at"
BASE_URL = "https://www.willhaben.at/iad/immobilien/haus-kaufen/haus-angebote"

KEYWORDS = [
    "Bauernhaus", "Bauernhof", "Landhaus", "Landgut",
    "Gehöft", "Schloss", "Reiterhof", "Weingut",
]

HEADERS = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36",
    "Accept-Language": "de-AT,de;q=0.9",
}


def parse_attrs(ad: dict) -> dict:
    return {a["name"]: a.get("values", []) for a in ad.get("attributes", {}).get("attribute", [])}


def extract_float(values: list) -> float | None:
    if not values:
        return None
    try:
        return float(str(values[0]).replace(".", "").replace(",", ".").strip())
    except (ValueError, TypeError):
        return None


def scrape_keyword(keyword: str, max_pages: int = 10) -> list[dict]:
    results = []
    for page in range(1, max_pages + 1):
        params = {"keyword": keyword, "page": page}
        try:
            r = requests.get(BASE_URL, params=params, headers=HEADERS, timeout=15, verify=False)
            if r.status_code != 200:
                break
            soup = BeautifulSoup(r.text, "html.parser")
            nd = soup.find("script", id="__NEXT_DATA__")
            if not nd:
                break
            data = json.loads(nd.string)
            sr = data["props"]["pageProps"]["searchResult"]
            ads = sr.get("advertSummaryList", {}).get("advertSummary", [])
            if not ads:
                break
            for ad in ads:
                attrs = parse_attrs(ad)
                coords = attrs.get("COORDINATES", [""])[0].split(",")
                lat = float(coords[0]) if len(coords) == 2 else None
                lon = float(coords[1]) if len(coords) == 2 else None
                seo = attrs.get("SEO_URL", [""])[0]
                if seo and not seo.startswith("/"):
                    seo = "/" + seo
                url = f"https://www.willhaben.at/iad{seo}" if seo else f"https://www.willhaben.at/iad/{ad.get('id','')}"
                price_raw = attrs.get("PRICE_FOR_DISPLAY", [None])[0]
                results.append({
                    "name": attrs.get("HEADING", [ad.get("description", "")])[0][:150],
                    "price_eur": price_raw,
                    "size_m2": extract_float(attrs.get("ESTATE_SIZE/LIVING_AREA")),
                    "plot_size_m2": None,  # willhaben liefert nur Freifläche, nicht Grundstücksgröße
                    "free_area_m2": extract_float(attrs.get("FREE_AREA/FREE_AREA_AREA_TOTAL")),
                    "rooms": extract_float(attrs.get("NUMBER_OF_ROOMS")),
                    "location": attrs.get("LOCATION", [""])[0],
                    "postcode": attrs.get("POSTCODE", [""])[0],
                    "lat": lat,
                    "lon": lon,
                    "url": url,
                    "platform": PLATFORM,
                    "property_type": keyword,
                    "description": ad.get("description", "")[:300],
                })
            # Letzte Seite erreicht?
            if page * 30 >= sr.get("rowsFound", 0):
                break
            time.sleep(0.7)
        except Exception as e:
            print(f"  [willhaben] Fehler '{keyword}' Seite {page}: {e}")
            break
    return results


def scrape() -> list[dict]:
    all_results = []
    seen_urls = set()
    for kw in KEYWORDS:
        print(f"  willhaben.at: '{kw}' ...")
        hits = scrape_keyword(kw)
        new = [h for h in hits if h["url"] not in seen_urls]
        seen_urls.update(h["url"] for h in new)
        all_results.extend(new)
        print(f"    -> {len(hits)} Treffer, {len(new)} neu ({len(all_results)} gesamt)")
    return all_results
