"""Horcrux OSINT · Social username availability check (Sherlock-style).

Dato uno username, controlla se esiste un account con quel nome
su una lista di social network/piattaforme pubbliche.

NOTE LEGALI/ETICHE:
  - Effettua solo richieste HTTP HEAD/GET su URL pubblici.
  - NON tenta login, NON scrape contenuti privati.
  - Rispetta User-Agent e rate limit (timeout corto, parallelism ridotto).
  - Equivalente a quello che farebbe un browser per controllare se URL esiste.
  - Strumento diffuso in pentest legittimo (cf. sherlock-project).
"""

from __future__ import annotations

import urllib.error
import urllib.request
from concurrent.futures import ThreadPoolExecutor, as_completed

USER_AGENT = (
    "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 "
    "(KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
)

# ── Lista di siti supportati ────────────────────────────────────────────────
# Format: site_name → {url_pattern, method, success_codes, fail_codes,
#                      body_must_contain (optional), body_must_not_contain (optional)}
#
# Per ogni sito definiamo la strategia per stabilire se l'username esiste:
#  - status: solo controllo HTTP status code
#  - body: richiede check del body (alcuni siti redirectano a 200 con error message)

SOCIAL_SITES: dict[str, dict] = {
    "GitHub": {
        "url": "https://github.com/{user}",
        "method": "HEAD",
        "exists_codes": [200],
        "missing_codes": [404],
        "category": "tech",
    },
    "GitLab": {
        "url": "https://gitlab.com/{user}",
        "method": "HEAD",
        "exists_codes": [200],
        "missing_codes": [404],
        "category": "tech",
    },
    "Reddit": {
        "url": "https://www.reddit.com/user/{user}/about.json",
        "method": "GET",
        "exists_codes": [200],
        "missing_codes": [404, 403],
        "category": "social",
    },
    "Twitter/X": {
        "url": "https://twitter.com/{user}",
        "method": "GET",
        "exists_codes": [200],
        "missing_codes": [404],
        "category": "social",
        "body_must_not_contain": ["This account doesn't exist"],
    },
    "Instagram": {
        "url": "https://www.instagram.com/{user}/",
        "method": "GET",
        "exists_codes": [200],
        "missing_codes": [404],
        "category": "social",
        "body_must_not_contain": ["Page Not Found", "Sorry, this page isn't available"],
    },
    "TikTok": {
        "url": "https://www.tiktok.com/@{user}",
        "method": "GET",
        "exists_codes": [200],
        "missing_codes": [404],
        "category": "social",
        "body_must_not_contain": ["Couldn't find this account"],
    },
    "Pinterest": {
        "url": "https://www.pinterest.com/{user}/",
        "method": "HEAD",
        "exists_codes": [200],
        "missing_codes": [404],
        "category": "social",
    },
    "Twitch": {
        "url": "https://www.twitch.tv/{user}",
        "method": "GET",
        "exists_codes": [200],
        "missing_codes": [404],
        "category": "gaming",
    },
    "Steam": {
        "url": "https://steamcommunity.com/id/{user}/",
        "method": "GET",
        "exists_codes": [200],
        "missing_codes": [404],
        "category": "gaming",
        "body_must_not_contain": ["The specified profile could not be found"],
    },
    "Tumblr": {
        "url": "https://{user}.tumblr.com/",
        "method": "HEAD",
        "exists_codes": [200, 301, 302],
        "missing_codes": [404],
        "category": "blog",
    },
    "Medium": {
        "url": "https://medium.com/@{user}",
        "method": "GET",
        "exists_codes": [200],
        "missing_codes": [404],
        "category": "blog",
        "body_must_not_contain": ["404", "user does not exist"],
    },
    "DEV": {
        "url": "https://dev.to/{user}",
        "method": "HEAD",
        "exists_codes": [200],
        "missing_codes": [404],
        "category": "tech",
    },
    "Keybase": {
        "url": "https://keybase.io/{user}",
        "method": "GET",
        "exists_codes": [200],
        "missing_codes": [404],
        "category": "tech",
    },
    "HackerNews": {
        "url": "https://news.ycombinator.com/user?id={user}",
        "method": "GET",
        "exists_codes": [200],
        "missing_codes": [404],
        "category": "tech",
        "body_must_not_contain": ["No such user"],
    },
    "Lichess": {
        "url": "https://lichess.org/@/{user}",
        "method": "HEAD",
        "exists_codes": [200],
        "missing_codes": [404],
        "category": "gaming",
    },
    "Chess.com": {
        "url": "https://www.chess.com/member/{user}",
        "method": "GET",
        "exists_codes": [200],
        "missing_codes": [404],
        "category": "gaming",
    },
    "Roblox": {
        "url": "https://www.roblox.com/users/profile?username={user}",
        "method": "HEAD",
        "exists_codes": [200],
        "missing_codes": [302, 404],
        "category": "gaming",
    },
    "Spotify": {
        "url": "https://open.spotify.com/user/{user}",
        "method": "HEAD",
        "exists_codes": [200],
        "missing_codes": [404],
        "category": "music",
    },
    "SoundCloud": {
        "url": "https://soundcloud.com/{user}",
        "method": "HEAD",
        "exists_codes": [200, 302, 301],
        "missing_codes": [404],
        "category": "music",
    },
    "PayPal.me": {
        "url": "https://www.paypal.com/paypalme/{user}",
        "method": "GET",
        "exists_codes": [200],
        "missing_codes": [404],
        "category": "finance",
    },
    # Additional popular sites
    "Vimeo": {
        "url": "https://vimeo.com/{user}",
        "method": "HEAD",
        "exists_codes": [200],
        "missing_codes": [404],
        "category": "media",
    },
    "Behance": {
        "url": "https://www.behance.net/{user}",
        "method": "HEAD",
        "exists_codes": [200],
        "missing_codes": [404],
        "category": "design",
    },
    "Dribbble": {
        "url": "https://dribbble.com/{user}",
        "method": "GET",
        "exists_codes": [200],
        "missing_codes": [404],
        "category": "design",
    },
    "Flickr": {
        "url": "https://www.flickr.com/people/{user}/",
        "method": "GET",
        "exists_codes": [200],
        "missing_codes": [404],
        "category": "photo",
    },
    "Bandcamp": {
        "url": "https://{user}.bandcamp.com",
        "method": "HEAD",
        "exists_codes": [200],
        "missing_codes": [404],
        "category": "music",
    },
    "Patreon": {
        "url": "https://www.patreon.com/{user}",
        "method": "HEAD",
        "exists_codes": [200],
        "missing_codes": [404],
        "category": "social",
    },
    "Last.fm": {
        "url": "https://www.last.fm/user/{user}",
        "method": "HEAD",
        "exists_codes": [200],
        "missing_codes": [404],
        "category": "music",
    },
    "Goodreads": {
        "url": "https://www.goodreads.com/{user}",
        "method": "GET",
        "exists_codes": [200],
        "missing_codes": [404],
        "category": "books",
    },
    "Mixcloud": {
        "url": "https://www.mixcloud.com/{user}/",
        "method": "HEAD",
        "exists_codes": [200],
        "missing_codes": [404],
        "category": "music",
    },
    "Pastebin": {
        "url": "https://pastebin.com/u/{user}",
        "method": "HEAD",
        "exists_codes": [200],
        "missing_codes": [404],
        "category": "tech",
    },
    "Replit": {
        "url": "https://replit.com/@{user}",
        "method": "HEAD",
        "exists_codes": [200],
        "missing_codes": [404],
        "category": "tech",
    },
    "Codepen": {
        "url": "https://codepen.io/{user}",
        "method": "HEAD",
        "exists_codes": [200],
        "missing_codes": [404],
        "category": "tech",
    },
    "Hackerrank": {
        "url": "https://www.hackerrank.com/{user}",
        "method": "HEAD",
        "exists_codes": [200],
        "missing_codes": [404],
        "category": "tech",
    },
    "Quora": {
        "url": "https://www.quora.com/profile/{user}",
        "method": "HEAD",
        "exists_codes": [200],
        "missing_codes": [404],
        "category": "social",
    },
    "About.me": {
        "url": "https://about.me/{user}",
        "method": "HEAD",
        "exists_codes": [200],
        "missing_codes": [404],
        "category": "social",
    },
}


def _check_one(site_name: str, site_cfg: dict, username: str, timeout: float = 8.0) -> dict:
    """Check di un singolo sito. Ritorna dict con esito."""
    url = site_cfg["url"].format(user=username)
    method = site_cfg.get("method", "HEAD")
    exists_codes = site_cfg.get("exists_codes", [200])
    missing_codes = site_cfg.get("missing_codes", [404])
    body_must_not = site_cfg.get("body_must_not_contain", [])
    body_must = site_cfg.get("body_must_contain", [])

    result = {
        "site": site_name,
        "category": site_cfg.get("category", ""),
        "url": url,
        "found": None,  # True / False / None (=unknown)
        "status": None,
        "error": None,
    }

    try:
        req = urllib.request.Request(url, method=method, headers={"User-Agent": USER_AGENT})
        with urllib.request.urlopen(req, timeout=timeout) as resp:
            result["status"] = resp.status

            if resp.status in missing_codes:
                result["found"] = False
            elif resp.status in exists_codes:
                # Optional body check
                if body_must_not or body_must:
                    try:
                        body = resp.read(8192).decode("utf-8", errors="replace")
                    except Exception:
                        body = ""
                    if body_must_not and any(s.lower() in body.lower() for s in body_must_not):
                        result["found"] = False
                    elif body_must and not any(s.lower() in body.lower() for s in body_must):
                        result["found"] = False
                    else:
                        result["found"] = True
                else:
                    result["found"] = True
            else:
                result["found"] = None  # unknown status

    except urllib.error.HTTPError as e:
        result["status"] = e.code
        if e.code in missing_codes:
            result["found"] = False
        elif e.code in exists_codes:
            result["found"] = True
        else:
            result["found"] = None
            result["error"] = f"HTTP {e.code}"
    except urllib.error.URLError as e:
        result["error"] = f"URL error: {e.reason}"
    except TimeoutError:
        result["error"] = "timeout"
    except Exception as e:
        result["error"] = str(e)[:80]

    return result


def check_username_on_socials(
    username: str,
    sites: list[str] | None = None,
    max_workers: int = 6,
    timeout: float = 8.0,
) -> dict:
    """Controlla username su lista di social.

    Args:
        username: lo username da cercare
        sites: lista nomi siti (None = tutti)
        max_workers: parallelismo (default 6 — gentile)
        timeout: timeout per richiesta in secondi

    Returns:
        {
            "username": "marco_rossi",
            "total_checked": 20,
            "found_count": 4,
            "results": [
                {"site": "GitHub", "found": True, "url": "...", "status": 200},
                ...
            ],
            "found_only": [...],
        }
    """
    if not username:
        return {"error": "username required"}

    if sites is None:
        sites = list(SOCIAL_SITES.keys())

    targets = {name: SOCIAL_SITES[name] for name in sites if name in SOCIAL_SITES}
    if not targets:
        return {"error": "no valid sites"}

    results: list[dict] = []

    with ThreadPoolExecutor(max_workers=max_workers) as ex:
        futures = {
            ex.submit(_check_one, name, cfg, username, timeout): name
            for name, cfg in targets.items()
        }
        for future in as_completed(futures):
            try:
                results.append(future.result())
            except Exception as e:
                results.append({
                    "site": futures[future],
                    "error": str(e)[:80],
                    "found": None,
                })

    # Sort: found True first, then found None, then False
    results.sort(key=lambda r: (
        0 if r.get("found") is True else (1 if r.get("found") is None else 2),
        r.get("site", "")
    ))

    found_only = [r for r in results if r.get("found") is True]

    return {
        "username": username,
        "total_checked": len(results),
        "found_count": len(found_only),
        "results": results,
        "found_only": found_only,
    }
