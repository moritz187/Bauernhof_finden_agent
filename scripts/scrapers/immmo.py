"""
Scraper für immmo.at

immmo.at ist ein österreichischer Aggregator mit regionalem Fokus auf NÖ/OÖ,
besonders stark im Mostviertel. Aggregiert u.a. von ImmobilienScout24,
aber mit eigenen Kategorie-URLs die gezielt nach Vierkanthof/Mostviertel filtern.

Seitenstruktur:
  URL: /immo/{kategorie}/{region}/{seite}
  Listing: <h3><a href="extern-url">Titel</a></h3> + Text mit Preis/Größe/Ort
  Preis: "€ 295.000,-"
  Größe: "3263 Ort / 250m² / 6 Zimmer"
"""

import re
import time
import requests
import urllib3
from bs4 import BeautifulSoup

urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)

PLATFORM = "immmo.at"
BASE = "https://www.immmo.at"

# Kategorie-URLs — gezielte Suche nach Bauernhöfen/Vierkanthöfen
CATEGORIES = [
    "/immo/Bauernhaus-kaufen/Niederoesterreich",
    "/immo/Bauernhaus-kaufen/Oberoesterreich",
    "/immo/Bauernhaus-kaufen/Steiermark",
    "/vierkanthof-kaufen",
    "/bauernhof-mostviertel-kaufen",
    "/bauernhoefe-im-mostviertel",
]

HEADERS = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36",
    "Accept-Language": "de-AT,de;q=0.9",
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


def _parse_price(text: str) -> str | None:
    m = re.search(r"€\s*([\d.,]+)", text)
    if m:
        return "€ " + m.group(1)
    return None


def _parse_size(text: str) -> float | None:
    m = re.search(r"([\d.]+)\s*m²", text)
    if m:
        try:
            return float(m.group(1).replace(".", "").replace(",", "."))
        except ValueError:
            pass
    return None


def _parse_location(text: str) -> str:
    # Format: "3263 Perwarth / 250m² / ..." → "3263 Perwarth"
    m = re.search(r"(\d{4}\s+[A-ZÄÖÜa-zäöüß][A-ZÄÖÜa-zäöüß\s\-]+?)(?:\s*/|\s+\d+\s*m²|$)", text)
    if m:
        return m.group(1).strip()
    return ""


def scrape_category(path: str) -> list[dict]:
    results = []
    seen = set()
    page = 1

    while True:
        url = BASE + path
        if page > 1:
            url = url.rstrip("/") + f"/{page}"

        try:
            r = requests.get(url, headers=HEADERS, timeout=15, verify=False)
            if r.status_code != 200:
                break
            soup = BeautifulSoup(r.text, "lxml")

            # Listings: h3 mit Link
            headings = soup.find_all(["h2", "h3"], string=False)
            links_found = []
            for h in headings:
                a = h.find("a", href=True)
                if a and ("immobilienscout24" in a["href"] or "willhaben" in a["href"]
                          or "immmo.at" in a["href"] or a["href"].startswith("http")):
                    links_found.append((h, a))

            # Fallback: direkt alle Links die auf Inserate zeigen
            if not links_found:
                for a in soup.find_all("a", href=re.compile(r"(immobilienscout24|immmo\.at/expose|willhaben)")):
                    links_found.append((a, a))

            if not links_found:
                break

            new_on_page = 0
            for container, a_tag in links_found:
                ext_url = a_tag.get("href", "")
                if not ext_url or ext_url in seen:
                    continue
                seen.add(ext_url)
                new_on_page += 1

                title = a_tag.get_text(strip=True) or container.get_text(strip=True)

                # Umliegender Text für Preis/Größe/Ort
                parent = container.find_parent(["li", "div", "article"]) or container
                block_text = parent.get_text(" ", strip=True)

                price_str = _parse_price(block_text)
                size_m2 = _parse_size(block_text)
                location = _parse_location(block_text)

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
                    "postcode": location[:4] if location else None,
                    "lat": lat,
                    "lon": lon,
                    "url": ext_url,
                    "platform": PLATFORM,
                    "property_type": "Bauernhaus",
                    "description": "",
                })

            if new_on_page == 0:
                break

            # Nächste Seite prüfen
            next_a = soup.find("a", string=re.compile(r"Weiter|Next|»|›|\d+"))
            pag_links = soup.find_all("a", href=re.compile(rf"{re.escape(path)}/\d+"))
            if not pag_links and not next_a:
                break

            page += 1
            time.sleep(0.7)

        except Exception as e:
            print(f"  [immmo] Fehler {path} Seite {page}: {e}")
            break

    return results


def scrape() -> list[dict]:
    all_results = []
    seen_urls = set()

    for cat in CATEGORIES:
        print(f"  immmo.at: {cat} ...")
        hits = scrape_category(cat)
        new = [h for h in hits if h["url"] not in seen_urls]
        seen_urls.update(h["url"] for h in new)
        all_results.extend(new)
        print(f"    -> {len(hits)} Treffer, {len(new)} neu ({len(all_results)} gesamt)")
        time.sleep(1)

    return all_results
