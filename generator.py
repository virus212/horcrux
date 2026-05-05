#!/usr/bin/env python3
"""Horcrux · Password Wordlist Generator with probabilistic ranking + topic patterns."""

import itertools
import json
import re
import sys

LEET_MAP = str.maketrans({
    'a': '4', 'A': '4', 'e': '3', 'E': '3', 'i': '1', 'I': '1',
    'o': '0', 'O': '0', 's': '5', 'S': '5', 'l': '1', 'L': '1', 't': '7', 'T': '7',
})

# Livello avanzato: include simboli + lettere extra (g, b, z, q)
LEET_MAP_ADVANCED = str.maketrans({
    'a': '@', 'A': '@', 'e': '3', 'E': '3', 'i': '1', 'I': '1',
    'o': '0', 'O': '0', 's': '$', 'S': '$', 'l': '1', 'L': '1', 't': '+', 'T': '+',
    'g': '9', 'G': '9', 'b': '8', 'B': '8', 'z': '2', 'Z': '2', 'q': '9', 'Q': '9',
})

# Password piu' comuni (top da rockyou/SecLists) — escluse di default per evitare rumore
COMMON_PASSWORDS_TOP: frozenset[str] = frozenset({
    # Top 50 SecLists / rockyou
    "password", "123456", "12345678", "1234567890", "qwerty", "abc123",
    "monkey", "letmein", "dragon", "111111", "baseball", "iloveyou",
    "trustno1", "1234567", "sunshine", "master", "123123", "welcome",
    "shadow", "ashley", "football", "jesus", "michael", "ninja",
    "mustang", "password1", "admin", "passw0rd", "qwerty123", "1q2w3e4r",
    "qwertyuiop", "12345", "1qaz2wsx", "zxcvbnm", "asdfghjkl", "qwert",
    "abcd1234", "tinkle", "iloveu", "p@ssw0rd", "qweasd", "qwe123",
    "test", "test123", "guest", "user", "root", "toor", "system",
    "pass", "pass123",
    # Italian common
    "amore", "ciao", "mamma", "casa", "italia", "juventus", "milan",
    "roma", "napoli", "inter", "ferrari", "amoremio", "tiamo", "ciaociao",
    # Numeric patterns
    "00000000", "11111111", "12121212", "55555555", "010101", "121212",
    "112233", "987654", "00000", "99999",
})


SUFFIXES_EASY = ["1", "123", "!", "2024", "2025"]
SUFFIXES_MEDIUM = SUFFIXES_EASY + ["#", "@", "01", "99", "12", ".", "!!", "2023"]
SUFFIXES_HARD = SUFFIXES_MEDIUM + ["007", "69", "1234", "2022", "2021", "321", "555",
                                    "00", "11", "22", "33", "44", "666", "888"]


# ── Italian dialect / texting slang ──────────────────────────────────────────
# Trasformazioni canoniche → varianti dialettali / abbreviate tipiche del
# texting italiano (chat, social, sms). Differenziatore vs CUPP/Mentalist
# che lavorano solo in inglese o con sostituzioni leet generiche.
IT_DIALECT_MAP: dict[str, list[str]] = {
    # Pronomi/congiunzioni più frequenti
    "che":      ["ke", "k", "kè"],
    "perché":   ["xké", "xke", "xkè"],
    "perche":   ["xke", "xché"],
    "per":      ["x", "xr"],
    "non":      ["nn", "nun"],
    "anche":    ["anke", "ank"],
    "ancora":   ["ank"],
    "comunque": ["cmq", "cmnq"],
    "quello":   ["kel", "kuello"],
    "questo":   ["kst", "kuesto", "qst"],
    "qualcuno": ["qlk", "qualk"],
    "qualche":  ["qlc"],
    "qualcosa": ["qlks"],
    "come":     ["kome", "kom"],
    "essere":   ["ess"],
    # Verbi essere/avere comuni
    "sei":      ["6"],
    "tu sei":   ["tu6"],
    "ci sei":   ["c6"],
    "hai":      ["ai"],
    # Quantificatori/avverbi
    "tutto":    ["tt", "tuto"],
    "niente":   ["nient", "nada"],
    "molto":    ["mlt"],
    "troppo":   ["trp"],
    # Casa/luoghi
    "casa":     ["kasa", "caza"],
    # Affettivi (importanti per pwd)
    "amore":    ["amo", "amor"],
    "tesoro":   ["teso"],
    "bacio":    ["bax", "ba6"],
    "baci":     ["bx"],
    # Saluti
    "ciao":     ["ciaoo", "cia"],
    "buongiorno": ["bgg", "bg"],
    "buonanotte": ["bn", "bnotte"],
    # Frasi affettive abbreviate (multi-token, sostituzione esatta)
    "ti voglio bene":    ["tvb"],
    "ti voglio un mondo di bene": ["tvumdb"],
    "ti amo":            ["ta", "tamo"],
    # Uni/lavoro
    "università": ["uni"],
    "universita": ["uni"],
    "lavoro":     ["lav"],
    # Cose/cibo
    "cose":     ["kose"],
    "cosa":     ["kosa"],
    "grazie":   ["grz", "thx"],
    "scusa":    ["sc", "scz"],
    # English borrows
    "love":     ["lov", "lv"],
}


def _dialect_variants(word: str) -> list[str]:
    """Genera varianti slang/dialect per un token italiano.

    Sostituisce ogni chiave di IT_DIALECT_MAP che compare nel token con le
    sue varianti. Lista deduplicata (case-insensitive). Vuota se nessuna chiave
    matcha — la chiamata e' a costo prossimo a zero.

    Esempi:
      "che"        -> ["ke", "k", "kè"]
      "perchécasa" -> ["xkékasa", "xkecasa", "xkècasa", "perchékasa", ...]
      "marco"      -> []
    """
    if not word or len(word) < 2:
        return []
    word_l = word.lower()
    variants: set[str] = set()
    for key, repls in IT_DIALECT_MAP.items():
        if key in word_l:
            for repl in repls:
                v = word_l.replace(key, repl)
                if v and v != word_l and len(v) >= 2:
                    variants.add(v)
    return sorted(variants)


# ── Probabilistic ranking config ─────────────────────────────────────────────
# Score base per categoria (0-1, alto = più probabile in pwd reali)
CATEGORY_BASE_SCORE = {
    "leaked_passwords": 0.98,  # password citate direttamente nel testo (jackpot)
    "names":            0.95,
    "ner_persons":      0.92,  # NER pre-estratto: piu' affidabile dei nomi heuristic
    "nicknames":        0.85,
    "animals":          0.85,
    "ages_birth_years": 0.85,
    "dates":            0.80,
    "gps_cities":       0.78,  # citta' visitate dal target via EXIF foto
    "brands":           0.70,
    "ner_orgs":         0.65,  # organizzazioni menzionate
    "ner_locations":    0.62,  # luoghi menzionati nei messaggi
    "phones":           0.60,
    "mentions":         0.58,  # persone nominate spesso
    "topics":           0.55,
    "emoji_keywords":   0.52,  # parole tradotte da emoji frequenti
    "keywords":         0.50,
    "forward_topics":   0.45,  # canali da cui forwarda
    "numbers":          0.40,
    "emojis":           0.30,
}

# Multiplier per tipo di mutazione (0-1)
MUTATION_DECAY = {
    "original":      1.00,
    "title":         0.95,
    "lower":         0.92,
    "upper":         0.78,
    "leet_full":     0.62,
    "leet_partial":  0.72,
    "suffix_short":  0.88,
    "suffix_long":   0.78,
    "prefix":        0.65,
    "reverse":       0.32,
    "combo_2":       0.75,
    "combo_3":       0.50,
    "topic_match":   0.82,
    "manual":        0.92,
}


# ── Topic-driven patterns ───────────────────────────────────────────────────
# Pattern tipici per ogni topic, applicati a nomi/nickname quando topic detected
TOPIC_SUFFIXES = {
    "gaming": ["TTV", "_yt", "Pro", "69", "_gg", "_lol", "Noob",
               "_ttv", "Gamer", "_main", "_alt"],
    "musica": ["Music", "_dj", "Beats", "_fm", "_live", "_band",
               "Sound", "Records"],
    "sport": [str(i) for i in (7, 9, 10, 11, 23, 99, 1, 14)],  # numeri maglia famosi
    "tech":  ["_dev", "_code", "Hacker", "404", "_admin", "_root",
              "Coder", "_h4ck"],
    "studio": ["_uni", "Student", "_lab", "Phd", "_grad"],
    "amore": ["love", "ForEver", "Amormio", "4ever", "_heart", "_xoxo"],
    "cibo":  [],
    "viaggio": ["_trip", "Wanderlust", "_world", "_travel"],
}

TOPIC_PREFIXES = {
    "gaming": ["xX", "Lord", "TheReal"],
    "amore":  ["my", "love_"],
    "tech":   ["dev_", "root_"],
}


# ── Helpers ─────────────────────────────────────────────────────────────────
def _case_variants(word: str) -> list[str]:
    variants = {word, word.lower(), word.upper(), word.capitalize()}
    if " " in word:
        parts = word.split()
        variants.add("".join(p.capitalize() for p in parts))
    return list(variants)


def _leet(word: str, level: str = "base") -> str:
    """Applica leet substitution. `level` puo' essere 'base' (solo cifre)
    oppure 'advanced' (include @, $, +, 9, 8, 2 per a/s/t/g/b/z)."""
    if level == "advanced":
        return word.translate(LEET_MAP_ADVANCED)
    return word.translate(LEET_MAP)


def _validate(pw: str) -> tuple[bool, str]:
    if len(pw) < 6:
        return False, "too_short"
    if len(pw) > 24:
        return False, "too_long"
    if re.match(r"^\d+$", pw) and len(pw) <= 7:
        return False, "all_digits_short"
    return True, ""


def _is_valid(pw: str) -> bool:
    return _validate(pw)[0]


# ── Token scoring engine ─────────────────────────────────────────────────────
def _build_token_scores(features: dict, manual_keys: list[str]) -> dict[str, float]:
    """Map token_lowercase → score basato su categoria + posizione."""
    scores: dict[str, float] = {}

    for category, base in CATEGORY_BASE_SCORE.items():
        items = features.get(category, [])
        if isinstance(items, dict):
            items = list(items.keys())
        if not items:
            continue
        n = max(len(items), 8)
        for i, item in enumerate(items):
            # leaked_passwords: niente position decay — sono tutti candidati
            # di pari (massima) priorità, l'ordine in lista è solo frequenza
            # di citazione, non confidence.
            if category == "leaked_passwords":
                score = base
            else:
                # Position penalty: primo posto 0%, ultimo 35%
                pos_decay = 1.0 - (i / n) * 0.35
                score = base * pos_decay
            key = str(item).lower().strip()
            if key:
                scores[key] = max(scores.get(key, 0), score)

    # Manual keys: alta priorità (user-curated)
    for k in manual_keys:
        kk = str(k).lower().strip()
        if kk:
            scores[kk] = max(scores.get(kk, 0), 0.92)

    return scores


def _score_password(pw: str, token_scores: dict[str, float]) -> float:
    """Score di una password basato su token contained + mutation pattern."""
    pw_lower = pw.lower()
    best_score = 0.0

    for token, base_score in token_scores.items():
        if not token or len(token) < 2:
            continue
        if token not in pw_lower:
            continue

        # Identifica tipo di mutazione
        if pw == token:
            mut = "original"
        elif pw.lower() == token:
            mut = "lower"
        elif pw == token.capitalize():
            mut = "title"
        elif pw == token.upper():
            mut = "upper"
        elif pw == token[::-1] or pw.lower() == token[::-1]:
            mut = "reverse"
        elif _leet(token) == pw_lower or _leet(token) == pw:
            mut = "leet_full"
        elif any(c in pw for c in "0413578") and token in pw_lower:
            mut = "leet_partial"
        else:
            # Probabile combo o suffix/prefix
            ratio = len(pw) / max(len(token), 1)
            if ratio > 2.5:
                mut = "combo_3"
            elif ratio > 1.6:
                mut = "combo_2"
            elif pw.lower().startswith(token):
                mut = "suffix_short" if len(pw) - len(token) <= 4 else "suffix_long"
            elif pw.lower().endswith(token):
                mut = "prefix"
            else:
                mut = "combo_2"

        decay = MUTATION_DECAY.get(mut, 0.5)
        score = base_score * decay

        if score > best_score:
            best_score = score

    return best_score


# ── Smart combos ─────────────────────────────────────────────────────────────
def _smart_name_year_combos(names: list[str], years: list[str]) -> list[str]:
    """Combinazioni nome+anno realistiche (Marco90, marco_1990, M90, ecc.)."""
    combos = []
    for name in names[:10]:
        if not name or len(name) < 2:
            continue
        for year in years:
            year_str = str(year).strip()
            if not year_str.isdigit():
                continue
            full = year_str
            short = year_str[-2:] if len(year_str) >= 2 else year_str

            for case_name in [name, name.lower(), name.upper(), name.capitalize()]:
                combos.append(f"{case_name}{full}")
                combos.append(f"{case_name}{short}")
                combos.append(f"{case_name}_{full}")
                combos.append(f"{case_name}_{short}")
                combos.append(f"{case_name}.{full}")
                combos.append(f"{case_name}.{short}")
                combos.append(f"{full}{case_name}")
                combos.append(f"{short}{case_name}")

            if len(name) >= 1:
                init = name[0]
                combos.append(f"{init.upper()}{full}")
                combos.append(f"{init.upper()}{short}")
                combos.append(f"{init.lower()}{full}")
                combos.append(f"{init.lower()}{short}")

    return combos


def _topic_pattern_combos(names: list[str], nicknames: list[str], topics: dict) -> list[str]:
    """Genera password con pattern tipici del topic detected."""
    combos = []
    if not topics:
        return combos

    base_tokens = list(names[:5]) + list(nicknames[:3])
    detected_topics = list(topics.keys()) if isinstance(topics, dict) else list(topics)

    for token in base_tokens:
        if not token or len(token) < 2:
            continue
        for topic in detected_topics:
            # Suffix patterns
            for suffix in TOPIC_SUFFIXES.get(topic, []):
                combos.append(f"{token.capitalize()}{suffix}")
                combos.append(f"{token.lower()}{suffix.lower()}")
                # Anche con anno
                combos.append(f"{token.capitalize()}{suffix}99")
            # Prefix patterns
            for prefix in TOPIC_PREFIXES.get(topic, []):
                combos.append(f"{prefix}{token.capitalize()}")
                combos.append(f"{prefix}{token.lower()}")
                # Wrapped (xXMarcoXx style)
                if prefix == "xX":
                    combos.append(f"xX{token.capitalize()}Xx")

    return combos


# ── Main generation ──────────────────────────────────────────────────────────
def generate_wordlist(
    features: dict,
    level: str = "medium",
    manual_keys: list[str] | None = None,
    return_stats: bool = False,
    sort_by_score: bool = True,
    leet_level: str = "auto",
    exclude_common: bool = True,
    exclude_extra: set[str] | list[str] | None = None,
    use_ml: bool = False,
    ml_weight: float = 0.4,
) -> list[str] | tuple[list[str], dict]:
    """Generate wordlist with optional probabilistic ranking.

    sort_by_score: ordina la wordlist per probability desc (top = più realistiche).
    return_stats: include drop_stats nella response.
    leet_level: 'off', 'base', 'advanced', 'auto' (deduce da level).
    exclude_common: filtra le password top piu' comuni (rockyou/seclists). Default True.
    exclude_extra: set/list aggiuntivo di password da escludere (es. wordlist user-uploaded).
                   Match case-insensitive sulla forma normalizzata.

    use_ml: se True, attiva PassGPT hybrid (Mode C) — aggiunge candidati ML
            condizionati sui top tokens + ri-ordina con log-likelihood PassGPT.
            Costo prima call: caricamento modello ~5-10s. Successive: ~5-15s.
    ml_weight: peso ML nello score combinato (0=solo rule, 1=solo ML). 0.4 default.
    """
    # Risolvi leet_level=auto in base al livello difficolta'
    if leet_level == "auto":
        leet_level = {"easy": "off", "medium": "base", "hard": "advanced"}.get(level, "base")
    manual_keys = manual_keys or []
    drop_stats = {
        "too_short": 0, "too_long": 0, "all_digits_short": 0,
        "duplicate": 0, "common": 0, "user_excluded": 0,
    }

    # Build base tokens
    base_tokens: list[str] = []
    base_tokens += features.get("leaked_passwords", [])[:15]
    base_tokens += features.get("names", [])[:15]
    base_tokens += [d.replace("/", "").replace("-", "").replace(".", "")
                    for d in features.get("dates", [])[:10]]
    base_tokens += features.get("numbers", [])[:10]
    base_tokens += features.get("phones", [])[:8]
    base_tokens += features.get("ages_birth_years", [])[:8]
    base_tokens += features.get("animals", [])[:10]
    base_tokens += features.get("brands", [])[:10]
    base_tokens += features.get("nicknames", [])[:8]
    base_tokens += features.get("keywords", [])[:20]
    for phrase in features.get("phrases", [])[:5]:
        for word in phrase.split():
            if len(word) >= 3:
                base_tokens.append(word)
    topics = features.get("topics", {})
    if isinstance(topics, dict):
        base_tokens += list(topics.keys())
    elif isinstance(topics, list):
        base_tokens += topics
    base_tokens += manual_keys

    # Dedupe preserve order
    seen = set()
    tokens = []
    for t in base_tokens:
        t = str(t).strip()
        if t and t.lower() not in seen:
            seen.add(t.lower())
            tokens.append(t)

    seen_pw: set[str] = set()
    result: list[str] = []

    extra_set = {str(w).strip().lower() for w in (exclude_extra or []) if str(w).strip()}

    def _add(pw: str):
        pw = pw.strip()
        if pw in seen_pw:
            drop_stats["duplicate"] += 1
            return
        ok, reason = _validate(pw)
        if not ok:
            drop_stats[reason] += 1
            return
        pw_low = pw.lower()
        if exclude_common and pw_low in COMMON_PASSWORDS_TOP:
            drop_stats["common"] += 1
            return
        if pw_low in extra_set:
            drop_stats["user_excluded"] += 1
            return
        seen_pw.add(pw)
        result.append(pw)

    # Leaked passwords: candidati diretti (sono gia' password literal trovate
    # nel testo). Inseriti per primi cosi' nel sort-by-score finiscono in cima.
    # Bypassa `all_digits_short` perche' un PIN tipo 4815 e' esattamente cio'
    # che ci e' stato detto essere la password.
    def _add_leaked(pw: str) -> None:
        pw = pw.strip()
        if not pw or len(pw) > 30 or pw in seen_pw:
            if pw in seen_pw:
                drop_stats["duplicate"] += 1
            return
        pw_low = pw.lower()
        if exclude_common and pw_low in COMMON_PASSWORDS_TOP:
            drop_stats["common"] += 1
            return
        if pw_low in extra_set:
            drop_stats["user_excluded"] += 1
            return
        seen_pw.add(pw)
        result.append(pw)

    for pw in features.get("leaked_passwords", [])[:30]:
        _add_leaked(pw)
        if pw.lower() != pw:
            _add_leaked(pw.lower())
        # Variante con suffix base — l'utente potrebbe averla ruotata
        for s in ("1", "!", "2024", "2025"):
            _add(pw + s)

    # Smart combos (always)
    names = features.get("names", [])[:10]
    years = features.get("dates", [])[:10] + features.get("ages_birth_years", [])
    years_clean = [y for y in years if str(y).isdigit() and len(str(y)) in (2, 4)]
    for pw in _smart_name_year_combos(names, years_clean):
        _add(pw)

    # Topic-driven patterns (always - leverages detected interests)
    nicknames = features.get("nicknames", [])[:5]
    for pw in _topic_pattern_combos(names, nicknames, topics):
        _add(pw)

    # Italian dialect mutations (medium/hard only — espandono significativamente
    # la wordlist con slang testuale tipico IT come ke/x/cmq/kasa che CUPP non
    # genera). Cap a 40 token per evitare esplosione combinatoria.
    if level in ("medium", "hard"):
        dialect_suffixes = SUFFIXES_MEDIUM if level == "medium" else SUFFIXES_HARD
        for token in tokens[:40]:
            for v in _dialect_variants(token):
                _add(v)
                _add(v.capitalize())
                if level == "hard":
                    _add(v.upper())
                for s in dialect_suffixes[:5]:
                    _add(v + s)
                    if level == "hard":
                        _add(v.capitalize() + s)

    # Standard mutations per livello
    if level == "easy":
        suffixes = SUFFIXES_EASY
        for token in tokens:
            for variant in _case_variants(token):
                _add(variant)
                for s in suffixes:
                    _add(variant + s)
            # Leet anche su easy se l'utente lo richiede esplicitamente
            if leet_level not in ("off", "auto"):
                leet = _leet(token, leet_level)
                if leet != token:
                    _add(leet)

    elif level == "medium":
        suffixes = SUFFIXES_MEDIUM
        for token in tokens:
            for variant in _case_variants(token):
                _add(variant)
                for s in suffixes:
                    _add(variant + s)
            if leet_level != "off":
                leet = _leet(token, leet_level)
                if leet != token:
                    _add(leet)
                    for s in suffixes[:5]:
                        _add(leet + s)

        for a, b in itertools.combinations(tokens[:8], 2):
            _add(a.capitalize() + b.capitalize())
            _add(a.lower() + b.lower())
            _add(a + "_" + b)

    else:  # hard
        suffixes = SUFFIXES_HARD
        for token in tokens:
            for variant in _case_variants(token):
                _add(variant)
                for s in suffixes:
                    _add(variant + s)
                    _add(s + variant)
            if leet_level != "off":
                leet = _leet(token, leet_level)
                if leet != token:
                    _add(leet)
                    for variant in _case_variants(leet):
                        _add(variant)
                        for s in suffixes[:6]:
                            _add(variant + s)
            _add(token[::-1])
            _add(token.lower()[::-1])
        for a, b in itertools.combinations(tokens[:12], 2):
            _add(a.capitalize() + b.capitalize())
            _add(a.lower() + b.lower())
            _add(a + b)
            _add(b + a)
            _add(a + "_" + b)
            for s in suffixes[:3]:
                _add(a.capitalize() + s + b.capitalize())
        for a, b, c in itertools.combinations(tokens[:5], 3):
            _add(a.capitalize() + b.capitalize() + c.capitalize())

    # ── ML Augmentation (PassGPT hybrid Mode C) ──────────────────────────
    ml_scores: dict[str, float] = {}
    if use_ml:
        import logging as _lg
        _ml_log = _lg.getLogger("horcrux.ml")
        _ml_log.info("PassGPT hybrid mode active")
        try:
            import ml_generator as mlg
            if mlg.is_available():
                # Genera prompts dai top token (lowercase per PassGPT char-level)
                ml_prompts: list[str] = []
                for cat in ("names", "ner_persons", "nicknames"):
                    for v in features.get(cat, [])[:5]:
                        if v and len(str(v)) >= 2:
                            ml_prompts.append(str(v).lower()[:8])
                for cat in ("ages_birth_years", "dates"):
                    for v in features.get(cat, [])[:5]:
                        s = str(v).strip()
                        if s.isdigit():
                            ml_prompts.append(s)
                ml_prompts = list(dict.fromkeys(ml_prompts))[:12]  # dedup + cap

                # 1. Aggiungi candidati ML al pool
                ml_candidates = mlg.generate_conditional(ml_prompts, samples_per_prompt=12)
                _ml_log.info(f"PassGPT generated {len(ml_candidates)} candidates, adding to pool")
                for pw in ml_candidates:
                    _add(pw)

                # 2. Score ALL passwords (rule + ML candidates) con log-lik PassGPT
                if sort_by_score and result:
                    ml_scores = mlg.score_passwords(result)
                    _ml_log.info(f"PassGPT scored {len(ml_scores)}/{len(result)} passwords")
        except Exception as e:
            _ml_log.warning(f"PassGPT augmentation skipped: {e}")
            ml_scores = {}

    # Probabilistic ranking — eventualmente hybrid con ML
    if sort_by_score and result:
        token_scores = _build_token_scores(features, manual_keys)
        if ml_scores:
            # Hybrid: combina rule-based score con ML log-likelihood
            mw = max(0.0, min(1.0, ml_weight))
            scored = [
                (pw,
                 mw * ml_scores.get(pw, 0.0)
                 + (1 - mw) * _score_password(pw, token_scores))
                for pw in result
            ]
        else:
            scored = [(pw, _score_password(pw, token_scores)) for pw in result]
        scored.sort(key=lambda x: -x[1])
        result = [pw for pw, _ in scored]

    if return_stats:
        return result, drop_stats
    return result


def count_only(features: dict, level: str = "medium", manual_keys: list[str] | None = None,
               leet_level: str = "auto", exclude_common: bool = True,
               exclude_extra: list[str] | None = None) -> int:
    """Fast count, skip scoring (no sort). Accetta gli stessi modificatori di
    `generate_wordlist` cosi' il preview riflette i toggle Smart Wizard."""
    res = generate_wordlist(
        features, level=level, manual_keys=manual_keys, sort_by_score=False,
        leet_level=leet_level, exclude_common=exclude_common, exclude_extra=exclude_extra,
    )
    return len(res) if isinstance(res, list) else len(res[0])


if __name__ == "__main__":
    if len(sys.argv) < 2:
        print("Usage: generator.py <features_json>", file=sys.stderr)
        sys.exit(1)
    try:
        with open(sys.argv[1]) as f:
            features = json.load(f)
        level = sys.argv[2] if len(sys.argv) > 2 else "medium"
        wordlist = generate_wordlist(features, level=level)
        for pw in wordlist:
            print(pw)
    except Exception as e:
        print(f"Error: {e}", file=sys.stderr)
        sys.exit(1)
