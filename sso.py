"""TOJI Ecosystem · Single Sign-On condiviso.

Permette a Mihawk, TheInvisibleHand e Horcrux di condividere lo stato di login.
Token firmato HMAC-SHA256 in `/tmp/.toji_sso.json`.

Quando un'app fa login → scrive il token.
Quando un'altra app riceve una request → legge il token, se valido auto-logga.

Sicurezza:
  - Token firmato HMAC-SHA256.
  - Chiave: TOJI_SSO_KEY env var se settata, altrimenti chiave random
    persistente in ~/.config/toji/sso_key (mode 600, condivisa tra le 3 app
    perche' stesso utente -> stesso $HOME). Nessun fallback hardcoded.
  - File token con permessi 0600 in /tmp (volatile).
  - TTL 12 ore.
"""

from __future__ import annotations

import hashlib
import hmac
import json
import os
import secrets
import sys
import time
from pathlib import Path

SSO_FILE = Path(os.environ.get("TOJI_SSO_FILE", "/tmp/.toji_sso.json"))
SSO_TTL = int(os.environ.get("TOJI_SSO_TTL", 12 * 3600))

_KEY_FILE = Path(os.environ.get(
    "TOJI_SSO_KEY_FILE",
    str(Path.home() / ".config" / "toji" / "sso_key"),
))


def _load_or_create_key() -> bytes:
    """Risolve la chiave HMAC. Priorita':
       1. env TOJI_SSO_KEY (qualsiasi stringa non vuota)
       2. file ~/.config/toji/sso_key (32 byte random, generato al primo run)
    Errore fatale se nessuna delle due strade riesce — niente default hardcoded.
    """
    env_key = os.environ.get("TOJI_SSO_KEY", "").strip()
    if env_key:
        return env_key.encode("utf-8")

    try:
        if _KEY_FILE.exists():
            data = _KEY_FILE.read_bytes().strip()
            if len(data) >= 16:
                return data
            # file presente ma corrotto: rigenera
        _KEY_FILE.parent.mkdir(parents=True, exist_ok=True)
        new_key = secrets.token_bytes(32)
        _KEY_FILE.write_bytes(new_key)
        try:
            _KEY_FILE.chmod(0o600)
        except OSError:
            pass
        print(
            f"[toji-sso] generata nuova chiave HMAC in {_KEY_FILE} "
            "(impostala via TOJI_SSO_KEY per produzione/CI)",
            file=sys.stderr,
        )
        return new_key
    except OSError as e:
        raise RuntimeError(
            f"toji-sso: impossibile leggere o creare la chiave HMAC ({e}). "
            "Imposta TOJI_SSO_KEY oppure rendi scrivibile "
            f"{_KEY_FILE.parent}."
        ) from e


SSO_KEY = _load_or_create_key()


def _sign(body: str) -> str:
    """HMAC-SHA256 hex of body."""
    return hmac.new(SSO_KEY, body.encode("utf-8"), hashlib.sha256).hexdigest()


def write_token(user: str, app_name: str = "") -> bool:
    """Scrive il token SSO. Return True se ok."""
    payload = {
        "user": user,
        "exp": int(time.time()) + SSO_TTL,
        "issued_by": app_name,
        "issued_at": int(time.time()),
    }
    body = json.dumps(payload, sort_keys=True, separators=(",", ":"))
    sig = _sign(body)
    full = {"data": payload, "sig": sig}
    try:
        SSO_FILE.write_text(json.dumps(full), encoding="utf-8")
        try:
            SSO_FILE.chmod(0o600)
        except OSError:
            pass
        return True
    except OSError:
        return False


def read_token() -> dict | None:
    """Legge e valida il token SSO. Return payload o None."""
    if not SSO_FILE.exists():
        return None
    try:
        raw = SSO_FILE.read_text(encoding="utf-8")
        full = json.loads(raw)
        if not isinstance(full, dict) or "data" not in full or "sig" not in full:
            return None
        body = json.dumps(full["data"], sort_keys=True, separators=(",", ":"))
        expected_sig = _sign(body)
        if not hmac.compare_digest(expected_sig, full["sig"]):
            return None
        if full["data"].get("exp", 0) < time.time():
            return None
        return full["data"]
    except (OSError, ValueError, KeyError):
        return None


def clear_token() -> None:
    """Cancella il token SSO."""
    try:
        SSO_FILE.unlink()
    except OSError:
        pass


def is_logged_in() -> bool:
    """Quick check: c'è un token valido?"""
    return read_token() is not None


def get_logged_user() -> str | None:
    """Return username dal token, o None."""
    tok = read_token()
    return tok.get("user") if tok else None
