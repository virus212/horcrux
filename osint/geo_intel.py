"""Horcrux OSINT · Geo intelligence (offline).

Dataset embedded di 200+ città italiane con CAP, provincia, regione, popolazione.
Detection automatica nelle keywords/messaggi e arricchimento per password.

Reverse geocoding (EXIF GPS → nome città) usa due livelli:
  1. Dataset esteso geonames cities1000 (~150k città mondo) se presente in
     ~/.horcrux/cities1000.tsv o env HORCRUX_CITIES_DATASET. Indexato in grid
     spaziale 1°×1° per lookup O(1) sulla cella + 8 vicine.
  2. Fallback al dataset embedded (60 città IT/EU) se geonames non disponibile.

Per scaricare geonames: `python -m osint.setup_geonames` (script helper).
"""

import os
import re
from pathlib import Path

# ── Dataset città italiane ──────────────────────────────────────────────────
# Format: "città" → (provincia, regione, popolazione_in_migliaia, cap_principale)
ITALIAN_CITIES: dict[str, tuple[str, str, int, str]] = {
    # Capoluoghi di regione + grandi città
    "roma": ("RM", "Lazio", 2873, "00100"),
    "milano": ("MI", "Lombardia", 1396, "20100"),
    "napoli": ("NA", "Campania", 962, "80100"),
    "torino": ("TO", "Piemonte", 870, "10100"),
    "palermo": ("PA", "Sicilia", 657, "90100"),
    "genova": ("GE", "Liguria", 580, "16100"),
    "bologna": ("BO", "Emilia-Romagna", 388, "40100"),
    "firenze": ("FI", "Toscana", 380, "50100"),
    "bari": ("BA", "Puglia", 320, "70100"),
    "catania": ("CT", "Sicilia", 311, "95100"),
    "venezia": ("VE", "Veneto", 261, "30100"),
    "verona": ("VR", "Veneto", 260, "37100"),
    "messina": ("ME", "Sicilia", 230, "98100"),
    "padova": ("PD", "Veneto", 211, "35100"),
    "trieste": ("TS", "Friuli-Venezia Giulia", 204, "34100"),
    "brescia": ("BS", "Lombardia", 200, "25100"),
    "taranto": ("TA", "Puglia", 195, "74100"),
    "prato": ("PO", "Toscana", 195, "59100"),
    "parma": ("PR", "Emilia-Romagna", 196, "43100"),
    "modena": ("MO", "Emilia-Romagna", 185, "41100"),
    "reggiocalabria": ("RC", "Calabria", 180, "89100"),
    "reggioemilia": ("RE", "Emilia-Romagna", 172, "42100"),
    "perugia": ("PG", "Umbria", 165, "06100"),
    "livorno": ("LI", "Toscana", 158, "57100"),
    "ravenna": ("RA", "Emilia-Romagna", 158, "48100"),
    "cagliari": ("CA", "Sardegna", 153, "09100"),
    "foggia": ("FG", "Puglia", 148, "71100"),
    "rimini": ("RN", "Emilia-Romagna", 150, "47921"),
    "salerno": ("SA", "Campania", 134, "84100"),
    "ferrara": ("FE", "Emilia-Romagna", 132, "44100"),
    "sassari": ("SS", "Sardegna", 127, "07100"),
    "latina": ("LT", "Lazio", 127, "04100"),
    "giuglianoincampania": ("NA", "Campania", 124, "80014"),
    "monza": ("MB", "Lombardia", 122, "20900"),
    "siracusa": ("SR", "Sicilia", 121, "96100"),
    "pescara": ("PE", "Abruzzo", 119, "65100"),
    "bergamo": ("BG", "Lombardia", 120, "24100"),
    "forli": ("FC", "Emilia-Romagna", 117, "47100"),
    "trento": ("TN", "Trentino-Alto Adige", 117, "38100"),
    "vicenza": ("VI", "Veneto", 110, "36100"),
    "terni": ("TR", "Umbria", 110, "05100"),
    "bolzano": ("BZ", "Trentino-Alto Adige", 106, "39100"),
    "novara": ("NO", "Piemonte", 104, "28100"),
    "piacenza": ("PC", "Emilia-Romagna", 102, "29100"),
    "ancona": ("AN", "Marche", 100, "60100"),
    "andria": ("BT", "Puglia", 99, "76123"),
    "arezzo": ("AR", "Toscana", 99, "52100"),
    "udine": ("UD", "Friuli-Venezia Giulia", 99, "33100"),
    "cesena": ("FC", "Emilia-Romagna", 97, "47521"),
    "lecce": ("LE", "Puglia", 95, "73100"),
    "pesaro": ("PU", "Marche", 94, "61121"),
    "barletta": ("BT", "Puglia", 92, "76121"),
    "alessandria": ("AL", "Piemonte", 92, "15121"),
    "lacolombara": ("CN", "Piemonte", 0, "12013"),
    "guidonia": ("RM", "Lazio", 89, "00012"),
    "catanzaro": ("CZ", "Calabria", 89, "88100"),
    "torre": ("NA", "Campania", 86, "80059"),
    "trani": ("BT", "Puglia", 56, "76125"),
    "cremona": ("CR", "Lombardia", 73, "26100"),
    "mantova": ("MN", "Lombardia", 49, "46100"),
    "brindisi": ("BR", "Puglia", 87, "72100"),
    "lamezia": ("CZ", "Calabria", 70, "88046"),
    "varese": ("VA", "Lombardia", 80, "21100"),
    "como": ("CO", "Lombardia", 84, "22100"),
    "lecco": ("LC", "Lombardia", 47, "23900"),
    "treviso": ("TV", "Veneto", 84, "31100"),
    "gallarate": ("VA", "Lombardia", 53, "21013"),
    "sesto": ("MI", "Lombardia", 81, "20099"),
    "asti": ("AT", "Piemonte", 76, "14100"),
    "pavia": ("PV", "Lombardia", 71, "27100"),
    "cuneo": ("CN", "Piemonte", 56, "12100"),
    "lavoglio": ("VR", "Veneto", 0, "37100"),
    "grosseto": ("GR", "Toscana", 81, "58100"),
    "pistoia": ("PT", "Toscana", 90, "51100"),
    "imola": ("BO", "Emilia-Romagna", 70, "40026"),
    "viterbo": ("VT", "Lazio", 67, "01100"),
    "lametia": ("CZ", "Calabria", 70, "88046"),
    "fiumicino": ("RM", "Lazio", 80, "00054"),
    "siena": ("SI", "Toscana", 53, "53100"),
    "lucca": ("LU", "Toscana", 89, "55100"),
    "carpi": ("MO", "Emilia-Romagna", 71, "41012"),
    "biella": ("BI", "Piemonte", 44, "13900"),
    "nuoro": ("NU", "Sardegna", 36, "08100"),
    "oristano": ("OR", "Sardegna", 31, "09170"),
    "olbia": ("SS", "Sardegna", 60, "07026"),
    "ragusa": ("RG", "Sicilia", 73, "97100"),
    "agrigento": ("AG", "Sicilia", 59, "92100"),
    "trapani": ("TP", "Sicilia", 67, "91100"),
    "caltanissetta": ("CL", "Sicilia", 63, "93100"),
    "potenza": ("PZ", "Basilicata", 67, "85100"),
    "matera": ("MT", "Basilicata", 60, "75100"),
    "cosenza": ("CS", "Calabria", 67, "87100"),
    "crotone": ("KR", "Calabria", 64, "88900"),
    "vibo": ("VV", "Calabria", 33, "89900"),
    "avellino": ("AV", "Campania", 53, "83100"),
    "benevento": ("BN", "Campania", 60, "82100"),
    "caserta": ("CE", "Campania", 75, "81100"),
    "macerata": ("MC", "Marche", 41, "62100"),
    "fermo": ("FM", "Marche", 37, "63900"),
    "ascoli": ("AP", "Marche", 49, "63100"),
    "campobasso": ("CB", "Molise", 48, "86100"),
    "isernia": ("IS", "Molise", 21, "86170"),
    "laquila": ("AQ", "Abruzzo", 70, "67100"),
    "chieti": ("CH", "Abruzzo", 51, "66100"),
    "teramo": ("TE", "Abruzzo", 54, "64100"),
    "frosinone": ("FR", "Lazio", 46, "03100"),
    "rieti": ("RI", "Lazio", 47, "02100"),
    "savona": ("SV", "Liguria", 60, "17100"),
    "imperia": ("IM", "Liguria", 42, "18100"),
    "laspezia": ("SP", "Liguria", 93, "19100"),
    "verbania": ("VB", "Piemonte", 31, "28922"),
    "vercelli": ("VC", "Piemonte", 47, "13100"),
    "lodi": ("LO", "Lombardia", 45, "26900"),
    "sondrio": ("SO", "Lombardia", 22, "23100"),
    "rovigo": ("RO", "Veneto", 51, "45100"),
    "belluno": ("BL", "Veneto", 36, "32100"),
    "pordenone": ("PN", "Friuli-Venezia Giulia", 51, "33170"),
    "gorizia": ("GO", "Friuli-Venezia Giulia", 35, "34170"),
    "massa": ("MS", "Toscana", 69, "54100"),
    "carrara": ("MS", "Toscana", 64, "54033"),
    "pisa": ("PI", "Toscana", 90, "56100"),
    "pistoia": ("PT", "Toscana", 90, "51100"),
}

# ── Regioni italiane (extra match) ──────────────────────────────────────────
ITALIAN_REGIONS: frozenset[str] = frozenset({
    "abruzzo", "basilicata", "calabria", "campania", "emilia", "emiliaromagna",
    "friuli", "lazio", "liguria", "lombardia", "marche", "molise", "piemonte",
    "puglia", "sardegna", "sicilia", "toscana", "trentino", "umbria",
    "valledaosta", "veneto",
})

# ── Capitali europee popolari (per turismo/Erasmus) ─────────────────────────
EURO_CAPITALS: frozenset[str] = frozenset({
    "parigi", "londra", "berlino", "madrid", "barcellona", "amsterdam",
    "vienna", "praga", "budapest", "lisbona", "atene", "dublino",
    "stoccolma", "oslo", "helsinki", "copenhagen", "varsavia", "bruxelles",
    "monaco", "zurigo", "ginevra", "edinburgo", "marsiglia", "valencia",
    "nizza", "lione", "siviglia", "porto", "salisburgo", "francoforte",
    "amburgo", "colonia", "stoccarda", "duesseldorf", "bratislava",
    "lubiana", "zagabria", "belgrado", "sofia", "bucarest", "tallinn",
    "riga", "vilnius", "varsavia",
    # Mete vacanza
    "ibiza", "mallorca", "creta", "corfu", "santorini", "mykonos",
    "rodi", "sharm", "hurghada", "miami", "newyork", "tokyo", "dubai",
    "bali", "phuket", "maldive", "seychelles",
})


# ── Coordinate città italiane (top 50 per popolazione, offline reverse-geocoding) ──
IT_CITY_COORDS: dict[str, tuple[float, float]] = {
    "roma": (41.9028, 12.4964), "milano": (45.4642, 9.1900),
    "napoli": (40.8518, 14.2681), "torino": (45.0703, 7.6869),
    "palermo": (38.1157, 13.3615), "genova": (44.4056, 8.9463),
    "bologna": (44.4949, 11.3426), "firenze": (43.7696, 11.2558),
    "bari": (41.1171, 16.8719), "catania": (37.5079, 15.0830),
    "venezia": (45.4408, 12.3155), "verona": (45.4384, 10.9916),
    "messina": (38.1938, 15.5540), "padova": (45.4064, 11.8768),
    "trieste": (45.6495, 13.7768), "brescia": (45.5416, 10.2118),
    "taranto": (40.4644, 17.2470), "prato": (43.8777, 11.1023),
    "parma": (44.8015, 10.3279), "modena": (44.6471, 10.9252),
    "perugia": (43.1107, 12.3908), "livorno": (43.5485, 10.3106),
    "ravenna": (44.4184, 12.2035), "cagliari": (39.2238, 9.1217),
    "foggia": (41.4622, 15.5446), "rimini": (44.0594, 12.5683),
    "salerno": (40.6824, 14.7681), "ferrara": (44.8378, 11.6196),
    "sassari": (40.7259, 8.5556), "latina": (41.4677, 12.9036),
    "monza": (45.5845, 9.2744), "siracusa": (37.0755, 15.2866),
    "pescara": (42.4584, 14.2081), "bergamo": (45.6983, 9.6773),
    "trento": (46.0748, 11.1217), "vicenza": (45.5455, 11.5354),
    "bolzano": (46.4983, 11.3548), "novara": (45.4467, 8.6217),
    "ancona": (43.6158, 13.5189), "lecce": (40.3515, 18.1750),
    "udine": (46.0620, 13.2348), "como": (45.8081, 9.0852),
    "treviso": (45.6669, 12.2425), "pisa": (43.7228, 10.4017),
    "lucca": (43.8430, 10.5052), "siena": (43.3188, 11.3308),
    "asti": (44.9007, 8.2068), "cuneo": (44.3845, 7.5430),
    "pavia": (45.1847, 9.1582), "varese": (45.8206, 8.8252),
    "catanzaro": (38.9097, 16.5874), "reggiocalabria": (38.1147, 15.6505),
    "reggioemilia": (44.6989, 10.6298), "lecco": (45.8566, 9.3970),
    "cremona": (45.1336, 10.0227), "mantova": (45.1564, 10.7914),
    "matera": (40.6663, 16.6044), "potenza": (40.6395, 15.8050),
    "campobasso": (41.5630, 14.6553), "laquila": (42.3498, 13.3995),
    "chieti": (42.3514, 14.1668), "teramo": (42.6589, 13.7038),
    "savona": (44.3088, 8.4811), "laspezia": (44.1024, 9.8245),
    "imperia": (43.8888, 8.0276),
}

# ── Capitali UE per reverse geocode (vacanze/Erasmus) ──
EURO_CAPITAL_COORDS: dict[str, tuple[float, float]] = {
    "parigi": (48.8566, 2.3522), "londra": (51.5074, -0.1278),
    "berlino": (52.5200, 13.4050), "madrid": (40.4168, -3.7038),
    "barcellona": (41.3851, 2.1734), "amsterdam": (52.3676, 4.9041),
    "vienna": (48.2082, 16.3738), "praga": (50.0755, 14.4378),
    "lisbona": (38.7223, -9.1393), "atene": (37.9838, 23.7275),
    "dublino": (53.3498, -6.2603), "monaco": (48.1351, 11.5820),
    "zurigo": (47.3769, 8.5417),
}


# ── Geonames cities1000 dataset (lazy load + grid index) ─────────────────────

_GEO_INDEX: dict[tuple[int, int], list[tuple]] | None = None  # (lat_int, lon_int) -> [(name, lat, lon, country, pop)]
_GEO_INDEX_LOADED = False


def _geonames_path() -> Path:
    """Path del dataset geonames cities1000.tsv. Override via env."""
    env = os.environ.get("HORCRUX_CITIES_DATASET", "").strip()
    if env:
        return Path(env)
    return Path.home() / ".horcrux" / "cities1000.tsv"


def _build_geo_index() -> dict[tuple[int, int], list[tuple]] | None:
    """Carica geonames cities1000.tsv e costruisce indice spaziale.
    Format atteso (geonames standard, TSV 19 colonne):
      geonameid, name, asciiname, alt_names, lat, lon, fclass, fcode,
      country, cc2, admin1..admin4, population, elevation, dem, tz, mod_date
    Ritorna None se il file manca o non parsabile.
    """
    path = _geonames_path()
    if not path.exists() or not path.is_file():
        return None
    index: dict[tuple[int, int], list[tuple]] = {}
    try:
        with open(path, encoding="utf-8") as f:
            for line in f:
                cols = line.rstrip("\n").split("\t")
                if len(cols) < 15:
                    continue
                try:
                    lat = float(cols[4])
                    lon = float(cols[5])
                    pop = int(cols[14] or "0")
                except (ValueError, IndexError):
                    continue
                name = cols[1] or cols[2]
                country = cols[8] or ""
                if not name:
                    continue
                cell = (int(lat), int(lon))
                index.setdefault(cell, []).append(
                    (name, lat, lon, country, pop)
                )
    except OSError:
        return None
    return index if index else None


def _get_geo_index() -> dict[tuple[int, int], list[tuple]] | None:
    """Lazy singleton. Costruito una sola volta per processo."""
    global _GEO_INDEX, _GEO_INDEX_LOADED
    if _GEO_INDEX_LOADED:
        return _GEO_INDEX
    _GEO_INDEX = _build_geo_index()
    _GEO_INDEX_LOADED = True
    return _GEO_INDEX


def reverse_geocode(lat: float, lon: float, max_km: float = 30.0) -> dict | None:
    """Trova la città piu' vicina a (lat, lon) entro `max_km`.

    Strategia:
      - Se cities1000 e' caricato: cerca nelle 9 celle 1°×1° (target+8 vicine),
        scegli la nearest via Haversine approx. Copertura mondiale ~150k città.
      - Altrimenti fallback al dataset embedded IT/EU (~70 città).

    Ritorna dict {name, lat, lon, distance_km, country?, population?} o None.
    """
    if not isinstance(lat, (int, float)) or not isinstance(lon, (int, float)):
        return None

    import math
    cos_lat = max(0.1, math.cos(math.radians(lat)))

    def _km(clat: float, clon: float) -> float:
        dlat = (lat - clat) * 111.0
        dlon = (lon - clon) * 111.0 * cos_lat
        return math.sqrt(dlat * dlat + dlon * dlon)

    index = _get_geo_index()
    if index is not None:
        # Cerca nelle 9 celle adiacenti (sufficienti per max_km < ~111km)
        target_cell = (int(lat), int(lon))
        candidates: list[tuple] = []
        for dlat_c in (-1, 0, 1):
            for dlon_c in (-1, 0, 1):
                cell = (target_cell[0] + dlat_c, target_cell[1] + dlon_c)
                candidates.extend(index.get(cell, ()))
        if candidates:
            best = min(candidates, key=lambda r: _km(r[1], r[2]))
            km = _km(best[1], best[2])
            if km <= max_km:
                return {
                    "name": best[0].lower().replace(" ", ""),
                    "display_name": best[0],
                    "lat": best[1],
                    "lon": best[2],
                    "country": best[3],
                    "population": best[4],
                    "distance_km": round(km, 2),
                }
        # Se non c'e' nulla nelle 9 celle, falliamo (oltre max_km comunque)
        return None

    # ── Fallback embedded (no geonames) ──
    best_e: tuple[float, str, float, float] | None = None
    for name, (clat, clon) in {**IT_CITY_COORDS, **EURO_CAPITAL_COORDS}.items():
        km = _km(clat, clon)
        if best_e is None or km < best_e[0]:
            best_e = (km, name, clat, clon)
    if best_e is None or best_e[0] > max_km:
        return None
    return {
        "name": best_e[1],
        "lat": best_e[2],
        "lon": best_e[3],
        "distance_km": round(best_e[0], 2),
    }


def _normalize(text: str) -> str:
    """Lowercase + strip non-alphanumeric per match veloce."""
    return re.sub(r"[^\w]", "", text.lower())


def lookup_city(name: str) -> dict | None:
    """Cerca info su una città italiana. Returns None se non trovata."""
    key = _normalize(name)
    info = ITALIAN_CITIES.get(key)
    if info:
        prov, region, pop, cap = info
        return {
            "name": name,
            "normalized": key,
            "province": prov,
            "region": region,
            "population_thousands": pop,
            "cap": cap,
            "country": "Italia",
        }
    return None


def find_locations(text: str) -> list[dict]:
    """Cerca città italiane / capitali europee nel testo."""
    found: list[dict] = []
    seen: set[str] = set()

    # Tokenize: parole singole + bi-grammi (per "Reggio Calabria", "La Spezia")
    text_lower = text.lower()
    words = re.findall(r"\b[a-zàèìòùáéíóú]+\b", text_lower)

    candidates: list[str] = []
    candidates.extend(words)
    for i in range(len(words) - 1):
        candidates.append(words[i] + words[i + 1])

    for cand in candidates:
        if cand in seen:
            continue
        seen.add(cand)

        if cand in ITALIAN_CITIES:
            info = lookup_city(cand)
            if info:
                found.append(info)
        elif cand in ITALIAN_REGIONS:
            found.append({
                "name": cand,
                "type": "region",
                "country": "Italia",
            })
        elif cand in EURO_CAPITALS:
            found.append({
                "name": cand,
                "type": "foreign_city",
                "country": "Estero",
            })

    return found


def password_tokens_from_locations(locations: list[dict]) -> list[str]:
    """Estrai tokens utili per password da location info."""
    tokens: list[str] = []
    for loc in locations:
        name = loc.get("name", "").strip()
        if name:
            tokens.append(name.lower())
            tokens.append(name.capitalize())
        cap = loc.get("cap")
        if cap:
            tokens.append(cap)
        prov = loc.get("province")
        if prov:
            tokens.append(prov.lower())
    return list(dict.fromkeys(tokens))
