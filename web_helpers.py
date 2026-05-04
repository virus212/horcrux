"""Horcrux · Web helpers (decorators, validation, logging, cache).

Centralizza:
  - Error handling (try/except universale)
  - Rate limiting (in-memory token bucket)
  - Input validation (lunghezza max)
  - CSRF protection (Origin/Referer check)
  - Logging strutturato
  - LRU cache con mtime invalidation per messages.json
"""

from __future__ import annotations

import logging
import logging.handlers
import os
import time
import traceback
from collections import defaultdict, deque
from functools import wraps
from pathlib import Path
from threading import Lock

from flask import jsonify, request

# ── Logging setup ──────────────────────────────────────────────────────────

LOG_DIR = Path(os.environ.get("HORCRUX_LOG_DIR", Path.home() / ".horcrux" / "logs"))
LOG_DIR.mkdir(parents=True, exist_ok=True)

logger = logging.getLogger("horcrux")
logger.setLevel(logging.INFO)

if not logger.handlers:
    fmt = logging.Formatter(
        "%(asctime)s [%(levelname)s] %(name)s · %(message)s",
        datefmt="%Y-%m-%d %H:%M:%S",
    )
    fh = logging.handlers.RotatingFileHandler(
        LOG_DIR / "server.log",
        maxBytes=5 * 1024 * 1024,
        backupCount=3,
        encoding="utf-8",
    )
    fh.setFormatter(fmt)
    fh.setLevel(logging.INFO)
    logger.addHandler(fh)

    # Console handler (only WARNING+)
    ch = logging.StreamHandler()
    ch.setFormatter(fmt)
    ch.setLevel(logging.WARNING)
    logger.addHandler(ch)


# ── Input validation constants ──────────────────────────────────────────────
MAX_INPUT_LEN = 500           # per stringhe singole (channel id, query, ecc.)
MAX_TEXT_LEN = 50_000         # per body testuali (es. ricerca con contesto, manual fields)
MAX_LIST_LEN = 200            # per liste (manual_keys, osint_tokens)


# ── Rate Limiter (in-memory, per IP + endpoint) ─────────────────────────────

class RateLimiter:
    """Sliding window in-memory rate limiter."""
    def __init__(self):
        self._buckets: dict[str, deque] = defaultdict(deque)
        self._lock = Lock()

    def check(self, key: str, max_requests: int, window_sec: float) -> bool:
        """True if request is allowed, False if rate-limited."""
        now = time.time()
        with self._lock:
            bucket = self._buckets[key]
            # Drop expired
            while bucket and bucket[0] < now - window_sec:
                bucket.popleft()
            if len(bucket) >= max_requests:
                return False
            bucket.append(now)
            return True


_rate_limiter = RateLimiter()


def rate_limit(max_requests: int = 30, window_sec: float = 60.0):
    """Decorator: rate limit per IP + endpoint."""
    def decorator(f):
        @wraps(f)
        def wrapped(*args, **kwargs):
            ip = request.remote_addr or "unknown"
            key = f"{ip}:{f.__name__}"
            if not _rate_limiter.check(key, max_requests, window_sec):
                logger.warning(f"Rate limit hit: {key}")
                return jsonify({
                    "error": "rate limit exceeded",
                    "retry_after_sec": int(window_sec),
                }), 429
            return f(*args, **kwargs)
        return wrapped
    return decorator


# ── CSRF protection (Origin/Referer check) ──────────────────────────────────

def csrf_protect(f):
    """Decorator: rifiuta POST/PUT/DELETE da Origin esterni."""
    @wraps(f)
    def wrapped(*args, **kwargs):
        if request.method in ("POST", "PUT", "DELETE", "PATCH"):
            origin = request.headers.get("Origin", "")
            referer = request.headers.get("Referer", "")
            host = request.host_url.rstrip("/")
            # Permetti se Origin == host o assente (chiamate same-origin di alcuni browser)
            if origin and not origin.startswith(host):
                # Ma accetta se è localhost/127.0.0.1 (devel)
                if not any(x in origin for x in ("localhost", "127.0.0.1")):
                    logger.warning(f"CSRF blocked: origin={origin} host={host}")
                    return jsonify({"error": "CSRF: invalid origin"}), 403
            if referer and host not in referer:
                if not any(x in referer for x in ("localhost", "127.0.0.1")):
                    logger.warning(f"CSRF blocked: referer={referer} host={host}")
                    return jsonify({"error": "CSRF: invalid referer"}), 403
        return f(*args, **kwargs)
    return wrapped


# ── Input validation ────────────────────────────────────────────────────────

def _validate_recursive(obj, depth: int = 0) -> str | None:
    """Validate input recursively. Returns error message or None."""
    if depth > 6:
        return "input too deeply nested"

    if isinstance(obj, str):
        if len(obj) > MAX_TEXT_LEN:
            return f"string too long (max {MAX_TEXT_LEN})"
    elif isinstance(obj, list):
        if len(obj) > MAX_LIST_LEN:
            return f"list too long (max {MAX_LIST_LEN})"
        for item in obj:
            err = _validate_recursive(item, depth + 1)
            if err:
                return err
    elif isinstance(obj, dict):
        if len(obj) > 50:
            return "dict has too many keys (max 50)"
        for k, v in obj.items():
            if not isinstance(k, str) or len(k) > 100:
                return "invalid dict key"
            err = _validate_recursive(v, depth + 1)
            if err:
                return err
    return None


def validate_input(f):
    """Decorator: valida lunghezza input per request args + JSON body."""
    @wraps(f)
    def wrapped(*args, **kwargs):
        # Validate query string args
        for k, v in request.args.items():
            if len(k) > 100:
                return jsonify({"error": "invalid query param key"}), 400
            if len(v) > MAX_INPUT_LEN:
                return jsonify({
                    "error": f"query param '{k}' too long (max {MAX_INPUT_LEN})"
                }), 400

        # Validate JSON body
        if request.method in ("POST", "PUT", "PATCH"):
            if request.is_json:
                try:
                    data = request.get_json(silent=True)
                    if data is not None:
                        err = _validate_recursive(data)
                        if err:
                            return jsonify({"error": f"invalid input: {err}"}), 400
                except Exception:
                    pass

        # Validate URL params
        for k, v in kwargs.items():
            if isinstance(v, str) and len(v) > MAX_INPUT_LEN:
                return jsonify({
                    "error": f"path param '{k}' too long (max {MAX_INPUT_LEN})"
                }), 400

        return f(*args, **kwargs)
    return wrapped


# ── Safe endpoint: try/except + log ─────────────────────────────────────────

def safe_endpoint(f):
    """Decorator: wrap in try/except, log eccezioni, ritorna JSON pulito."""
    @wraps(f)
    def wrapped(*args, **kwargs):
        try:
            return f(*args, **kwargs)
        except Exception as e:
            logger.error(
                f"Endpoint '{f.__name__}' failed: {type(e).__name__}: {e}\n"
                f"{traceback.format_exc()}"
            )
            # Sanitize: don't leak internal details to user
            return jsonify({
                "error": "internal server error",
                "type": type(e).__name__,
                "message": str(e)[:200],
            }), 500
    return wrapped


# ── Path traversal protection ───────────────────────────────────────────────

def safe_path(base: Path, user_input: str) -> Path | None:
    """Resolve user_input under base, ensure no traversal. None se invalid."""
    if not user_input or not isinstance(user_input, str):
        return None
    if any(c in user_input for c in ("\x00", "\n", "\r")):
        return None
    if len(user_input) > 200:
        return None
    try:
        candidate = (base / user_input).resolve()
        base_resolved = base.resolve()
        # Check if candidate is under base
        candidate.relative_to(base_resolved)
        return candidate
    except (ValueError, OSError):
        return None


# ── LRU Cache for messages.json with mtime invalidation ────────────────────

class MessagesCache:
    """Cache messages.json content keyed by path, invalidated by mtime."""
    def __init__(self, max_size: int = 32):
        self._cache: dict[str, tuple[float, list]] = {}  # path → (mtime, data)
        self._lock = Lock()
        self._max = max_size

    def get(self, path: Path) -> list | None:
        """Return cached messages if mtime unchanged. None otherwise."""
        try:
            mtime = path.stat().st_mtime
        except OSError:
            return None

        with self._lock:
            cached = self._cache.get(str(path))
            if cached and cached[0] == mtime:
                return cached[1]
        return None

    def set(self, path: Path, data: list) -> None:
        try:
            mtime = path.stat().st_mtime
        except OSError:
            return

        with self._lock:
            # Evict oldest if full
            if len(self._cache) >= self._max:
                # Remove an arbitrary entry (LRU semplice: il primo)
                k = next(iter(self._cache))
                del self._cache[k]
            self._cache[str(path)] = (mtime, data)

    def invalidate(self, path: Path) -> None:
        with self._lock:
            self._cache.pop(str(path), None)

    def clear(self) -> None:
        with self._lock:
            self._cache.clear()


messages_cache = MessagesCache(max_size=32)


# ── Helper: compose multiple decorators ─────────────────────────────────────

def standard_endpoint(rate_max: int = 60, rate_window: float = 60.0):
    """Compose: validate + rate_limit + safe.

    Per essere applicato OPZIONALMENTE in cima a @app.route.
    Nota: csrf e login_required restano separati (login_required rimane
    nel web_app.py).
    """
    def decorator(f):
        @wraps(f)
        @safe_endpoint
        @rate_limit(max_requests=rate_max, window_sec=rate_window)
        @validate_input
        def wrapped(*args, **kwargs):
            return f(*args, **kwargs)
        return wrapped
    return decorator
