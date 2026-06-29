"""
Scraper für immowelt.at

~167 Bauernhäuser AT, ~40 NÖ, ~22 OÖ, ~15 Burgen/Schlösser.
Stabile URL-Struktur: /suche/kaufen/haus/{typ}/{bundesland}/{region-code}

Seitenstruktur:
  Listings als <article> oder <div> mit data-testid Attributen
  Titel in <h2> oder <strong>
  Preis, Größe, Ort als Text-Elemente
  Pagination via ?sp={seite} oder URL-Pfad
"""

import re
import time
import requests
import urllib3
from bs4 import BeautifulSoup

urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)

PLATFORM = "immowelt.at"
BASE = "https://www.immowelt.at"

SEARCH_URLS = [
    "/suche/kaufen/haus/bauernhaus/osterreich/ad02at1",
    "/suche/kaufen/haus/bauernhaus/niederosterreich/ad04at3",
    "/suche/kaufen/haus/bauernhaus/oberoesterreich/ad04at4",
    "/suche/kaufen/haus/bauernhaus/steiermark/ad04at6",
    "/suche/oesterreich/haeuser/kaufen/burg-schloss",
    "/suche/oesterreich/landwirtschaft-forstwirtschaft/mk/bauernhof",
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


def scrape_url(path: str) -> list[dict]:
    results = []
    seen = set()
    page = 1

    # property_type aus URL ableiten
    if "burg-schloss" in path:
        ptype = "Burg/Schloss"
    elif "bauernhaus" in path:
        ptype = "Bauernhaus"
    elif "bauernhof" in path:
        ptype = "Bauernhof"
    else:
        ptype = "Landwirtschaft"

    while True:
        url = BASE + path
        if page > 1:
            # immowelt nutzt ?sp=N für Pagination
            sep = "&" if "?" in path else "?"
            url = BASE + path + f"{sep}sp={page}"

        try:
            r = requests.get(url, headers=HEADERS, timeout=15, verify=False)
            if r.status_code != 200:
                break
            soup = BeautifulSoup(r.text, "lxml")

            # Listings: article oder div mit Link auf /expose/
            articles = soup.find_all(["article", "div"], attrs={"data-testid": re.compile(r"listitem|result|expose")})
            if not articles:
                # Fallback: alle Links die auf /expose/ zeigen
                expose_links = soup.find_all("a", href=re.compile(r"/expose/"))
                articles = list({a.find_parent(["article", "li", "div"]) for a in expose_links if a.find_parent(["article", "li", "div"])})

            if not articles:
                break

            new_on_page = 0
            for art in articles:
                link = art.find("a", href=re.compile(r"/expose/"))
                if not link:
                    continue
                href = link.get("href", "")
                full_url = BASE + href if href.startswith("/") else href
                if full_url in seen:
                    continue
                seen.add(full_url)
                new_on_page += 1

                text = art.get_text(" ", strip=True)

                # Titel
                title_el = art.find(["h2", "h3", "strong", "span"], class_=re.compile(r"title|heading|name", re.I))
                if not title_el:
                    title_el = art.find(["h2", "h3"])
                title = title_el.get_text(strip=True) if title_el else text[:80]

                # Preis
                price_str = None
                price_m = re.search(r"€\s*([\d.,]+)\s*(?:,-)?", text)
                if price_m:
                    price_str = "€ " + price_m.group(1)

                # Größe m²
                size_m2 = None
                size_m = re.search(r"([\d.,]+)\s*m²\s*(?:Wohnfläche|Nutzfläche|Wohn|$)", text)
                if size_m:
                    size_m2 = _parse_num(size_m.group(1))

                # Grundstück
                plot_m2 = None
                plot_m = re.search(r"([\d.,]+)\s*m²\s*Grundfläche", text)
                if plot_m:
                    plot_m2 = _parse_num(plot_m.group(1))

                # Ort — PLZ + Ortsname
                location = ""
                loc_m = re.search(r"(\d{4}\s+[A-ZÄÖÜa-zäöüß][^\d,€\n]{2,30}?)(?:\s*,|\s*\||\s*·|\s+\d|$)", text)
                if loc_m:
                    location = loc_m.group(1).strip()

                lat, lon = None, None
                if location:
                    lat, lon = geocode(location)

                results.append({
                    "name": title[:150],
                    "price_eur": price_str,
                    "size_m2": size_m2,
                    "plot_size_m2": plot_m2,
                    "rooms": None,
                    "location": location,
                    "postcode": location[:4] if location and location[:4].isdigit() else None,
                    "lat": lat,
                    "lon": lon,
                    "url": full_url,
                    "platform": PLATFORM,
                    "property_type": ptype,
                    "description": "",
                })

            if new_on_page == 0:
                break

            # Nächste Seite?
            next_btn = soup.find("a", attrs={"aria-label": re.compile(r"nächste|next|weiter", re.I)})
            if not next_btn:
                next_btn = soup.find("a", string=re.compile(r"»|›|Weiter|Next", re.I))
            if not next_btn:
                break

            page += 1
            time.sleep(0.8)

        except Exception as e:
            print(f"  [immowelt] Fehler {path} Seite {page}: {e}")
            break

    return results


def scrape() -> list[dict]:
    all_results = []
    seen_urls = set()

    for path in SEARCH_URLS:
        label = path.split("/")[-2] + "/" + path.split("/")[-1]
        print(f"  immowelt.at: {label} ...")
        hits = scrape_url(path)
        new = [h for h in hits if h["url"] not in seen_urls]
        seen_urls.update(h["url"] for h in new)
        all_results.extend(new)
        print(f"    -> {len(hits)} Treffer, {len(new)} neu ({len(all_results)} gesamt)")
        time.sleep(1)

    return all_results
