"""Horcrux OSINT · Phone number intelligence (offline).

Fornisce:
  - Country detection da prefisso internazionale (+39, +33, ...)
  - IT mobile operator detection da prefisso (storico, pre-MNP)
  - IT landline city detection
  - Variants utili per password (last 4, last 6, full senza prefisso)

NOTA: dato Mobile Number Portability (MNP), il prefisso non è più affidabile
al 100% per identificare l'operatore. È utile come "operatore originale"
e come pattern OSINT — comune in vecchi DB e wordlist.
"""

import re

# ── Country codes (ISO + nome paese) ────────────────────────────────────────
COUNTRY_CODES: dict[str, dict[str, str]] = {
    "1":   {"iso": "US/CA", "country": "USA/Canada"},
    "20":  {"iso": "EG", "country": "Egitto"},
    "27":  {"iso": "ZA", "country": "Sudafrica"},
    "30":  {"iso": "GR", "country": "Grecia"},
    "31":  {"iso": "NL", "country": "Olanda"},
    "32":  {"iso": "BE", "country": "Belgio"},
    "33":  {"iso": "FR", "country": "Francia"},
    "34":  {"iso": "ES", "country": "Spagna"},
    "36":  {"iso": "HU", "country": "Ungheria"},
    "39":  {"iso": "IT", "country": "Italia"},
    "40":  {"iso": "RO", "country": "Romania"},
    "41":  {"iso": "CH", "country": "Svizzera"},
    "43":  {"iso": "AT", "country": "Austria"},
    "44":  {"iso": "GB", "country": "Regno Unito"},
    "45":  {"iso": "DK", "country": "Danimarca"},
    "46":  {"iso": "SE", "country": "Svezia"},
    "47":  {"iso": "NO", "country": "Norvegia"},
    "48":  {"iso": "PL", "country": "Polonia"},
    "49":  {"iso": "DE", "country": "Germania"},
    "51":  {"iso": "PE", "country": "Perù"},
    "52":  {"iso": "MX", "country": "Messico"},
    "53":  {"iso": "CU", "country": "Cuba"},
    "54":  {"iso": "AR", "country": "Argentina"},
    "55":  {"iso": "BR", "country": "Brasile"},
    "56":  {"iso": "CL", "country": "Cile"},
    "57":  {"iso": "CO", "country": "Colombia"},
    "58":  {"iso": "VE", "country": "Venezuela"},
    "60":  {"iso": "MY", "country": "Malesia"},
    "61":  {"iso": "AU", "country": "Australia"},
    "62":  {"iso": "ID", "country": "Indonesia"},
    "63":  {"iso": "PH", "country": "Filippine"},
    "64":  {"iso": "NZ", "country": "Nuova Zelanda"},
    "65":  {"iso": "SG", "country": "Singapore"},
    "66":  {"iso": "TH", "country": "Thailandia"},
    "81":  {"iso": "JP", "country": "Giappone"},
    "82":  {"iso": "KR", "country": "Corea del Sud"},
    "84":  {"iso": "VN", "country": "Vietnam"},
    "86":  {"iso": "CN", "country": "Cina"},
    "90":  {"iso": "TR", "country": "Turchia"},
    "91":  {"iso": "IN", "country": "India"},
    "92":  {"iso": "PK", "country": "Pakistan"},
    "93":  {"iso": "AF", "country": "Afghanistan"},
    "94":  {"iso": "LK", "country": "Sri Lanka"},
    "95":  {"iso": "MM", "country": "Myanmar"},
    "98":  {"iso": "IR", "country": "Iran"},
    "212": {"iso": "MA", "country": "Marocco"},
    "213": {"iso": "DZ", "country": "Algeria"},
    "216": {"iso": "TN", "country": "Tunisia"},
    "218": {"iso": "LY", "country": "Libia"},
    "234": {"iso": "NG", "country": "Nigeria"},
    "351": {"iso": "PT", "country": "Portogallo"},
    "352": {"iso": "LU", "country": "Lussemburgo"},
    "353": {"iso": "IE", "country": "Irlanda"},
    "354": {"iso": "IS", "country": "Islanda"},
    "355": {"iso": "AL", "country": "Albania"},
    "356": {"iso": "MT", "country": "Malta"},
    "357": {"iso": "CY", "country": "Cipro"},
    "358": {"iso": "FI", "country": "Finlandia"},
    "359": {"iso": "BG", "country": "Bulgaria"},
    "370": {"iso": "LT", "country": "Lituania"},
    "371": {"iso": "LV", "country": "Lettonia"},
    "372": {"iso": "EE", "country": "Estonia"},
    "373": {"iso": "MD", "country": "Moldavia"},
    "374": {"iso": "AM", "country": "Armenia"},
    "375": {"iso": "BY", "country": "Bielorussia"},
    "376": {"iso": "AD", "country": "Andorra"},
    "377": {"iso": "MC", "country": "Monaco"},
    "378": {"iso": "SM", "country": "San Marino"},
    "380": {"iso": "UA", "country": "Ucraina"},
    "381": {"iso": "RS", "country": "Serbia"},
    "382": {"iso": "ME", "country": "Montenegro"},
    "385": {"iso": "HR", "country": "Croazia"},
    "386": {"iso": "SI", "country": "Slovenia"},
    "387": {"iso": "BA", "country": "Bosnia"},
    "389": {"iso": "MK", "country": "Macedonia del Nord"},
    "420": {"iso": "CZ", "country": "Repubblica Ceca"},
    "421": {"iso": "SK", "country": "Slovacchia"},
    "423": {"iso": "LI", "country": "Liechtenstein"},
    "972": {"iso": "IL", "country": "Israele"},
    "971": {"iso": "AE", "country": "Emirati Arabi"},
    "966": {"iso": "SA", "country": "Arabia Saudita"},
}

# ── Operatori italiani mobile (prefisso storico) ────────────────────────────
# Mappa il primo gruppo di 3 cifre dopo il "3" → operatore originale.
# Esempio: 333 → TIM, 320 → Wind, 380 → 3 (H3G).
IT_MOBILE_OPERATORS: dict[str, str] = {
    # 320-329 → Wind (poi WindTre)
    "320": "Wind", "321": "Wind", "322": "Wind", "323": "Wind",
    "324": "Wind", "325": "Wind", "326": "Wind", "327": "Wind",
    "328": "Wind", "329": "Wind",
    # 330-339 → TIM
    "330": "TIM", "331": "TIM", "332": "TIM", "333": "TIM",
    "334": "TIM", "335": "TIM", "336": "TIM", "337": "TIM",
    "338": "TIM", "339": "TIM",
    # 340-349 → vari (Wind/TIM/Vodafone misti)
    "340": "TIM", "341": "Vodafone", "342": "Wind",
    "343": "Vodafone", "344": "Wind", "345": "Wind",
    "346": "Vodafone", "347": "TIM", "348": "TIM", "349": "TIM",
    # 350-359
    "350": "Iliad", "351": "Iliad", "352": "Iliad",
    "353": "TIM", "354": "TIM", "355": "TIM",
    "356": "TIM", "357": "TIM", "358": "TIM", "359": "TIM",
    # 360-369 → Vodafone
    "360": "Vodafone", "361": "Vodafone", "362": "Vodafone",
    "363": "Vodafone", "364": "Vodafone", "365": "Vodafone",
    "366": "Vodafone", "367": "Vodafone", "368": "Vodafone",
    "369": "Vodafone",
    # 370-379 → vari
    "370": "PosteMobile", "371": "PosteMobile",
    "373": "TIM", "375": "Iliad",
    "377": "PosteMobile",
    # 380-389 → 3 / WindTre
    "380": "3", "381": "3", "382": "3", "383": "3",
    "384": "3", "385": "3", "386": "3", "387": "3",
    "388": "3", "389": "3",
    # 390-399 → vari/Coop/PosteMobile
    "390": "PosteMobile", "391": "PosteMobile", "392": "Vodafone",
    "393": "Vodafone", "397": "PosteMobile",
}

# ── Prefissi rete fissa IT → città/area ────────────────────────────────────
IT_LANDLINE_PREFIXES: dict[str, str] = {
    "010": "Genova", "011": "Torino", "015": "Biella", "0125": "Ivrea",
    "0131": "Alessandria", "0141": "Asti", "0142": "Casale Monferrato",
    "015": "Biella",
    "02": "Milano",
    "030": "Brescia", "031": "Como", "035": "Bergamo", "0341": "Lecco",
    "0342": "Sondrio", "0376": "Mantova", "0382": "Pavia",
    "041": "Venezia", "0421": "San Donà di Piave", "045": "Verona",
    "0444": "Vicenza", "049": "Padova",
    "050": "Pisa", "051": "Bologna", "055": "Firenze",
    "059": "Modena", "0532": "Ferrara", "0541": "Rimini",
    "0521": "Parma", "0522": "Reggio Emilia", "0571": "Empoli",
    "059": "Modena", "0577": "Siena", "0583": "Lucca", "0586": "Livorno",
    "06": "Roma",
    "070": "Cagliari", "071": "Ancona", "0721": "Pesaro", "075": "Perugia",
    "0742": "Foligno", "0744": "Terni", "079": "Sassari",
    "080": "Bari", "081": "Napoli", "0823": "Caserta", "0825": "Avellino",
    "0824": "Benevento", "0828": "Battipaglia", "0832": "Lecce",
    "0835": "Matera", "0865": "Isernia", "0871": "Chieti",
    "0883": "Andria", "0884": "Manfredonia", "085": "Pescara",
    "089": "Salerno", "090": "Messina", "091": "Palermo",
    "095": "Catania", "0961": "Catanzaro", "0965": "Reggio Calabria",
    "0971": "Potenza", "0985": "Cosenza Tirreno", "0975": "Sala Consilina",
    "099": "Taranto",
}


def _clean_phone(raw: str) -> str:
    """Strip whitespace, dots, dashes, parentheses."""
    return re.sub(r"[\s.\-()]+", "", raw)


def enrich_phone(raw: str) -> dict:
    """Restituisce metadata su un numero di telefono.

    Returns:
        {
            "raw": "+39 333 1234567",
            "clean": "393331234567",
            "country_code": "39",
            "country": "Italia",
            "iso": "IT",
            "type": "mobile" | "landline" | "unknown",
            "operator": "TIM" | None,
            "area": "Roma" | None,
            "national": "3331234567",
            "last4": "4567",
            "last6": "234567",
            "last8": "31234567",
        }
    """
    clean = _clean_phone(raw)
    out = {
        "raw": raw,
        "clean": clean,
        "country_code": None,
        "country": None,
        "iso": None,
        "type": "unknown",
        "operator": None,
        "area": None,
        "national": clean,
        "last4": clean[-4:] if len(clean) >= 4 else None,
        "last6": clean[-6:] if len(clean) >= 6 else None,
        "last8": clean[-8:] if len(clean) >= 8 else None,
    }

    # Strip leading 00 (alternative international prefix)
    if clean.startswith("00"):
        clean = clean[2:]
    # Strip leading +
    if clean.startswith("+"):
        clean = clean[1:]

    # Detect country code (try 3, then 2, then 1 digits)
    country_code = None
    national = clean
    for length in (3, 2, 1):
        prefix = clean[:length]
        if prefix in COUNTRY_CODES:
            country_code = prefix
            national = clean[length:]
            break

    # Italy without explicit +39 → assume IT if starts with 3 (mobile) or 0 (landline)
    if country_code is None:
        if clean.startswith(("3", "0")) and 9 <= len(clean) <= 11:
            country_code = "39"
            national = clean

    if country_code:
        info = COUNTRY_CODES.get(country_code)
        out["country_code"] = country_code
        if info:
            out["country"] = info["country"]
            out["iso"] = info["iso"]
        out["national"] = national

    # If Italy, classify mobile/landline + operator/area
    if country_code == "39":
        if national.startswith("3") and len(national) >= 9:
            # Mobile
            out["type"] = "mobile"
            prefix3 = national[:3]
            out["operator"] = IT_MOBILE_OPERATORS.get(prefix3)
        elif national.startswith("0"):
            # Landline
            out["type"] = "landline"
            # Try 4-digit prefix first, then 3, then 2
            for plen in (4, 3, 2):
                prefix = national[:plen]
                if prefix in IT_LANDLINE_PREFIXES:
                    out["area"] = IT_LANDLINE_PREFIXES[prefix]
                    break

    # Update last-N from cleaned national (more useful for password patterns)
    if len(national) >= 4:
        out["last4"] = national[-4:]
    if len(national) >= 6:
        out["last6"] = national[-6:]
    if len(national) >= 8:
        out["last8"] = national[-8:]

    return out


def password_tokens_from_phone(phone: str) -> list[str]:
    """Estrai tokens utili per password da un numero di telefono."""
    info = enrich_phone(phone)
    tokens = []
    if info["last4"]:
        tokens.append(info["last4"])
    if info["last6"]:
        tokens.append(info["last6"])
    if info["last8"]:
        tokens.append(info["last8"])
    if info["national"] and info["national"] != info["clean"]:
        tokens.append(info["national"])
    if info["operator"]:
        tokens.append(info["operator"].lower())
    if info["area"]:
        tokens.append(info["area"].lower())
    return list(dict.fromkeys(tokens))  # dedupe preserve order
