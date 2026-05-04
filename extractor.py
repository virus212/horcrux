#!/usr/bin/env python3
"""Horcrux · Feature Extractor.

Wrapper su TextAnalyzer. Mantiene l'interfaccia precedente per compatibilità
con web_app.py, ma ora carica anche i file aggregate prodotti dal nuovo TIH:
_users.json, _forward_map.json, _mentions_map.json (presenti se messaggi sono
stati estratti con la nuova versione di TheInvisibleHand).
"""

import json
import sys
from pathlib import Path

from text_analyzer import TextAnalyzer


def _load_json_safe(path: Path) -> dict:
    if not path.exists():
        return {}
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
        return data if isinstance(data, dict) else {}
    except (json.JSONDecodeError, OSError):
        return {}


def load_messages(channel_dir: Path, author_filter: str | None = None) -> list[dict]:
    """Load messages.json. `author_filter` accetta sia display_name (substring)
    sia author_uid esatto (es. tg:user:12345)."""
    path = channel_dir / "messages.json"
    with open(path, encoding="utf-8") as f:
        raw = json.load(f)
    msgs = [m for m in raw if m.get("_") == "Message"]
    if author_filter:
        if author_filter.startswith(("tg:", "wa:")):
            msgs = [m for m in msgs if m.get("author_uid") == author_filter]
        else:
            af = author_filter.lower()
            msgs = [m for m in msgs if af in m.get("user_display_name", "").lower()]
    return msgs


def load_aggregates(channel_dir: Path) -> dict:
    """Carica i file aggregate prodotti da TIH: users, forwards, mentions.
    Tutti opzionali — torna {} per quelli assenti."""
    return {
        "users": _load_json_safe(channel_dir / "_users.json"),
        "forwards": _load_json_safe(channel_dir / "_forward_map.json"),
        "mentions": _load_json_safe(channel_dir / "_mentions_map.json"),
    }


def extract_features(channel_dir: Path, author_filter: str | None = None) -> dict:
    """Run pipeline TextAnalyzer + arricchimento da aggregates."""
    msgs = load_messages(channel_dir, author_filter)
    aggregates = load_aggregates(channel_dir)
    analyzer = TextAnalyzer(msgs, aggregates=aggregates, author_filter=author_filter)
    return analyzer.extract_features()


def get_analyzer(channel_dir: Path, author_filter: str | None = None) -> TextAnalyzer:
    """Get configured analyzer for a channel (search, co-occurrences)."""
    msgs = load_messages(channel_dir, author_filter)
    aggregates = load_aggregates(channel_dir)
    return TextAnalyzer(msgs, aggregates=aggregates, author_filter=author_filter)


if __name__ == "__main__":
    if len(sys.argv) < 2:
        print("Usage: extractor.py <channel_dir> [author_filter]", file=sys.stderr)
        sys.exit(1)
    af = sys.argv[2] if len(sys.argv) > 2 else None
    result = extract_features(Path(sys.argv[1]), af)
    print(json.dumps(result, ensure_ascii=False, indent=2))
