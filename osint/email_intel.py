"""Horcrux OSINT · Email intelligence (offline).

Estrae email dai messaggi e arricchisce con:
  - Provider detection (Gmail, Libero, Hotmail, ...)
  - Pattern del local part (nome.cognome, nome_anno, nomeanno, ...)
  - Tokens utili per wordlist (username, dominio, parts)
"""

import re

EMAIL_RE = re.compile(
    r"\b[a-zA-Z0-9._%+\-]+@[a-zA-Z0-9.\-]+\.[a-zA-Z]{2,}\b"
)

# ── Provider mapping ────────────────────────────────────────────────────────
EMAIL_PROVIDERS: dict[str, str] = {
    # Italian
    "libero.it": "Libero", "alice.it": "Alice/TIM", "tim.it": "TIM",
    "tin.it": "TIM", "virgilio.it": "Virgilio", "tiscali.it": "Tiscali",
    "tiscali.com": "Tiscali", "fastwebnet.it": "Fastweb",
    "vodafone.it": "Vodafone", "wind.it": "WindTre", "windtre.it": "WindTre",
    "iliad.it": "Iliad", "poste.it": "Poste", "postemail.it": "Poste",
    "katamail.com": "Katamail", "inwind.it": "Wind",
    # International
    "gmail.com": "Gmail", "googlemail.com": "Gmail",
    "yahoo.com": "Yahoo", "yahoo.it": "Yahoo IT", "ymail.com": "Yahoo",
    "hotmail.com": "Hotmail", "hotmail.it": "Hotmail IT",
    "outlook.com": "Outlook", "outlook.it": "Outlook IT",
    "live.com": "Live", "msn.com": "MSN",
    "icloud.com": "iCloud", "me.com": "iCloud", "mac.com": "iCloud",
    "aol.com": "AOL", "aol.it": "AOL IT",
    "protonmail.com": "ProtonMail", "proton.me": "ProtonMail",
    "tutanota.com": "Tutanota", "fastmail.com": "Fastmail",
    "gmx.com": "GMX", "gmx.it": "GMX IT",
    "zoho.com": "Zoho", "yandex.com": "Yandex",
}

# ── Pattern detection ───────────────────────────────────────────────────────
PATTERN_NOME_COGNOME = re.compile(r"^([a-z]+)[._-]([a-z]+)$")
PATTERN_NOME_ANNO = re.compile(r"^([a-z]+)[._-]?(\d{2,4})$")
PATTERN_INITIAL_COGNOME = re.compile(r"^([a-z])[._-]?([a-z]{3,})$")
PATTERN_NOMECOGNOME_NUM = re.compile(r"^([a-z]+)(\d+)$")


def extract_emails(text: str) -> list[str]:
    """Estrai tutte le email dal testo."""
    return list(set(EMAIL_RE.findall(text)))


def enrich_email(email: str) -> dict:
    """Restituisce metadata su una singola email.

    Returns:
        {
            "email": "marco.rossi@gmail.com",
            "local": "marco.rossi",
            "domain": "gmail.com",
            "tld": "com",
            "provider": "Gmail",
            "pattern": "nome.cognome",
            "parts": ["marco", "rossi"],
            "year": "1990" | None,
            "tokens_for_password": ["marco", "rossi", ...],
        }
    """
    if "@" not in email:
        return {"email": email, "error": "invalid"}

    local, _, domain = email.lower().rpartition("@")
    parts = re.split(r"[._\-]", local)
    parts = [p for p in parts if p]

    out = {
        "email": email,
        "local": local,
        "domain": domain,
        "tld": domain.rsplit(".", 1)[1] if "." in domain else "",
        "provider": EMAIL_PROVIDERS.get(domain, "Sconosciuto"),
        "parts": parts,
        "pattern": "unknown",
        "year": None,
        "tokens_for_password": [],
    }

    tokens = []

    # Pattern detection
    m1 = PATTERN_NOME_COGNOME.match(local)
    m2 = PATTERN_NOME_ANNO.match(local)
    m3 = PATTERN_INITIAL_COGNOME.match(local)
    m4 = PATTERN_NOMECOGNOME_NUM.match(local)

    if m1:
        out["pattern"] = "nome.cognome"
        nome, cognome = m1.group(1), m1.group(2)
        tokens.extend([nome, cognome, nome.capitalize(), cognome.capitalize()])
    elif m4:
        nome_or_full, num = m4.group(1), m4.group(2)
        if len(num) in (2, 4) and num.isdigit():
            out["pattern"] = "nome+anno"
            out["year"] = num
            tokens.extend([nome_or_full, nome_or_full.capitalize(), num])
    elif m2:
        nome, num = m2.group(1), m2.group(2)
        if len(num) in (2, 4) and num.isdigit():
            out["pattern"] = "nome.anno"
            out["year"] = num
            tokens.extend([nome, nome.capitalize(), num])
    elif m3:
        out["pattern"] = "iniziale.cognome"
        cognome = m3.group(2)
        tokens.extend([cognome, cognome.capitalize()])
    else:
        # Generic: tokenize parts
        for p in parts:
            if len(p) >= 3 and p.isalpha():
                tokens.extend([p, p.capitalize()])
            elif p.isdigit() and len(p) in (2, 4):
                tokens.append(p)
                if not out["year"]:
                    out["year"] = p
        if not out["pattern"] or out["pattern"] == "unknown":
            out["pattern"] = "generic"

    # Domain part (sometimes useful: e.g. "company" emails)
    if domain not in EMAIL_PROVIDERS:
        domain_root = domain.split(".")[0]
        if len(domain_root) >= 4 and domain_root.isalpha():
            tokens.append(domain_root)
            tokens.append(domain_root.capitalize())

    # Dedupe preserve order
    seen = set()
    out["tokens_for_password"] = [
        t for t in tokens if not (t.lower() in seen or seen.add(t.lower()))
    ]
    return out


def enrich_emails(text: str) -> list[dict]:
    """Estrai tutte le email dal testo + arricchisci ognuna."""
    return [enrich_email(e) for e in extract_emails(text)]


def password_tokens_from_emails(emails_or_texts: list[str]) -> list[str]:
    """Combine token from multiple emails."""
    all_tokens: list[str] = []
    for item in emails_or_texts:
        if "@" in item:
            info = enrich_email(item)
            all_tokens.extend(info.get("tokens_for_password", []))
        else:
            for email in extract_emails(item):
                info = enrich_email(email)
                all_tokens.extend(info.get("tokens_for_password", []))
    seen: set[str] = set()
    return [t for t in all_tokens if not (t.lower() in seen or seen.add(t.lower()))]
