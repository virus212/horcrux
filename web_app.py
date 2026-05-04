#!/usr/bin/env python3
"""HORCRUX · Password Wordlist Generator from Chat Archives"""

import hashlib
import io
import json
import os
import re
import secrets
from collections import Counter
from datetime import datetime, timedelta
from functools import wraps
from pathlib import Path

from flask import Flask, jsonify, redirect, render_template, request, send_file, session, url_for

from extractor import extract_features, get_analyzer
from generator import count_only, generate_wordlist
from osint import (
    enrich_phone,
    extract_emails,
    enrich_email,
    find_locations,
    generate_username_variants,
    check_username_on_socials,
    SOCIAL_SITES,
    # Online tools
    whois_lookup,
    dns_lookup,
    ip_geolocation,
    wayback_search,
    email_reputation,
    github_user_info,
    reddit_user_info,
    parse_codice_fiscale,
    find_codici_fiscali,
)
from osint.phone_intel import password_tokens_from_phone
from osint.email_intel import password_tokens_from_emails
from osint.geo_intel import password_tokens_from_locations
from web_helpers import (
    safe_endpoint, rate_limit, validate_input, csrf_protect,
    safe_path, messages_cache, logger,
)
from sso import write_token as sso_write, read_token as sso_read, clear_token as sso_clear

# ── Configuration ──────────────────────────────────────────────────────────
APP_DIR = Path(__file__).resolve().parent
MIHAWK_DIR = Path(os.environ.get(
    "HORCRUX_MIHAWK_DIR",
    Path.home() / "Desktop" / "Mihawk---chat-explorer-and-analyzer-main"
))

USERNAME = os.environ.get("HORCRUX_USER", "toji")
PASSWORD = os.environ.get("HORCRUX_PASS", "lilliv")
USING_DEFAULT_CREDS = (USERNAME == "toji" and PASSWORD == "lilliv")

app = Flask(__name__, template_folder="templates", static_folder="static")
app.secret_key = os.environ.get("HORCRUX_SECRET") or secrets.token_hex(32)
app.permanent_session_lifetime = timedelta(hours=12)

logger.info(f"Horcrux server starting · MIHAWK_DIR={MIHAWK_DIR}")
if USING_DEFAULT_CREDS:
    logger.warning("⚠️  USING DEFAULT CREDENTIALS (toji/lilliv) — change HORCRUX_USER/HORCRUX_PASS!")


def login_required(view):
    @wraps(view)
    def wrapped(*args, **kwargs):
        if not session.get("authed"):
            # Try SSO: if another app has already logged in, accept it
            sso_tok = sso_read()
            if sso_tok:
                session.permanent = True
                session["authed"] = True
                session["sso_user"] = sso_tok.get("user", "")
                logger.info(f"SSO auto-login as '{sso_tok.get('user')}' (from {sso_tok.get('issued_by','?')})")
            else:
                if request.path.startswith("/api/"):
                    return jsonify({"error": "auth required"}), 401
                return redirect(url_for("login"))
        return view(*args, **kwargs)
    return wrapped


def load_messages_cached(channel_dir: Path) -> list[dict]:
    """Load messages.json with mtime-invalidated cache."""
    msg_file = channel_dir / "messages.json"
    if not msg_file.exists():
        return []
    cached = messages_cache.get(msg_file)
    if cached is not None:
        return cached
    try:
        with open(msg_file, encoding="utf-8") as f:
            data = json.load(f)
    except (OSError, json.JSONDecodeError) as e:
        logger.warning(f"Cannot load {msg_file}: {e}")
        return []
    messages_cache.set(msg_file, data)
    return data


def resolve_channel_dir(channel_id: str) -> Path | None:
    """Path-traversal-safe resolution of channel directory."""
    safe = safe_path(MIHAWK_DIR, channel_id)
    if safe is None or not safe.is_dir():
        return None
    return safe


def discover_channels() -> dict[str, str]:
    """Discover Mihawk-compatible channel folders."""
    if not MIHAWK_DIR.is_dir():
        return {}
    found = {}
    for entry in sorted(MIHAWK_DIR.iterdir()):
        if not entry.is_dir() or entry.name.startswith((".", "_", "__")):
            continue
        if not (entry / "messages.json").exists():
            continue
        label_file = entry / "_label.txt"
        if label_file.exists():
            try:
                name = label_file.read_text(encoding="utf-8").strip() or entry.name
            except Exception:
                name = entry.name
        else:
            name = entry.name.replace("_-_", " - ").replace("_", " ")
        found[entry.name] = name
    return found


def merge_features(*features_list: dict) -> dict:
    """Merge multiple feature dicts into one."""
    merged = {
        "names": [], "dates": [], "numbers": [], "phones": [],
        "ages_birth_years": [], "animals": [], "keywords": [],
        "topics": {}, "emojis": [], "authors": [], "message_count": 0,
    }
    for feat in features_list:
        if not feat:
            continue
        for k in ["names", "dates", "numbers", "phones", "ages_birth_years",
                  "animals", "keywords", "emojis", "authors"]:
            for item in feat.get(k, []):
                if item not in merged[k]:
                    merged[k].append(item)
        # Topics: sum counts
        topics = feat.get("topics", {})
        if isinstance(topics, dict):
            for t, c in topics.items():
                merged["topics"][t] = merged["topics"].get(t, 0) + c
        merged["message_count"] += feat.get("message_count", 0)
    return merged


# ── Routes ─────────────────────────────────────────────────────────────────

@app.route("/login", methods=["GET", "POST"])
def login():
    # If SSO valid, auto-login
    if request.method == "GET":
        sso_tok = sso_read()
        if sso_tok:
            session.permanent = True
            session["authed"] = True
            session["sso_user"] = sso_tok.get("user", "")
            return redirect(url_for("index"))

    error = None
    if request.method == "POST":
        if (request.form.get("username") == USERNAME and
            request.form.get("password") == PASSWORD):
            session.permanent = True
            session["authed"] = True
            session["sso_user"] = USERNAME
            sso_write(USERNAME, app_name="horcrux")
            logger.info(f"Login + SSO write by '{USERNAME}'")
            return redirect(url_for("index"))
        error = "Credenziali errate"
    return render_template("login.html", error=error)


@app.route("/logout")
def logout():
    user = session.get("sso_user", "?")
    session.clear()
    sso_clear()
    logger.info(f"Logout + SSO clear by '{user}'")
    return redirect(url_for("login"))


@app.route("/")
@login_required
def index():
    return render_template("index.html")


@app.route("/api/channels")
@login_required
@validate_input
@safe_endpoint
def api_channels():
    """List all available Mihawk channels with author info."""
    channels = discover_channels()
    result = []
    for folder, name in channels.items():
        channel_dir = MIHAWK_DIR / folder
        try:
            data = load_messages_cached(channel_dir)
            msgs = [m for m in data if m.get("_") == "Message"]
            count = len(msgs)
            authors = sorted(set(m.get("user_display_name", "") for m in msgs if m.get("user_display_name")))
            is_group = len(authors) > 1
        except Exception:
            count = 0
            authors = []
            is_group = False
        has_wordlist = (channel_dir / "wordlist.txt").exists()
        has_profile = (channel_dir / "_horcrux_profile.json").exists()
        result.append({
            "id": folder,
            "name": name,
            "message_count": count,
            "authors": authors,
            "is_group": is_group,
            "has_wordlist": has_wordlist,
            "has_profile": has_profile,
        })
    return jsonify(result)


@app.route("/api/extract")
@login_required
@rate_limit(max_requests=30, window_sec=60)
@validate_input
@safe_endpoint
def api_extract():
    """Extract features from a single channel."""
    channel_id = request.args.get("channel")
    author = request.args.get("author")

    if not channel_id:
        return jsonify({"error": "channel parameter required"}), 400

    channel_dir = resolve_channel_dir(channel_id)
    if channel_dir is None or not (channel_dir / "messages.json").exists():
        return jsonify({"error": "channel not found"}), 404

    try:
        features = extract_features(channel_dir, author_filter=author)
        features["author_filter"] = author
        return jsonify(features)
    except Exception as e:
        return jsonify({"error": str(e)}), 500


@app.route("/api/extract-multi", methods=["POST"])
@login_required
@csrf_protect
@rate_limit(max_requests=30, window_sec=60)
@validate_input
@safe_endpoint
def api_extract_multi():
    """Search a person across all channels and merge features. (Task #4)"""
    data = request.get_json() or {}
    author = data.get("author", "").strip()

    if not author:
        return jsonify({"error": "author required"}), 400

    channels = discover_channels()
    matched_channels: list[dict] = []
    all_features: list[dict] = []

    for folder in channels:
        channel_dir = MIHAWK_DIR / folder
        try:
            features = extract_features(channel_dir, author_filter=author)
            if features.get("message_count", 0) > 0:
                matched_channels.append({
                    "id": folder,
                    "name": channels[folder],
                    "message_count": features["message_count"],
                })
                all_features.append(features)
        except Exception:
            continue

    if not all_features:
        return jsonify({"error": f"no messages found for author '{author}'"}), 404

    merged = merge_features(*all_features)
    merged["author_filter"] = author
    merged["matched_channels"] = matched_channels

    return jsonify(merged)


@app.route("/api/authors/<channel_id>")
@login_required
@validate_input
@safe_endpoint
def api_authors(channel_id):
    """Get list of authors in a channel."""
    channel_dir = resolve_channel_dir(channel_id)
    if channel_dir is None:
        return jsonify({"error": "channel not found"}), 404
    msg_file = channel_dir / "messages.json"
    if not msg_file.exists():
        return jsonify({"error": "channel not found"}), 404

    try:
        data = load_messages_cached(channel_dir)

        msgs = [m for m in data if m.get("_") == "Message"]
        authors = sorted(set(m.get("user_display_name", "") for m in msgs if m.get("user_display_name")))
        return jsonify({"authors": authors})
    except Exception as e:
        return jsonify({"error": str(e)}), 500


@app.route("/api/count", methods=["POST"])
@login_required
@csrf_protect
@rate_limit(max_requests=30, window_sec=60)
@validate_input
@safe_endpoint
def api_count():
    """Fast count without saving - for live preview. (Task #5)"""
    data = request.get_json() or {}
    features = data.get("features", {})
    level = data.get("level", "medium")
    manual_keys = data.get("manual_keys", [])
    leet_level = data.get("leet_level", "auto")
    exclude_common = bool(data.get("exclude_common", True))
    exclude_extra = data.get("exclude_extra") or []

    if level not in ("easy", "medium", "hard"):
        return jsonify({"error": "level must be easy|medium|hard"}), 400

    try:
        count = count_only(
            features, level=level, manual_keys=manual_keys,
            leet_level=leet_level, exclude_common=exclude_common,
            exclude_extra=exclude_extra,
        )
        return jsonify({"count": count})
    except Exception as e:
        return jsonify({"error": str(e)}), 500


@app.route("/api/generate", methods=["POST"])
@login_required
@csrf_protect
@rate_limit(max_requests=30, window_sec=60)
@validate_input
@safe_endpoint
def api_generate():
    """Generate wordlist from features (extracted or provided)."""
    data = request.get_json() or {}

    channel_id = data.get("channel")
    level = data.get("level", "medium")
    manual_keys = data.get("manual_keys", [])
    provided_features = data.get("features")
    leet_level = data.get("leet_level", "auto")
    exclude_common = bool(data.get("exclude_common", True))
    exclude_extra = data.get("exclude_extra") or []

    if not channel_id:
        return jsonify({"error": "channel required"}), 400
    if level not in ("easy", "medium", "hard"):
        return jsonify({"error": "level must be easy|medium|hard"}), 400
    if leet_level not in ("auto", "off", "base", "advanced"):
        return jsonify({"error": "leet_level must be auto|off|base|advanced"}), 400

    # ── Modalita' standalone: niente chat, solo features manuali/OSINT ──
    if channel_id == "_standalone":
        if not provided_features:
            return jsonify({"error": "features required in standalone mode"}), 400
        target_name = (data.get("target_name") or "standalone").strip()
        target_safe = re.sub(r"[^A-Za-z0-9_-]+", "_", target_name).strip("_") or "standalone"
        out_root = APP_DIR / "manual_wordlists"
        out_root.mkdir(parents=True, exist_ok=True)
        channel_dir = out_root  # path dummy per i salvataggi
        features = provided_features
        wordlist, drop_stats = generate_wordlist(
            features, level=level, manual_keys=manual_keys, return_stats=True,
            leet_level=leet_level, exclude_common=exclude_common, exclude_extra=exclude_extra,
        )
        wordlist_path = out_root / f"{target_safe}.txt"
        header = f"# Horcrux standalone · {datetime.now().strftime('%Y-%m-%d %H:%M')} · target={target_name} · level={level}\n"
        wordlist_path.write_text(header + "\n".join(wordlist), encoding="utf-8")
        return jsonify({
            "count": len(wordlist),
            "drop_stats": drop_stats,
            "drop_total": sum(drop_stats.values()),
            "preview": wordlist[:30],
            "saved": str(wordlist_path),
            "standalone": True,
            "target": target_safe,
        })

    channel_dir = resolve_channel_dir(channel_id)
    if channel_dir is None or not (channel_dir / "messages.json").exists():
        return jsonify({"error": "channel not found"}), 404

    features = provided_features if provided_features else extract_features(channel_dir)
    wordlist, drop_stats = generate_wordlist(
        features, level=level, manual_keys=manual_keys, return_stats=True,
        leet_level=leet_level, exclude_common=exclude_common, exclude_extra=exclude_extra,
    )

    wordlist_path = channel_dir / "wordlist.txt"
    header = f"# Horcrux wordlist · {datetime.now().strftime('%Y-%m-%d %H:%M')} · level={level}\n"
    wordlist_path.write_text(header + "\n".join(wordlist), encoding="utf-8")

    # History: salva anche con timestamp
    history_dir = channel_dir / "_horcrux_history"
    history_dir.mkdir(exist_ok=True)
    history_path = history_dir / f"wordlist_{datetime.now().strftime('%Y%m%d_%H%M%S')}_{level}.txt"
    history_path.write_text(header + "\n".join(wordlist), encoding="utf-8")

    logger.info(
        f"Generated wordlist for {channel_id}: {len(wordlist)} pwds, "
        f"drops={drop_stats}, level={level}"
    )

    return jsonify({
        "count": len(wordlist),
        "preview": wordlist[:30],
        "saved": True,
        "drop_stats": drop_stats,
        "drop_total": sum(drop_stats.values()),
    })


@app.route("/api/exclusion/parse", methods=["POST"])
@login_required
@csrf_protect
@validate_input
@safe_endpoint
def api_exclusion_parse():
    """Parse una wordlist di esclusione passata come testo (una password per riga).

    Risponde con il set normalizzato (lowercase, trimmed, no commenti #).
    Il client poi passa questo set a /api/generate via campo `exclude_extra`.
    Limite 50k voci per evitare abusi.
    """
    data = request.get_json() or {}
    text = data.get("text", "")
    if not isinstance(text, str):
        return jsonify({"error": "text must be a string"}), 400
    if len(text) > 5_000_000:  # 5 MB safety
        return jsonify({"error": "wordlist too large (max 5MB)"}), 413

    out: list[str] = []
    seen: set = set()
    for line in text.splitlines():
        word = line.strip()
        if not word or word.startswith("#"):
            continue
        key = word.lower()
        if key not in seen:
            seen.add(key)
            out.append(word)
        if len(out) >= 50_000:
            break
    return jsonify({"count": len(out), "words": out})


@app.route("/api/stats/<channel_id>")
@login_required
@validate_input
@safe_endpoint
def api_stats(channel_id):
    """Statistics on the generated wordlist. (Task #6)"""
    channel_dir = resolve_channel_dir(channel_id)
    if channel_dir is None:
        return jsonify({"error": "channel not found"}), 404
    wordlist_path = channel_dir / "wordlist.txt"
    if not wordlist_path.exists():
        return jsonify({"error": "wordlist not found"}), 404

    try:
        lines = wordlist_path.read_text(encoding="utf-8").splitlines()
        passwords = [l for l in lines if l and not l.startswith("#")]

        # Length distribution
        length_dist: Counter = Counter()
        for p in passwords:
            length_dist[len(p)] += 1

        # Quality stats
        leet_chars = set("4310578")  # leet substitutions
        with_leet = sum(1 for p in passwords if any(c in leet_chars for c in p))
        with_special = sum(1 for p in passwords if any(c in "!@#$%^&*.+-_" for c in p))
        with_upper = sum(1 for p in passwords if any(c.isupper() for c in p))
        with_digit = sum(1 for p in passwords if any(c.isdigit() for c in p))

        # Length percentages
        total = len(passwords) or 1
        length_buckets = {
            "6-8": sum(c for l, c in length_dist.items() if 6 <= l <= 8),
            "9-12": sum(c for l, c in length_dist.items() if 9 <= l <= 12),
            "13-16": sum(c for l, c in length_dist.items() if 13 <= l <= 16),
            "17+": sum(c for l, c in length_dist.items() if l >= 17),
        }

        return jsonify({
            "total": total,
            "length_dist": dict(sorted(length_dist.items())),
            "length_buckets": length_buckets,
            "with_leet_pct": round(100 * with_leet / total, 1),
            "with_special_pct": round(100 * with_special / total, 1),
            "with_upper_pct": round(100 * with_upper / total, 1),
            "with_digit_pct": round(100 * with_digit / total, 1),
            "avg_length": round(sum(len(p) for p in passwords) / total, 1),
            "min_length": min((len(p) for p in passwords), default=0),
            "max_length": max((len(p) for p in passwords), default=0),
        })
    except Exception as e:
        return jsonify({"error": str(e)}), 500


@app.route("/api/download/<channel_id>")
@login_required
@validate_input
@safe_endpoint
def api_download(channel_id):
    """Download generated wordlist (txt format)."""
    channel_dir = resolve_channel_dir(channel_id)
    if channel_dir is None:
        return jsonify({"error": "channel not found"}), 404
    wordlist_path = channel_dir / "wordlist.txt"
    if not wordlist_path.exists():
        return jsonify({"error": "wordlist not found"}), 404
    return send_file(wordlist_path, as_attachment=True, download_name="wordlist.txt")


def _build_hashcat_rules(features: dict | None) -> list[str]:
    """Genera regole hashcat dinamiche basate sulle feature trovate.

    Sintassi base usata:
      :    no-op            l    lowercase           u    uppercase
      c    capitalize       C    invert-cap          r    reverse
      $X   append X         ^X   prepend X
      sXY  swap X→Y         d    duplicate
    """
    rules = ["# Horcrux hashcat rules — generated from target features"]
    base = [":", "l", "u", "c", "C", "r", "d"]
    rules.extend(["# core mutations", *base, ""])

    # ── Suffix comuni ──
    rules.append("# common suffixes")
    for s in ["$1", "$2", "$3", "$0", "$!", "$#", "$@", "$.", "$_"]:
        rules.append(s)
    rules.append("$1$2$3")
    rules.append("$1$2$3$4")

    # ── Anno append dinamico ──
    years = set()
    if features:
        for d in features.get("dates", []):
            ds = str(d)
            for y in ("19" + str(i) for i in range(40, 100)):
                if y in ds:
                    years.add(y)
            for y in ("20" + str(i).zfill(2) for i in range(0, 30)):
                if y in ds:
                    years.add(y)
        for y in features.get("ages_birth_years", []):
            ys = str(y).strip()
            if ys.isdigit() and len(ys) == 4:
                years.add(ys)

    if years:
        rules.append("")
        rules.append("# year append (from target dates/birth_years)")
        for y in sorted(years):
            rules.append("$" + "$".join(y))  # e.g. $1$9$9$5
        # short year
        for y in sorted(years):
            rules.append("$" + y[-2:][0] + "$" + y[-2:][1])

    # ── Leet ──
    rules.append("")
    rules.append("# leet base")
    for r in ["sa4", "se3", "si1", "so0", "ss5", "sl1", "st7"]:
        rules.append(r)
    rules.append("sa4 se3 si1 so0 ss5")  # full base leet

    rules.append("")
    rules.append("# leet advanced (with symbols)")
    for r in ["sa@", "ss$", "st+", "sg9", "sb8", "sz2"]:
        rules.append(r)
    rules.append("sa@ se3 si1 so0 ss$")  # full advanced leet

    # ── Topic-specific: solo se topic detected ──
    topics = (features or {}).get("topics") or {}
    topic_keys = list(topics.keys()) if isinstance(topics, dict) else (topics if isinstance(topics, list) else [])
    if "gaming" in topic_keys:
        rules.append("")
        rules.append("# gaming-specific suffixes")
        for s in ["$T$T$V", "$P$r$o", "$_$g$g", "$6$9", "$x$X"]:
            rules.append(s)
    if "musica" in topic_keys:
        rules.append("")
        rules.append("# musica-specific suffixes")
        for s in ["$_$d$j", "$_$f$m", "$B$e$a$t$s"]:
            rules.append(s)
    if "tech" in topic_keys:
        rules.append("")
        rules.append("# tech-specific suffixes")
        for s in ["$_$d$e$v", "$4$0$4", "$_$h$x"]:
            rules.append(s)
    if "amore" in topic_keys:
        rules.append("")
        rules.append("# amore-specific suffixes")
        for s in ["$l$o$v$e", "$_$x$o", "$4$e$v$e$r"]:
            rules.append(s)

    return rules


def _build_john_rules(features: dict | None) -> list[str]:
    """Genera regole John the Ripper dinamiche dalle feature."""
    rules = [
        "# Horcrux John the Ripper rules — generated from target features",
        "[List.Rules:HorcruxTarget]",
        ":", "l", "u", "c", "C", "r", "d",
        "$1", "$2", "$3", "$!", "$@", "$#",
    ]
    years = set()
    if features:
        for y in features.get("ages_birth_years", []):
            ys = str(y).strip()
            if ys.isdigit() and len(ys) == 4:
                years.add(ys)
    if years:
        rules.append("# year append")
        for y in sorted(years):
            rules.append("$" + "$".join(y))
    rules.append("# leet base")
    rules += ["sa4", "se3", "si1", "so0", "ss5", "sa4 se3 si1 so0"]
    rules.append("# leet advanced")
    rules += ["sa@", "ss$", "st+", "sg9", "sb8"]
    return rules


@app.route("/api/export/<channel_id>/<fmt>")
@login_required
@validate_input
@safe_endpoint
def api_export(channel_id, fmt):
    """Export wordlist in different formats: txt, hashcat, john, json.

    Hashcat / John rules sono ora DINAMICHE: lette dalle feature del target
    (anni di nascita, topic detected, ecc.) per regole piu' mirate.
    """
    # Standalone usa cartella dedicata
    if channel_id == "_standalone":
        return jsonify({"error": "standalone export non ancora supportato. Scarica .txt"}), 400

    channel_dir = resolve_channel_dir(channel_id)
    if channel_dir is None:
        return jsonify({"error": "channel not found"}), 404
    wordlist_path = channel_dir / "wordlist.txt"
    if not wordlist_path.exists():
        return jsonify({"error": "wordlist not found"}), 404

    lines = wordlist_path.read_text(encoding="utf-8").splitlines()
    passwords = [l for l in lines if l and not l.startswith("#")]

    # Carica features per regole dinamiche (best-effort)
    features = None
    profile_path = channel_dir / "_horcrux_profile.json"
    if profile_path.exists():
        try:
            features = json.loads(profile_path.read_text(encoding="utf-8"))
        except (json.JSONDecodeError, OSError):
            features = None
    if features is None:
        try:
            features = extract_features(channel_dir)
        except Exception:
            features = {}

    if fmt == "txt":
        return send_file(wordlist_path, as_attachment=True, download_name="wordlist.txt")

    elif fmt == "hashcat":
        rules = _build_hashcat_rules(features)
        content = "\n".join(rules)
        return send_file(
            io.BytesIO(content.encode("utf-8")),
            mimetype="text/plain",
            as_attachment=True,
            download_name="horcrux.rule"
        )

    elif fmt == "john":
        rules = _build_john_rules(features)
        content = "\n".join(rules)
        return send_file(
            io.BytesIO(content.encode("utf-8")),
            mimetype="text/plain",
            as_attachment=True,
            download_name="horcrux.john.rule"
        )

    elif fmt == "json":
        report = {
            "channel": channel_id,
            "generated_at": datetime.now().isoformat(),
            "total_passwords": len(passwords),
            "passwords": passwords,
            "features_summary": {
                k: (len(v) if isinstance(v, (list, dict)) else v)
                for k, v in (features or {}).items()
            } if features else {},
        }
        content = json.dumps(report, ensure_ascii=False, indent=2)
        return send_file(
            io.BytesIO(content.encode("utf-8")),
            mimetype="application/json",
            as_attachment=True,
            download_name="wordlist.json"
        )

    return jsonify({"error": "format must be txt|hashcat|john|json"}), 400


@app.route("/api/profile/save", methods=["POST"])
@login_required
@csrf_protect
@validate_input
@safe_endpoint
def api_profile_save():
    """Save modified features as a profile. (Task #8)"""
    data = request.get_json() or {}
    channel_id = data.get("channel")
    features = data.get("features")
    name = data.get("name", "default")

    if not channel_id or not features:
        return jsonify({"error": "channel and features required"}), 400

    channel_dir = resolve_channel_dir(channel_id)
    if channel_dir is None or not (channel_dir / "messages.json").exists():
        return jsonify({"error": "channel not found"}), 404

    profile_path = channel_dir / "_horcrux_profile.json"
    profile_data = {
        "name": name,
        "saved_at": datetime.now().isoformat(),
        "features": features,
    }
    profile_path.write_text(json.dumps(profile_data, ensure_ascii=False, indent=2), encoding="utf-8")

    return jsonify({"saved": True, "path": str(profile_path)})


@app.route("/api/profile/load/<channel_id>")
@login_required
@validate_input
@safe_endpoint
def api_profile_load(channel_id):
    """Load saved profile. (Task #8)"""
    channel_dir = resolve_channel_dir(channel_id)
    if channel_dir is None:
        return jsonify({"error": "channel not found"}), 404
    profile_path = channel_dir / "_horcrux_profile.json"
    if not profile_path.exists():
        return jsonify({"error": "no profile saved"}), 404

    try:
        data = json.loads(profile_path.read_text(encoding="utf-8"))
        return jsonify(data)
    except Exception as e:
        return jsonify({"error": str(e)}), 500


@app.route("/api/crack", methods=["POST"])
@login_required
@csrf_protect
@rate_limit(max_requests=30, window_sec=60)
@validate_input
@safe_endpoint
def api_crack():
    """Try to crack a hash with the generated wordlist. (Task #9)"""
    data = request.get_json() or {}
    channel_id = data.get("channel")
    hash_type = data.get("hash_type", "md5").lower()
    target_hash = data.get("hash", "").strip().lower()

    if not channel_id or not target_hash:
        return jsonify({"error": "channel and hash required"}), 400

    if hash_type not in ("md5", "sha1", "sha256", "sha512"):
        return jsonify({"error": "hash_type must be md5|sha1|sha256|sha512"}), 400

    # Validate hex hash
    if not re.match(r"^[a-f0-9]+$", target_hash):
        return jsonify({"error": "hash must be hex"}), 400

    channel_dir = resolve_channel_dir(channel_id)
    if channel_dir is None:
        return jsonify({"error": "channel not found"}), 404
    wordlist_path = channel_dir / "wordlist.txt"
    if not wordlist_path.exists():
        return jsonify({"error": "wordlist not found - generate first"}), 404

    hasher_map = {
        "md5": hashlib.md5,
        "sha1": hashlib.sha1,
        "sha256": hashlib.sha256,
        "sha512": hashlib.sha512,
    }
    hasher = hasher_map[hash_type]

    lines = wordlist_path.read_text(encoding="utf-8").splitlines()
    passwords = [l for l in lines if l and not l.startswith("#")]

    attempts = 0
    for pw in passwords:
        attempts += 1
        h = hasher(pw.encode("utf-8")).hexdigest()
        if h == target_hash:
            return jsonify({
                "cracked": True,
                "password": pw,
                "attempts": attempts,
                "total": len(passwords),
                "percentage": round(100 * attempts / len(passwords), 2),
            })

    return jsonify({
        "cracked": False,
        "attempts": attempts,
        "total": len(passwords),
    })


# ── Search & Co-occurrences (Task #12) ─────────────────────────────────────

@app.route("/api/search", methods=["POST"])
@login_required
@csrf_protect
@rate_limit(max_requests=30, window_sec=60)
@validate_input
@safe_endpoint
def api_search():
    """Cerca un termine nei messaggi del canale, ritorna match con contesto."""
    data = request.get_json() or {}
    channel_id = data.get("channel")
    query = (data.get("query") or "").strip()
    author = data.get("author")
    max_results = min(int(data.get("max_results", 30)), 200)
    context_chars = min(int(data.get("context_chars", 60)), 200)

    if not channel_id:
        return jsonify({"error": "channel required"}), 400
    if not query:
        return jsonify({"error": "query required"}), 400
    if len(query) < 2:
        return jsonify({"error": "query too short (min 2 chars)"}), 400

    channel_dir = resolve_channel_dir(channel_id)
    if channel_dir is None or not (channel_dir / "messages.json").exists():
        return jsonify({"error": "channel not found"}), 404

    try:
        analyzer = get_analyzer(channel_dir, author_filter=author)
        results = analyzer.search(query, max_results=max_results, context_chars=context_chars)
        co_occur = analyzer.co_occurrences(query, top_n=10)
        return jsonify({
            "query": query,
            "total_matches": len(results),
            "results": results,
            "co_occurrences": [{"word": w, "count": c} for w, c in co_occur],
        })
    except Exception as e:
        return jsonify({"error": str(e)}), 500


# ── Manual Wizard Mode (Task #13 + #14) ────────────────────────────────────

@app.route("/manual")
@login_required
def manual():
    """Pagina wizard per creare wordlist manualmente, senza chat."""
    return render_template("manual.html")


@app.route("/api/manual-generate", methods=["POST"])
@login_required
@csrf_protect
@rate_limit(max_requests=30, window_sec=60)
@validate_input
@safe_endpoint
def api_manual_generate():
    """Genera wordlist da dati inseriti manualmente nel wizard."""
    data = request.get_json() or {}
    level = data.get("level", "medium")
    target_name = (data.get("target_name") or "wordlist").strip()
    fields = data.get("fields", {})
    osint_tokens = data.get("osint_tokens", [])  # tokens raccolti via OSINT

    if level not in ("easy", "medium", "hard"):
        return jsonify({"error": "level must be easy|medium|hard"}), 400

    # Sanitize target_name for filename
    target_safe = re.sub(r"[^\w\-]+", "_", target_name)[:60] or "wordlist"

    # Map wizard fields → features dict (same schema as auto extraction)
    def normalize(v):
        if isinstance(v, list):
            return [str(x).strip() for x in v if str(x).strip()]
        if isinstance(v, str):
            return [s.strip() for s in re.split(r"[,;\n]+", v) if s.strip()]
        return []

    nome = normalize(fields.get("nome"))
    cognome = normalize(fields.get("cognome"))
    soprannomi = normalize(fields.get("soprannomi"))
    anno_nascita = normalize(fields.get("anno_nascita"))
    date_importanti = normalize(fields.get("date_importanti"))
    numeri = normalize(fields.get("numeri"))
    telefono = normalize(fields.get("telefono"))
    famiglia = normalize(fields.get("famiglia"))
    partner = normalize(fields.get("partner"))
    animali = normalize(fields.get("animali"))
    hobby = normalize(fields.get("hobby"))
    squadra = normalize(fields.get("squadra"))
    brands = normalize(fields.get("brands"))
    luoghi = normalize(fields.get("luoghi"))
    parole_speciali = normalize(fields.get("parole_speciali"))

    # Build features dict compatible with generator
    names = nome + cognome + famiglia + partner
    # Add animal pet names if Title Case (assume names of pets)
    for a in animali:
        if a and a[0].isupper():
            names.append(a)

    # Compute birth year derivative
    ages_birth_years: list[str] = []
    for y in anno_nascita:
        if y.isdigit():
            ages_birth_years.append(y)
            if len(y) == 4:
                ages_birth_years.append(y[2:])

    features = {
        "names": list(dict.fromkeys(names)),  # dedupe preserve order
        "dates": list(dict.fromkeys(anno_nascita + date_importanti)),
        "numbers": numeri,
        "phones": telefono,
        "ages_birth_years": ages_birth_years,
        "animals": [a for a in animali if a and not a[0].isupper()],
        "keywords": list(dict.fromkeys(hobby + squadra + parole_speciali + luoghi)),
        "brands": brands,
        "nicknames": soprannomi,
        "phrases": [],
        "topics": {},
        "emojis": [],
        "authors": [],
        "message_count": 0,
    }

    # OSINT tokens go through manual_keys param (treated as additional tokens)
    manual_keys_list = [str(t).strip() for t in osint_tokens if str(t).strip()]
    wordlist, drop_stats = generate_wordlist(
        features, level=level, manual_keys=manual_keys_list, return_stats=True,
    )

    # Save to manual folder
    manual_dir = APP_DIR / "manual_wordlists"
    manual_dir.mkdir(exist_ok=True)
    wordlist_path = manual_dir / f"{target_safe}.txt"
    header = (f"# Horcrux MANUAL wordlist · {datetime.now().strftime('%Y-%m-%d %H:%M')} "
              f"· level={level} · target={target_name}\n")
    wordlist_path.write_text(header + "\n".join(wordlist), encoding="utf-8")

    logger.info(
        f"Manual wordlist '{target_safe}': {len(wordlist)} pwds, drops={drop_stats}"
    )

    return jsonify({
        "count": len(wordlist),
        "preview": wordlist[:30],
        "saved_to": str(wordlist_path.relative_to(APP_DIR)),
        "target": target_safe,
        "drop_stats": drop_stats,
        "drop_total": sum(drop_stats.values()),
    })


@app.route("/api/manual-download/<target>")
@login_required
@validate_input
@safe_endpoint
def api_manual_download(target):
    """Download di una wordlist manuale."""
    target_safe = re.sub(r"[^\w\-]+", "_", target)[:60]
    path = APP_DIR / "manual_wordlists" / f"{target_safe}.txt"
    if not path.exists():
        return jsonify({"error": "wordlist not found"}), 404
    return send_file(path, as_attachment=True, download_name=f"{target_safe}.txt")


# ── OSINT Enrichment Endpoints (Stage 3) ────────────────────────────────────

@app.route("/api/osint/phone", methods=["POST"])
@login_required
@csrf_protect
@validate_input
@safe_endpoint
def api_osint_phone():
    """Lookup operatore/paese da numero di telefono."""
    data = request.get_json() or {}
    phone = (data.get("phone") or "").strip()
    if not phone:
        return jsonify({"error": "phone required"}), 400
    info = enrich_phone(phone)
    info["password_tokens"] = password_tokens_from_phone(phone)
    return jsonify(info)


@app.route("/api/osint/email", methods=["POST"])
@login_required
@csrf_protect
@validate_input
@safe_endpoint
def api_osint_email():
    """Estrai e arricchisci email dal testo."""
    data = request.get_json() or {}
    text = data.get("text", "")
    single = data.get("email")

    if single:
        info = enrich_email(single)
        return jsonify({"emails": [info]})

    if not text:
        return jsonify({"error": "text or email required"}), 400

    emails = extract_emails(text)
    enriched = [enrich_email(e) for e in emails]
    all_tokens = password_tokens_from_emails(emails)
    return jsonify({
        "emails": enriched,
        "count": len(enriched),
        "all_password_tokens": all_tokens,
    })


@app.route("/api/osint/locations", methods=["POST"])
@login_required
@csrf_protect
@validate_input
@safe_endpoint
def api_osint_locations():
    """Cerca città italiane / località nel testo."""
    data = request.get_json() or {}
    text = data.get("text", "")

    # Or extract from a channel directly
    if not text and data.get("channel"):
        channel_dir = resolve_channel_dir(data["channel"])
        if channel_dir and (channel_dir / "messages.json").exists():
            msgs = load_messages_cached(channel_dir)
            text = " ".join(m.get("message", "") for m in msgs
                            if m.get("_") == "Message")

    if not text:
        return jsonify({"error": "text or channel required"}), 400

    locations = find_locations(text)
    tokens = password_tokens_from_locations(locations)
    return jsonify({
        "locations": locations,
        "count": len(locations),
        "password_tokens": tokens,
    })


@app.route("/api/osint/usernames", methods=["POST"])
@login_required
@csrf_protect
@validate_input
@safe_endpoint
def api_osint_usernames():
    """Genera username candidates da nome+cognome+anno."""
    data = request.get_json() or {}
    nome = (data.get("nome") or "").strip()
    cognome = (data.get("cognome") or "").strip()
    anno = (data.get("anno") or "").strip()
    nickname = (data.get("nickname") or "").strip()
    max_results = min(int(data.get("max_results", 80)), 200)

    if not nome and not cognome and not nickname:
        return jsonify({"error": "almeno un campo (nome/cognome/nickname) richiesto"}), 400

    usernames = generate_username_variants(
        nome=nome, cognome=cognome, anno=anno,
        nickname=nickname, max_results=max_results,
    )
    return jsonify({
        "input": {"nome": nome, "cognome": cognome, "anno": anno, "nickname": nickname},
        "count": len(usernames),
        "usernames": usernames,
    })


@app.route("/api/osint/social-sites")
@login_required
@validate_input
@safe_endpoint
def api_osint_social_sites():
    """Lista dei siti supportati per social check."""
    return jsonify({
        "sites": [
            {"name": name, "category": cfg.get("category", ""),
             "url_pattern": cfg["url"]}
            for name, cfg in SOCIAL_SITES.items()
        ],
        "total": len(SOCIAL_SITES),
    })


@app.route("/api/osint/social-check", methods=["POST"])
@login_required
@csrf_protect
@rate_limit(max_requests=30, window_sec=60)
@validate_input
@safe_endpoint
def api_osint_social_check():
    """Sherlock-style: controlla username su 20+ siti."""
    data = request.get_json() or {}
    username = (data.get("username") or "").strip()
    if not username or len(username) < 3:
        return jsonify({"error": "username required (min 3 chars)"}), 400

    sites = data.get("sites")  # opzionale: lista nomi siti
    timeout = float(data.get("timeout", 8.0))

    try:
        result = check_username_on_socials(username, sites=sites, timeout=timeout)
        return jsonify(result)
    except Exception as e:
        return jsonify({"error": str(e)[:200]}), 500


@app.route("/api/osint/enrich-features", methods=["POST"])
@login_required
@csrf_protect
@rate_limit(max_requests=30, window_sec=60)
@validate_input
@safe_endpoint
def api_osint_enrich_features():
    """Auto-enrichment: prende features e aggiunge OSINT tokens.

    Strategia:
      1. Per ogni telefono → estrai operatore/last4/last6
      2. Per ogni keyword → cerca match con città IT
      3. Da ogni nome combinato con anno → genera username candidates
      4. Cerca email nei messaggi del canale (se passato channel) → estrai pattern

    Returns features arricchite con campi extra:
      - osint_phones: lista metadata per ogni telefono
      - osint_locations: città trovate
      - osint_usernames: username candidates
      - osint_emails: email enrichite
      - osint_added_tokens: lista tokens da aggiungere alla wordlist
    """
    data = request.get_json() or {}
    features = data.get("features", {}) or {}
    channel_id = data.get("channel")

    osint_info: dict = {}
    new_tokens: list[str] = []

    # 1. Phone enrichment
    phone_results = []
    for phone in features.get("phones", []):
        info = enrich_phone(phone)
        info["password_tokens"] = password_tokens_from_phone(phone)
        phone_results.append(info)
        new_tokens.extend(info["password_tokens"])
    osint_info["phones"] = phone_results

    # 2. Locations from keywords + channel text
    text_for_loc = " ".join(features.get("keywords", []) + features.get("names", []))
    if channel_id:
        channel_dir = resolve_channel_dir(channel_id)
        if channel_dir is None:
            return jsonify({"error": "channel not found"}), 404
        msg_file = channel_dir / "messages.json"
        if msg_file.exists():
            try:
                msgs = load_messages_cached(channel_dir)
                text_for_loc += " " + " ".join(
                    m.get("message", "") for m in msgs[:500]  # cap to avoid heavy
                    if m.get("_") == "Message"
                )
            except Exception:
                pass

    locations = find_locations(text_for_loc)
    osint_info["locations"] = locations
    new_tokens.extend(password_tokens_from_locations(locations))

    # 3. Username candidates from names + dates (anno nascita)
    usernames: list[str] = []
    names = features.get("names", [])[:5]
    years = features.get("dates", [])[:3] + features.get("ages_birth_years", [])[:3]
    years_clean = [y for y in years if str(y).isdigit() and len(str(y)) == 4]
    if names:
        primary = names[0]
        secondary = names[1] if len(names) > 1 else ""
        for year in years_clean[:2] + [""]:  # also without year
            usernames.extend(generate_username_variants(
                nome=primary, cognome=secondary,
                anno=year, max_results=30,
            ))
    osint_info["usernames"] = list(dict.fromkeys(usernames))[:60]
    new_tokens.extend(osint_info["usernames"])

    # 4. Emails from channel
    osint_info["emails"] = []
    if channel_id:
        channel_dir = resolve_channel_dir(channel_id)
        if channel_dir is None:
            return jsonify({"error": "channel not found"}), 404
        msg_file = channel_dir / "messages.json"
        if msg_file.exists():
            try:
                msgs = load_messages_cached(channel_dir)
                full_text = " ".join(
                    m.get("message", "") for m in msgs
                    if m.get("_") == "Message"
                )
                emails = extract_emails(full_text)
                if emails:
                    enriched = [enrich_email(e) for e in emails]
                    osint_info["emails"] = enriched
                    new_tokens.extend(password_tokens_from_emails(emails))
            except Exception:
                pass

    # Dedupe new tokens preserve order
    seen: set[str] = set()
    osint_info["added_tokens"] = [
        t for t in new_tokens
        if t and not (t.lower() in seen or seen.add(t.lower()))
    ]

    return jsonify(osint_info)


# ── OSINT Online Tools (Stage 3.5) ─────────────────────────────────────────

@app.route("/api/osint/whois", methods=["POST"])
@login_required
@csrf_protect
@rate_limit(max_requests=30, window_sec=60)
@validate_input
@safe_endpoint
def api_osint_whois():
    """WHOIS lookup."""
    data = request.get_json() or {}
    domain = (data.get("domain") or "").strip()
    if not domain:
        return jsonify({"error": "domain required"}), 400
    return jsonify(whois_lookup(domain))


@app.route("/api/osint/dns", methods=["POST"])
@login_required
@csrf_protect
@rate_limit(max_requests=30, window_sec=60)
@validate_input
@safe_endpoint
def api_osint_dns():
    """DNS records lookup."""
    data = request.get_json() or {}
    domain = (data.get("domain") or "").strip()
    if not domain:
        return jsonify({"error": "domain required"}), 400
    return jsonify(dns_lookup(domain))


@app.route("/api/osint/ip-geo", methods=["POST"])
@login_required
@csrf_protect
@rate_limit(max_requests=30, window_sec=60)
@validate_input
@safe_endpoint
def api_osint_ip_geo():
    """IP geolocation."""
    data = request.get_json() or {}
    ip = (data.get("ip") or "").strip()
    if not ip:
        return jsonify({"error": "ip required"}), 400
    return jsonify(ip_geolocation(ip))


@app.route("/api/osint/wayback", methods=["POST"])
@login_required
@csrf_protect
@rate_limit(max_requests=30, window_sec=60)
@validate_input
@safe_endpoint
def api_osint_wayback():
    """Wayback Machine search."""
    data = request.get_json() or {}
    query = (data.get("query") or "").strip()
    limit = min(int(data.get("limit", 20)), 100)
    if not query:
        return jsonify({"error": "query required"}), 400
    return jsonify(wayback_search(query, limit=limit))


@app.route("/api/osint/email-rep", methods=["POST"])
@login_required
@csrf_protect
@rate_limit(max_requests=30, window_sec=60)
@validate_input
@safe_endpoint
def api_osint_email_rep():
    """Email reputation via emailrep.io."""
    data = request.get_json() or {}
    email = (data.get("email") or "").strip()
    if "@" not in email:
        return jsonify({"error": "valid email required"}), 400
    return jsonify(email_reputation(email))


@app.route("/api/osint/github-user", methods=["POST"])
@login_required
@csrf_protect
@rate_limit(max_requests=30, window_sec=60)
@validate_input
@safe_endpoint
def api_osint_github_user():
    """GitHub user public info."""
    data = request.get_json() or {}
    username = (data.get("username") or "").strip()
    if not username:
        return jsonify({"error": "username required"}), 400
    return jsonify(github_user_info(username))


@app.route("/api/osint/reddit-user", methods=["POST"])
@login_required
@csrf_protect
@rate_limit(max_requests=30, window_sec=60)
@validate_input
@safe_endpoint
def api_osint_reddit_user():
    """Reddit user public info."""
    data = request.get_json() or {}
    username = (data.get("username") or "").strip()
    if not username:
        return jsonify({"error": "username required"}), 400
    return jsonify(reddit_user_info(username))


@app.route("/api/osint/codice-fiscale", methods=["POST"])
@login_required
@csrf_protect
@validate_input
@safe_endpoint
def api_osint_codice_fiscale():
    """Parser Codice Fiscale italiano (offline)."""
    data = request.get_json() or {}
    cf = (data.get("cf") or "").strip()
    text = (data.get("text") or "").strip()
    epoca = data.get("epoca", "auto")

    if cf:
        return jsonify(parse_codice_fiscale(cf, epoca=epoca))

    if text:
        codici = find_codici_fiscali(text)
        results = [parse_codice_fiscale(c) for c in codici]
        return jsonify({
            "found": codici,
            "count": len(codici),
            "parsed": results,
        })

    return jsonify({"error": "cf or text required"}), 400


if __name__ == "__main__":
    port = int(os.environ.get("HORCRUX_PORT", 5100))
    # Bind 0.0.0.0 per essere accessibile dalla LAN (override via HORCRUX_HOST)
    host = os.environ.get("HORCRUX_HOST", "0.0.0.0")
    logger.info(f"Listening on {host}:{port}")
    app.run(host=host, port=port, debug=False)
