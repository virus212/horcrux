"""Horcrux OSINT · Username generator (offline).

Dato nome, cognome, anno, genera username candidati realistici.
Pattern basati su username reali in leak DB pubblici.
"""

import re

# Common separators between name parts
SEPARATORS = ["", ".", "_", "-"]

# Numeric suffixes commonly appended to usernames
NUM_SUFFIXES = ["", "1", "01", "07", "21", "23", "69", "99", "00", "11", "22", "07"]


def _normalize_part(text: str) -> str:
    """Lowercase + strip non-alpha."""
    return re.sub(r"[^a-zàèìòùáéíóú]", "", text.lower())


def generate_username_variants(
    nome: str = "",
    cognome: str = "",
    anno: str = "",
    nickname: str = "",
    max_results: int = 80,
) -> list[str]:
    """Genera username candidates da nome+cognome+anno.

    Esempi (input: nome=Marco, cognome=Rossi, anno=1990):
        marco, rossi, marcorossi, marco_rossi, marco.rossi,
        m.rossi, mrossi, marcoros, marco90, rossi90,
        marcorossi90, marco1990, marco_90, mrossi_90,
        rossi_marco, marko, ...
    """
    n = _normalize_part(nome)
    c = _normalize_part(cognome)
    nick = _normalize_part(nickname)
    year_short = anno[-2:] if anno and len(anno) >= 2 else ""
    year_full = anno if anno and len(anno) == 4 and anno.isdigit() else ""

    seen: set[str] = set()
    out: list[str] = []

    def add(username: str):
        username = username.lower().strip()
        if not username or len(username) < 3 or len(username) > 24:
            return
        if username in seen:
            return
        seen.add(username)
        out.append(username)

    # Pure single forms
    if n:
        add(n)
        add(n.capitalize())
    if c:
        add(c)
        add(c.capitalize())
    if nick:
        add(nick)

    # nome+cognome combinations
    if n and c:
        for sep in SEPARATORS:
            for first, second in [(n, c), (c, n)]:
                add(f"{first}{sep}{second}")

        # initial+lastname / firstname+initial
        if len(n) > 0:
            for sep in SEPARATORS:
                add(f"{n[0]}{sep}{c}")
                add(f"{c}{sep}{n[0]}")

        # short+short combos
        if len(n) >= 3 and len(c) >= 3:
            add(n[:3] + c[:3])
            add(n[:4] + c[:4])

    # With year suffixes
    bases = []
    if n:
        bases.append(n)
    if c:
        bases.append(c)
    if n and c:
        bases.append(n + c)
        bases.append(n + "_" + c)
        bases.append(n + "." + c)
        bases.append(n[0] + c)  # mrossi
        bases.append(n + c[0])  # marcor

    for base in bases:
        if year_short:
            for sep in ["", "_", "."]:
                add(f"{base}{sep}{year_short}")
        if year_full:
            for sep in ["", "_", "."]:
                add(f"{base}{sep}{year_full}")
        for suffix in NUM_SUFFIXES:
            if suffix:
                add(f"{base}{suffix}")

    # With nickname
    if nick:
        if year_short:
            add(f"{nick}{year_short}")
            add(f"{nick}_{year_short}")
        if n:
            add(f"{nick}{n}")
            add(f"{n}{nick}")

    # Common variations: leet-light (no numbers)
    if n and len(n) >= 4:
        # Remove vowels
        no_vowels = re.sub(r"[aeiou]", "", n)
        if len(no_vowels) >= 3:
            add(no_vowels)
            if year_short:
                add(no_vowels + year_short)

    # Truncated / common nicknames
    if n and len(n) >= 6:
        add(n[:5])  # marco -> marc

    return out[:max_results]


def generate_email_candidates(
    nome: str = "",
    cognome: str = "",
    anno: str = "",
    domain: str = "gmail.com",
) -> list[str]:
    """Genera email candidate (utile per OSINT email enumeration)."""
    usernames = generate_username_variants(nome, cognome, anno, max_results=30)
    return [f"{u}@{domain}" for u in usernames]
