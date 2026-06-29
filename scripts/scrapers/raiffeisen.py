"""
Scraper für raiffeisen-immobilien.at

Raiffeisen ist Österreichs größtes regionales Maklernetzwerk mit ~300 Maklern
und besonders starker Präsenz in ländlichen Regionen (NÖ, OÖ, Stmk).

Seitenstruktur:
  Suchliste: /de/immobilien?page=N&transactionType=BUY&estateType=FARMHOUSE
  Karte:     /de/immobilien/kauf/{plz}/{ort}/{slug}.{id}
  Listing:   <a href="..."><h4>Titel</h4><p>PLZ Ort</p><p>Wohnfläche: X m²</p><p>Kaufpreis: X €</p></a>
"""

import re
import time
import requests
import urllib3
from urllib.parse import unquote
from bs4 import BeautifulSoup

urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)

PLATFORM = "raiffeisen-immobilien.at"
BASE = "https://www.raiffeisen-immobilien.at"
SEARCH = BASE + "/de/immobilien"

# Alle relevanten Objekttypen
ESTATE_TYPES = [
    "FARMHOUSE",       # Bauernhof
    "COUNTRY_HOUSE",   # Landhaus
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
        return float(clean)
    except ValueError:
        return None


def scrape_type(estate_type: str) -> list[dict]:
    results = []
    seen = set()
    page = 1

    while True:
        params = {
            "page": page,
            "transactionType": "BUY",
            "estateType": estate_type,
        }
        try:
            r = requests.get(SEARCH, params=params, headers=HEADERS, timeout=15, verify=False)
            if r.status_code != 200:
                break
            soup = BeautifulSoup(r.text, "lxml")

            # Listings sind <a> Tags die auf Detailseiten zeigen
            cards = soup.find_all("a", href=re.compile(r"/de/immobilien/kauf/"))
            if not cards:
                break

            new_on_page = 0
            for card in cards:
                href = card.get("href", "")
                url = BASE + href.split("?")[0]  # ohne Query-Parameter
                if url in seen:
                    continue
                seen.add(url)
                new_on_page += 1

                # Titel aus h4
                title_el = card.find(["h4", "h3", "h2"])
                title = title_el.get_text(strip=True) if title_el else ""

                # Alle <p> Tags im Card
                paras = [p.get_text(strip=True) for p in card.find_all("p")]

                location = ""
                size_m2 = None
                plot_size_m2 = None
                price_str = None

                for para in paras:
                    if re.match(r"^\d{4}\s", para):  # PLZ + Ort
                        location = para
                    elif "Wohnfläche" in para or "Nutzfläche" in para:
                        size_m2 = _parse_num(para)
                    elif "Grundfläche" in para or "Grundstück" in para:
                        plot_size_m2 = _parse_num(para)
                    elif "Kaufpreis" in para or "€" in para:
                        price_str = para.replace("Kaufpreis:", "").strip()

                # PLZ + Ort aus URL extrahieren (doppelt URL-decodieren wegen %2520)
                if not location:
                    m = re.search(r"/kauf/(\d{4})/([^/?]+)/", href)
                    if m:
                        plz = m.group(1)
                        ort = unquote(unquote(m.group(2))).replace("-", " ").title()
                        location = f"{plz} {ort}"

                # Titel aus URL-Slug als Fallback
                if not title:
                    slug_m = re.search(r"/kauf/\d{4}/[^/]+/([^./]+)\.", href)
                    if slug_m:
                        title = unquote(unquote(slug_m.group(1))).replace("-", " ").replace("%20", " ").title()

                lat, lon = None, None
                if location:
                    lat, lon = geocode(location)

                results.append({
                    "name": title[:150],
                    "price_eur": price_str,
                    "size_m2": size_m2,
                    "plot_size_m2": plot_size_m2,
                    "rooms": None,
                    "location": location,
                    "postcode": location[:4] if location else None,
                    "lat": lat,
                    "lon": lon,
                    "url": url,
                    "platform": PLATFORM,
                    "property_type": estate_type.replace("_", " ").title(),
                    "description": "",
                })

            if new_on_page == 0:
                break

            # Prüfen ob weitere Seiten vorhanden
            next_link = soup.find("a", string=re.compile(r"Weiter|Next|»|›"))
            if not next_link:
                # Kein "Weiter" Button → letzte Seite
                # Zusätzlich: prüfen ob page-Parameter in pagination vorhanden
                pag = soup.find_all("a", href=re.compile(r"page=\d+"))
                max_page = page
                for pl in pag:
                    m = re.search(r"page=(\d+)", pl.get("href", ""))
                    if m:
                        max_page = max(max_page, int(m.group(1)))
                if page >= max_page:
                    break

            page += 1
            time.sleep(0.8)

        except Exception as e:
            print(f"  [raiffeisen] Fehler {estate_type} Seite {page}: {e}")
            break

    return results


def scrape() -> list[dict]:
    all_results = []
    seen_urls = set()

    for et in ESTATE_TYPES:
        print(f"  raiffeisen-immobilien.at: {et} ...")
        hits = scrape_type(et)
        new = [h for h in hits if h["url"] not in seen_urls]
        seen_urls.update(h["url"] for h in new)
        all_results.extend(new)
        print(f"    -> {len(hits)} Treffer, {len(new)} neu ({len(all_results)} gesamt)")
        time.sleep(1)

    return all_results
