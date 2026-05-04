"""Horcrux OSINT · Traduttore emoji → parole IT/EN.

Le emoji da sole non sono usate in password (la maggior parte dei sistemi
non le accetta), ma il significato che trasportano sì. Esempio: target che
riceve molti ⚽ → tifoso di calcio → "calcio", "football", "interfan",
"juventus" ecc. diventano candidati password.

Dataset minimal ma curato: copre le emoji piu' indicative di topic/interessi.
Per emoji non mappate, ritorniamo lista vuota (no rumore).
"""
from __future__ import annotations

# ── Mappatura emoji → keyword di topic/interesse (IT + EN) ──────────────────
EMOJI_TO_WORDS: dict[str, list[str]] = {
    # ── Sport ──
    "⚽": ["calcio", "football", "soccer", "pallone"],
    "🏀": ["basket", "basketball", "nba"],
    "⚾": ["baseball", "mlb"],
    "🎾": ["tennis", "atp", "wta"],
    "🏐": ["volley", "pallavolo"],
    "🏈": ["football", "nfl", "americano"],
    "🏒": ["hockey", "puck"],
    "🏓": ["pingpong", "tabletennis"],
    "🏸": ["badminton"],
    "🥊": ["boxe", "boxing", "boxer"],
    "🏆": ["trofeo", "trophy", "champion", "winner"],
    "🥇": ["oro", "gold", "winner"],
    "🏅": ["medal", "medaglia"],
    "⛹": ["sport", "athlete"],
    "🏇": ["horseracing", "ippica"],
    "🏌": ["golf"],
    "🏊": ["nuoto", "swim", "swimming"],
    "🚴": ["bike", "cycling", "ciclismo"],
    "🏃": ["running", "corsa", "runner"],
    "🤸": ["ginnastica", "gymnastics"],

    # ── Musica ──
    "🎵": ["music", "musica", "song"],
    "🎶": ["music", "musica", "song", "melody"],
    "🎸": ["chitarra", "guitar", "rock"],
    "🎹": ["piano", "pianoforte"],
    "🥁": ["drums", "batteria"],
    "🎤": ["mic", "singer", "cantante", "karaoke"],
    "🎧": ["headphones", "cuffie", "music", "dj"],
    "🎺": ["trumpet", "tromba"],
    "🎻": ["violin", "violino"],
    "🎷": ["sax", "saxophone"],

    # ── Gaming / tech ──
    "🎮": ["gaming", "game", "videogame", "gamer"],
    "🕹": ["arcade", "joystick", "retro"],
    "♟": ["chess", "scacchi"],
    "🎰": ["casino", "slot", "jackpot"],
    "💻": ["pc", "computer", "laptop", "tech"],
    "🖥": ["pc", "computer", "monitor"],
    "⌨": ["keyboard", "tastiera"],
    "🖱": ["mouse"],
    "📱": ["phone", "smartphone", "mobile", "iphone"],
    "🤖": ["robot", "ai", "bot"],

    # ── Cinema / TV ──
    "🎬": ["cinema", "movie", "film", "director"],
    "🎥": ["camera", "video", "filmmaker"],
    "📺": ["tv", "television"],
    "🎭": ["theater", "teatro", "drama"],
    "🎨": ["arte", "art", "paint"],
    "🎤": ["mic", "singer", "rap"],

    # ── Cibo ──
    "🍕": ["pizza", "italia", "italy"],
    "🍔": ["burger", "fastfood", "mcdonald"],
    "🌭": ["hotdog"],
    "🍟": ["fries", "patatine"],
    "🌮": ["taco", "mexican"],
    "🍣": ["sushi", "japan"],
    "🍝": ["pasta", "spaghetti", "italia"],
    "🍦": ["gelato", "icecream"],
    "🍩": ["donut", "ciambella"],
    "🍫": ["cioccolato", "chocolate"],
    "🍷": ["vino", "wine"],
    "🍺": ["birra", "beer"],
    "🍸": ["cocktail", "martini"],
    "☕": ["caffe", "coffee", "espresso"],
    "🍵": ["te", "tea"],

    # ── Animali (boost se gia' in dict ANIMALS) ──
    "🐶": ["cane", "dog", "puppy"],
    "🐱": ["gatto", "cat", "kitten"],
    "🐭": ["topo", "mouse"],
    "🐹": ["criceto", "hamster"],
    "🐰": ["coniglio", "rabbit", "bunny"],
    "🦊": ["volpe", "fox"],
    "🐻": ["orso", "bear"],
    "🐼": ["panda"],
    "🦁": ["leone", "lion"],
    "🐯": ["tigre", "tiger"],
    "🐮": ["mucca", "cow"],
    "🐷": ["maiale", "pig", "porco"],
    "🐸": ["rana", "frog"],
    "🐵": ["scimmia", "monkey"],
    "🐔": ["gallina", "chicken"],
    "🐧": ["pinguino", "penguin"],
    "🐦": ["uccello", "bird"],
    "🐤": ["pulcino", "chick"],
    "🦅": ["aquila", "eagle"],
    "🦆": ["anatra", "duck"],
    "🦉": ["gufo", "owl"],
    "🐝": ["ape", "bee"],
    "🦋": ["farfalla", "butterfly"],
    "🐛": ["bruco", "caterpillar"],
    "🐠": ["pesce", "fish"],
    "🐬": ["delfino", "dolphin"],
    "🐳": ["balena", "whale"],
    "🐢": ["tartaruga", "turtle"],
    "🦄": ["unicorno", "unicorn"],
    "🐉": ["drago", "dragon"],
    "🦖": ["dino", "dinosaur", "trex"],

    # ── Cuore / amore ──
    "❤": ["amore", "love", "cuore", "heart"],
    "❤️": ["amore", "love", "cuore", "heart"],
    "💕": ["amore", "love", "kiss"],
    "💖": ["amore", "love", "sparkle"],
    "💗": ["amore", "love"],
    "💓": ["amore", "heart"],
    "💞": ["amore", "love"],
    "💝": ["amore", "gift", "regalo"],
    "💔": ["heartbreak", "ex"],
    "😍": ["love", "amore"],
    "😘": ["kiss", "bacio"],
    "💋": ["kiss", "bacio", "rossetto"],

    # ── Risate ──
    "😂": ["lol", "ahaha", "ridere", "laugh"],
    "🤣": ["lol", "rotfl", "laugh"],
    "😆": ["laugh", "ridere"],

    # ── Natura / viaggio ──
    "🌸": ["fiore", "flower", "sakura", "primavera"],
    "🌹": ["rosa", "rose", "fiore"],
    "🌻": ["girasole", "sunflower"],
    "🌳": ["albero", "tree", "natura"],
    "🌲": ["pino", "pine", "tree"],
    "🌴": ["palma", "palm", "vacanze"],
    "☀": ["sole", "sun", "estate"],
    "🌊": ["mare", "sea", "ocean", "wave"],
    "⛰": ["montagna", "mountain"],
    "🏔": ["montagna", "mountain", "alps"],
    "🗻": ["fuji", "montagna"],
    "✈": ["aereo", "plane", "viaggio", "travel"],
    "🚗": ["auto", "car"],
    "🏍": ["moto", "motorbike", "bike"],
    "🚲": ["bici", "bike", "bicycle"],
    "🚆": ["treno", "train"],
    "⛴": ["nave", "ship", "boat"],
    "🛳": ["nave", "cruise", "crociera"],
    "🌍": ["mondo", "world", "earth"],
    "🌎": ["mondo", "world", "americas"],
    "🌏": ["mondo", "world", "asia"],

    # ── Bandiere comuni IT/EN ──
    "🇮🇹": ["italia", "italy", "italian"],
    "🇺🇸": ["usa", "america"],
    "🇬🇧": ["uk", "england", "britain"],
    "🇪🇸": ["spagna", "spain", "espana"],
    "🇫🇷": ["francia", "france"],
    "🇩🇪": ["germania", "germany"],
    "🇯🇵": ["giappone", "japan"],

    # ── Religione ──
    "🙏": ["preghiera", "pray", "amen"],
    "✝": ["cristiano", "christian", "cross"],
    "☪": ["islam", "muslim"],
    "✡": ["judaism", "ebraico"],

    # ── Lavoro / studio ──
    "📚": ["libri", "books", "studio", "study"],
    "📖": ["libro", "book", "leggere"],
    "✏": ["penna", "pen", "scrivere", "study"],
    "🎓": ["laurea", "graduation", "uni"],
    "💼": ["lavoro", "work", "business"],
    "💰": ["soldi", "money", "cash"],
    "💵": ["dollar", "soldi"],
    "💸": ["money", "spend"],
    "💳": ["card", "carta"],
    "📈": ["trader", "trading", "stocks"],

    # ── Vibes ──
    "🔥": ["fuoco", "fire", "hot", "lit"],
    "💯": ["100", "perfect", "best"],
    "⚡": ["fulmine", "lightning", "speed", "energy"],
    "✨": ["sparkle", "magic", "stelle"],
    "🌟": ["stella", "star"],
    "⭐": ["stella", "star", "preferito"],
    "💎": ["diamante", "diamond", "gem"],
    "🎉": ["festa", "party", "celebration"],
    "🎊": ["festa", "party", "confetti"],
    "🎁": ["regalo", "gift", "present"],
    "🎂": ["compleanno", "birthday", "torta"],
    "🍾": ["champagne", "festa", "party"],
}


def emoji_to_keywords(emoji: str) -> list[str]:
    """Restituisce parole IT/EN associate all'emoji, lista vuota se non in mappa.

    Tenta anche di rimuovere variation selectors per matching robusto.
    """
    if not emoji:
        return []
    direct = EMOJI_TO_WORDS.get(emoji)
    if direct:
        return list(direct)
    # Strip variation selector U+FE0F (alcune emoji vengono salvate con o senza)
    stripped = emoji.replace("️", "")
    return list(EMOJI_TO_WORDS.get(stripped, []))


def expand_emoji_list(emojis: list[str], max_keywords: int = 30) -> list[str]:
    """Espande una lista di emoji in keyword uniche, ordinate per priorita'."""
    out: list[str] = []
    seen: set[str] = set()
    for emoji in emojis:
        for kw in emoji_to_keywords(emoji):
            if kw not in seen and len(out) < max_keywords:
                seen.add(kw)
                out.append(kw)
    return out
