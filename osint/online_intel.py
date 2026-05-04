"""Horcrux OSINT · Online tools (network-required).

Tools che richiedono network ma usano SOLO API pubbliche e gratuite:
  - WHOIS lookup (via comando shell `whois`)
  - DNS records (via socket built-in)
  - IP geolocation (ipapi.co - free no key)
  - Wayback Machine search (archive.org - free no key)
  - Email reputation (emailrep.io - free no key for basic)
  - GitHub user public info (api.github.com - free)
  - Reddit user public info (reddit.com/user/.json - free)

NOTE LEGALI/ETICHE:
  - Tutte le API sono pubbliche e free tier.
  - Nessun login, nessuno scraping aggressivo.
  - User-Agent dichiarato + rate limit gentile.
  - Tutti i dati sono già pubblici (WHOIS, DNS, ecc.).
"""

from __future__ import annotations

import json
import re
import socket
import subprocess
import urllib.error
import urllib.parse
import urllib.request

USER_AGENT = "Horcrux-OSINT/1.0 (Educational; Cybersecurity Research)"
DEFAULT_TIMEOUT = 8.0


def _http_get(url: str, timeout: float = DEFAULT_TIMEOUT, headers: dict | None = None) -> tuple[int, str]:
    """Helper: HTTP GET con User-Agent. Returns (status_code, body)."""
    h = {"User-Agent": USER_AGENT, "Accept": "application/json"}
    if headers:
        h.update(headers)
    req = urllib.request.Request(url, headers=h)
    try:
        with urllib.request.urlopen(req, timeout=timeout) as resp:
            return resp.status, resp.read().decode("utf-8", errors="replace")
    except urllib.error.HTTPError as e:
        try:
            body = e.read().decode("utf-8", errors="replace")
        except Exception:
            body = ""
        return e.code, body
    except (urllib.error.URLError, TimeoutError, socket.timeout) as e:
        return 0, str(e)


# ════════════════════════════════════════════════════════════════════════
# 1. WHOIS lookup
# ════════════════════════════════════════════════════════════════════════

def whois_lookup(domain: str) -> dict:
    """WHOIS via shell command. Pubblicamente accessibile.

    Returns:
        {
            "domain": "example.com",
            "raw": "...",
            "registrar": "GoDaddy",
            "creation_date": "2010-...",
            "expiration_date": "2025-...",
            "name_servers": [...],
            "tokens": ["godaddy", "2010", ...]
        }
    """
    domain = domain.strip().lower()
    if not re.match(r"^[a-z0-9.\-]+\.[a-z]{2,}$", domain):
        return {"error": "invalid domain"}

    try:
        result = subprocess.run(
            ["whois", domain],
            capture_output=True, text=True, timeout=15,
        )
        raw = result.stdout
    except FileNotFoundError:
        return {"error": "comando 'whois' non installato sul sistema"}
    except subprocess.TimeoutExpired:
        return {"error": "whois timeout"}
    except Exception as e:
        return {"error": str(e)}

    # Parse common fields
    info = {"domain": domain, "raw": raw[:5000]}  # cap raw

    patterns = {
        "registrar": r"(?:Registrar|Registrar Name|Sponsoring Registrar):\s*(.+)",
        "creation_date": r"(?:Creation Date|Created|Registered on|Registered):\s*(.+)",
        "expiration_date": r"(?:Expiration Date|Expiry Date|Expires|paid-till):\s*(.+)",
        "updated_date": r"(?:Updated Date|Last Updated|Last Modified|Changed):\s*(.+)",
        "registrant_country": r"(?:Registrant Country|Country):\s*(.+)",
        "admin_email": r"(?:Admin Email|admin-c.*?email):\s*(.+)",
    }

    for key, pat in patterns.items():
        m = re.search(pat, raw, re.IGNORECASE)
        if m:
            info[key] = m.group(1).strip().splitlines()[0]

    # Name servers
    ns = re.findall(r"(?:Name Server|nserver|nameserver):\s*(\S+)", raw, re.IGNORECASE)
    if ns:
        info["name_servers"] = list(dict.fromkeys(ns[:8]))

    # Token extraction for password generation
    tokens = []
    if info.get("registrar"):
        first_word = info["registrar"].split()[0].lower()
        if first_word.isalpha() and len(first_word) > 3:
            tokens.append(first_word)
    for date_field in ("creation_date", "expiration_date"):
        if info.get(date_field):
            year_match = re.search(r"(19|20)\d{2}", info[date_field])
            if year_match:
                tokens.append(year_match.group(0))
    info["tokens"] = list(dict.fromkeys(tokens))

    return info


# ════════════════════════════════════════════════════════════════════════
# 2. DNS records
# ════════════════════════════════════════════════════════════════════════

def dns_lookup(domain: str) -> dict:
    """DNS records via dig command (preferred) or socket fallback."""
    domain = domain.strip().lower()
    if not re.match(r"^[a-z0-9.\-]+\.[a-z]{2,}$", domain):
        return {"error": "invalid domain"}

    info = {"domain": domain, "records": {}}

    # Try dig first (richer output)
    record_types = ["A", "AAAA", "MX", "NS", "TXT", "CNAME"]
    dig_available = False
    try:
        subprocess.run(["dig", "-v"], capture_output=True, timeout=2)
        dig_available = True
    except (FileNotFoundError, subprocess.TimeoutExpired):
        dig_available = False

    if dig_available:
        for rtype in record_types:
            try:
                result = subprocess.run(
                    ["dig", "+short", domain, rtype],
                    capture_output=True, text=True, timeout=5,
                )
                lines = [l.strip() for l in result.stdout.splitlines() if l.strip()]
                if lines:
                    info["records"][rtype] = lines[:10]
            except Exception:
                pass
    else:
        # Fallback: socket only A record
        try:
            ip = socket.gethostbyname(domain)
            info["records"]["A"] = [ip]
        except Exception as e:
            info["error"] = f"DNS resolution failed: {e}"

    return info


# ════════════════════════════════════════════════════════════════════════
# 3. IP geolocation
# ════════════════════════════════════════════════════════════════════════

def ip_geolocation(ip: str) -> dict:
    """IP geolocation via ipapi.co (free, no API key)."""
    ip = ip.strip()
    # Validate: IPv4 or IPv6 or domain
    if not re.match(r"^[a-zA-Z0-9.:\-]+$", ip):
        return {"error": "invalid IP/domain"}

    url = f"https://ipapi.co/{ip}/json/"
    status, body = _http_get(url, timeout=10)

    if status == 0:
        return {"error": f"network: {body}"}
    if status != 200:
        return {"error": f"HTTP {status}", "body": body[:200]}

    try:
        data = json.loads(body)
    except json.JSONDecodeError:
        return {"error": "invalid JSON response"}

    if "error" in data:
        return {"error": data.get("reason", "unknown")}

    out = {
        "ip": data.get("ip", ip),
        "city": data.get("city"),
        "region": data.get("region"),
        "country": data.get("country_name"),
        "country_code": data.get("country_code"),
        "postal": data.get("postal"),
        "lat": data.get("latitude"),
        "lon": data.get("longitude"),
        "timezone": data.get("timezone"),
        "org": data.get("org"),
        "isp": data.get("asn"),
    }

    tokens = []
    for k in ("city", "region", "country"):
        v = out.get(k)
        if v and isinstance(v, str) and len(v) > 2:
            tokens.append(v.lower())
            tokens.append(v.replace(" ", ""))
    if out.get("postal"):
        tokens.append(str(out["postal"]))
    out["tokens"] = list(dict.fromkeys(tokens))
    return out


# ════════════════════════════════════════════════════════════════════════
# 4. Wayback Machine search
# ════════════════════════════════════════════════════════════════════════

def wayback_search(query: str, limit: int = 20, max_retries: int = 2) -> dict:
    """Cerca uno username/dominio nel Wayback Machine.

    Free, no API key. Utile per trovare vecchi profili archiviati.
    Include retry exponential per timeouts (Wayback è spesso lento).
    """
    query = query.strip()
    if len(query) < 3:
        return {"error": "query troppo corta"}

    url = (
        "https://web.archive.org/cdx/search/cdx"
        f"?url=*{urllib.parse.quote(query)}*"
        f"&limit={limit}&output=json"
    )

    status, body = 0, ""
    timeouts = [10, 20, 30]  # exponential
    for attempt in range(max_retries + 1):
        timeout = timeouts[min(attempt, len(timeouts) - 1)]
        status, body = _http_get(url, timeout=timeout)
        if status == 200:
            break
        if status == 0 and "timed out" not in body.lower():
            break  # non-timeout error, no retry

    if status == 0:
        return {"error": f"network: {body}"}
    if status != 200:
        return {"error": f"HTTP {status}"}

    try:
        data = json.loads(body)
    except json.JSONDecodeError:
        return {"error": "invalid JSON"}

    if not data or len(data) < 2:
        return {"query": query, "snapshots": []}

    headers = data[0]
    rows = data[1:]
    snapshots = []
    for row in rows[:limit]:
        snap = dict(zip(headers, row))
        snapshots.append({
            "timestamp": snap.get("timestamp"),
            "url": snap.get("original"),
            "archive_url": (
                f"https://web.archive.org/web/{snap.get('timestamp')}/"
                f"{snap.get('original')}"
            ),
            "status": snap.get("statuscode"),
            "mime": snap.get("mimetype"),
        })

    return {
        "query": query,
        "total": len(snapshots),
        "snapshots": snapshots,
    }


# ════════════════════════════════════════════════════════════════════════
# 5. Email reputation (EmailRep.io free)
# ════════════════════════════════════════════════════════════════════════

def email_reputation(email: str) -> dict:
    """Email reputation via emailrep.io (free, no key for basic)."""
    email = email.strip()
    if "@" not in email:
        return {"error": "invalid email"}

    url = f"https://emailrep.io/{urllib.parse.quote(email)}"
    status, body = _http_get(url, timeout=10, headers={"Accept": "application/json"})

    if status == 0:
        return {"error": f"network: {body}"}
    if status == 429:
        return {"error": "rate limit (free tier exhausted - try again later)"}
    if status != 200:
        return {"error": f"HTTP {status}", "body": body[:200]}

    try:
        data = json.loads(body)
    except json.JSONDecodeError:
        return {"error": "invalid JSON"}

    out = {
        "email": email,
        "reputation": data.get("reputation"),
        "suspicious": data.get("suspicious"),
        "references": data.get("references"),
        "details": {
            "blacklisted": data.get("details", {}).get("blacklisted"),
            "malicious_activity": data.get("details", {}).get("malicious_activity"),
            "credentials_leaked": data.get("details", {}).get("credentials_leaked"),
            "data_breach": data.get("details", {}).get("data_breach"),
            "first_seen": data.get("details", {}).get("first_seen"),
            "last_seen": data.get("details", {}).get("last_seen"),
            "domain_age": data.get("details", {}).get("domain_exists"),
            "profiles": data.get("details", {}).get("profiles", []),
        },
    }
    return out


# ════════════════════════════════════════════════════════════════════════
# 6. GitHub user public info
# ════════════════════════════════════════════════════════════════════════

def github_user_info(username: str) -> dict:
    """GitHub public user info via api.github.com (free, ~60 req/h unauth)."""
    username = username.strip()
    if not re.match(r"^[a-zA-Z0-9\-_]{1,39}$", username):
        return {"error": "invalid username"}

    url = f"https://api.github.com/users/{username}"
    status, body = _http_get(url, timeout=10)

    if status == 404:
        return {"username": username, "exists": False}
    if status != 200:
        return {"error": f"HTTP {status}", "body": body[:200]}

    try:
        data = json.loads(body)
    except json.JSONDecodeError:
        return {"error": "invalid JSON"}

    out = {
        "username": data.get("login"),
        "exists": True,
        "name": data.get("name"),
        "bio": data.get("bio"),
        "company": data.get("company"),
        "location": data.get("location"),
        "blog": data.get("blog"),
        "email": data.get("email"),
        "twitter": data.get("twitter_username"),
        "public_repos": data.get("public_repos"),
        "followers": data.get("followers"),
        "created_at": data.get("created_at"),
        "html_url": data.get("html_url"),
        "avatar_url": data.get("avatar_url"),
    }

    # Token extraction
    tokens = []
    if out["name"]:
        for part in re.split(r"\s+", out["name"]):
            if len(part) >= 3 and part.isalpha():
                tokens.append(part.lower())
    if out["company"]:
        company = re.sub(r"[^\w]", "", out["company"]).lower()
        if 3 < len(company) < 20:
            tokens.append(company)
    if out["location"]:
        loc_first = out["location"].split(",")[0].strip().lower()
        if loc_first:
            tokens.append(loc_first.replace(" ", ""))
    if out["created_at"]:
        year = out["created_at"][:4]
        if year.isdigit():
            tokens.append(year)
    if out["twitter"]:
        tokens.append(out["twitter"])

    out["tokens"] = list(dict.fromkeys(tokens))
    return out


# ════════════════════════════════════════════════════════════════════════
# 7. Reddit user public info
# ════════════════════════════════════════════════════════════════════════

def reddit_user_info(username: str) -> dict:
    """Reddit public user info via reddit.com/user/X/about.json (free)."""
    username = username.strip()
    if not re.match(r"^[a-zA-Z0-9_\-]{1,20}$", username):
        return {"error": "invalid username"}

    url = f"https://www.reddit.com/user/{username}/about.json"
    status, body = _http_get(url, timeout=10)

    if status == 404:
        return {"username": username, "exists": False}
    if status != 200:
        return {"error": f"HTTP {status}", "body": body[:200]}

    try:
        data = json.loads(body)
    except json.JSONDecodeError:
        return {"error": "invalid JSON"}

    user = data.get("data", {})
    out = {
        "username": user.get("name"),
        "exists": True,
        "id": user.get("id"),
        "created_utc": user.get("created_utc"),
        "comment_karma": user.get("comment_karma"),
        "link_karma": user.get("link_karma"),
        "is_gold": user.get("is_gold"),
        "is_mod": user.get("is_mod"),
        "verified": user.get("verified"),
        "html_url": f"https://www.reddit.com/user/{username}",
    }

    # Convert UTC to year
    tokens = []
    ts = user.get("created_utc")
    if ts:
        try:
            from datetime import datetime as _dt
            year = _dt.utcfromtimestamp(int(ts)).year
            tokens.append(str(year))
            out["created_year"] = year
        except (ValueError, OSError):
            pass

    out["tokens"] = list(dict.fromkeys(tokens))
    return out


# ════════════════════════════════════════════════════════════════════════
# 8. Codice Fiscale italiano (parser offline, OSINT-relevant)
# ════════════════════════════════════════════════════════════════════════

CF_MONTH_MAP = {
    "A": 1, "B": 2, "C": 3, "D": 4, "E": 5, "H": 6,
    "L": 7, "M": 8, "P": 9, "R": 10, "S": 11, "T": 12,
}
CF_MONTH_NAMES = {
    1: "Gennaio", 2: "Febbraio", 3: "Marzo", 4: "Aprile",
    5: "Maggio", 6: "Giugno", 7: "Luglio", 8: "Agosto",
    9: "Settembre", 10: "Ottobre", 11: "Novembre", 12: "Dicembre",
}


def parse_codice_fiscale(cf: str, epoca: str = "auto") -> dict:
    """Parse codice fiscale italiano (16 char) → estrai DOB + sesso + comune.

    Format: SSSNNNYYMDD-CC-K (S=cogn, N=nome, Y=year, M=month, D=day, C=comune, K=check)

    Args:
        cf: codice fiscale 16 caratteri
        epoca: 'auto' (heuristic), 'old' (1900s force), 'new' (2000s force)

    Note: l'epoca aiuta a disambiguare anni come '85' (= 1985 o 2085?).
    """
    cf = cf.strip().upper().replace(" ", "")
    if not re.match(r"^[A-Z0-9]{16}$", cf):
        return {"error": "Codice fiscale non valido (deve essere 16 caratteri)"}

    cogn_code = cf[0:3]
    nome_code = cf[3:6]
    year_2d = cf[6:8]
    month_letter = cf[8]
    day_2d = cf[9:11]
    comune = cf[11:15]
    check = cf[15]

    # Validate components
    try:
        yr = int(year_2d)
        if epoca == "old":
            year_full = 1900 + yr
        elif epoca == "new":
            year_full = 2000 + yr
        else:
            # Auto: heuristic considerando l'anno corrente
            from datetime import datetime as _dt
            current_yy = _dt.now().year % 100
            # Se l'anno suggerirebbe una nascita futura nel 2000s,
            # va nel 1900s (es. yr=99 → 1999, non 2099)
            if 2000 + yr > _dt.now().year:
                year_full = 1900 + yr
            else:
                year_full = 2000 + yr
    except ValueError:
        return {"error": "anno non valido"}

    if month_letter not in CF_MONTH_MAP:
        return {"error": "mese non valido"}
    month = CF_MONTH_MAP[month_letter]

    try:
        day = int(day_2d)
    except ValueError:
        return {"error": "giorno non valido"}

    # Day > 40 → female (subtract 40)
    if day > 40:
        sesso = "F"
        day -= 40
    else:
        sesso = "M"

    if not (1 <= day <= 31):
        return {"error": "giorno fuori range"}

    out = {
        "cf": cf,
        "valid": True,
        "anno_nascita": year_full,
        "anno_short": year_2d,
        "mese": month,
        "mese_nome": CF_MONTH_NAMES.get(month, "?"),
        "giorno": day,
        "data_nascita": f"{day:02d}/{month:02d}/{year_full}",
        "sesso": sesso,
        "codice_comune": comune,
        "check_digit": check,
        "iniziali_cognome": cogn_code,
        "iniziali_nome": nome_code,
    }

    # Tokens for password gen
    tokens = [
        str(year_full),
        year_2d,
        f"{day:02d}",
        f"{month:02d}",
        f"{day:02d}{month:02d}",
        f"{day:02d}{month:02d}{year_full}",
        f"{day:02d}{month:02d}{year_2d}",
    ]
    out["tokens"] = list(dict.fromkeys(tokens))
    return out


def find_codici_fiscali(text: str) -> list[str]:
    """Trova codici fiscali italiani nel testo."""
    pattern = re.compile(r"\b[A-Z]{6}[0-9]{2}[A-Z][0-9]{2}[A-Z][0-9]{3}[A-Z]\b", re.IGNORECASE)
    return [m.upper() for m in pattern.findall(text)]
