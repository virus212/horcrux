#!/usr/bin/env python3
"""Horcrux · TextAnalyzer · Pipeline di analisi testo centralizzata.

Architettura:
  Tokenize → Normalize → Categorize → Score → Aggregate

Ogni token mantiene metadata completi (frequency, positions, sources, confidence)
per permettere classification accurata e debugging.
"""

import re
from collections import Counter
from dataclasses import dataclass, field
from datetime import datetime


# ═══════════════════════════════════════════════════════════════════════════
# DICTIONARIES (costanti riusabili)
# ═══════════════════════════════════════════════════════════════════════════

ANIMALS: frozenset[str] = frozenset({
    # Italian
    "cane", "gatto", "tigre", "leone", "aquila", "cobra", "serpente", "lupo",
    "volpe", "orso", "toro", "mucca", "cavallo", "coniglio", "topo", "ratto",
    "delfino", "balena", "squalo", "corvo", "gufo", "falco", "pappagallo", "panda",
    "koala", "gorilla", "scimmia", "elefante", "giraffa", "zebra", "ippopotamo",
    "rinoceronte", "coccodrillo", "tartaruga", "rana", "lucertola", "lepre", "cervo",
    "capra", "pecora", "maiale", "fenicottero", "pinguino", "cigno", "anatra",
    "gallina", "gallo", "piccione", "pantera", "giaguaro", "leopardo", "lince",
    "puma", "ghepardo", "polpo", "granchio", "salmone", "trota", "riccio",
    "castoro", "lontra", "tricheco", "foca", "drago",
    # English
    "dog", "cat", "tiger", "lion", "eagle", "snake", "wolf", "fox", "bear",
    "bull", "cow", "horse", "rabbit", "mouse", "rat", "dolphin", "whale",
    "shark", "crow", "owl", "hawk", "parrot", "monkey", "elephant", "giraffe",
    "hippo", "rhino", "crocodile", "turtle", "frog", "deer", "goat", "sheep",
    "pig", "swan", "duck", "chicken", "pigeon", "panther", "jaguar", "leopard",
    "lynx", "cheetah", "octopus", "crab", "salmon", "hedgehog", "beaver",
    "otter", "seal", "dragon", "phoenix", "unicorn",
})

STOPWORDS: frozenset[str] = frozenset({
    # Articoli
    "il", "lo", "la", "i", "gli", "le", "un", "uno", "una",
    # Preposizioni
    "di", "a", "da", "in", "con", "su", "per", "tra", "fra",
    "del", "dello", "della", "dei", "degli", "delle",
    "al", "allo", "alla", "ai", "agli", "alle",
    "dal", "dallo", "dalla", "dai", "dagli", "dalle",
    "nel", "nello", "nella", "nei", "negli", "nelle",
    "sul", "sullo", "sulla", "sui", "sugli", "sulle", "col", "coi",
    # Congiunzioni
    "e", "ed", "ma", "o", "od", "che", "se", "perché", "perche",
    "quindi", "dunque", "allora", "comunque", "tuttavia", "però", "pero",
    "anche", "ancora", "oppure", "ovvero", "cioè", "cioe", "infatti",
    "mentre", "quando", "dopo", "prima", "finché", "appena",
    # Pronomi
    "io", "tu", "lui", "lei", "noi", "voi", "loro", "egli", "ella",
    "essi", "esse", "me", "te", "ce", "ve", "ne", "ci", "vi", "mi", "ti", "si",
    "questo", "questa", "questi", "queste", "quello", "quella", "quelli", "quelle",
    "stesso", "stessa", "stessi", "stesse",
    # Possessivi
    "mio", "mia", "miei", "mie", "tuo", "tua", "tuoi", "tue",
    "suo", "sua", "suoi", "sue", "nostro", "nostra", "nostri", "nostre",
    "vostro", "vostra", "vostri", "vostre",
    # Indefiniti
    "ogni", "ognuno", "ognuna", "qualcuno", "qualcosa", "chiunque",
    "qualsiasi", "qualunque", "ciascuno", "altro", "altra", "altri", "altre",
    "tutto", "tutta", "tutti", "tutte", "molto", "molta", "molti", "molte",
    "poco", "poca", "pochi", "poche", "tanto", "tanta", "tanti", "tante",
    "troppo", "troppa", "troppi", "troppe", "alcuni", "alcune",
    "nessuno", "nessuna", "niente", "nulla",
    # Avverbi
    "non", "no", "sì", "si", "già", "gia", "mai", "sempre",
    "spesso", "ora", "adesso", "subito", "presto", "tardi", "ieri", "oggi", "domani",
    "qua", "qui", "là", "lì", "dove", "dovunque", "ovunque",
    "abbastanza", "quasi", "circa", "bene", "male", "meglio", "peggio",
    "così", "cosi", "come", "ecco", "appunto", "addirittura", "davvero",
    "veramente", "praticamente", "letteralmente", "assolutamente",
    "magari", "forse", "probabilmente", "sicuramente", "certamente",
    "proprio", "neanche", "neppure", "nemmeno", "solo", "soltanto",
    "soprattutto", "specialmente", "infine", "finalmente", "almeno",
    "perfino", "secondo", "tipo", "diciamo", "insomma",
    # Verbi essere
    "essere", "sono", "sei", "è", "siamo", "siete",
    "ero", "eri", "era", "eravamo", "eravate", "erano",
    "fui", "fosti", "fu", "fummo", "foste", "furono",
    "sarò", "sarai", "sarà", "saremo", "sarete", "saranno",
    "sia", "siano", "fossi", "fosse", "fossimo", "fossero",
    "stato", "stata", "stati", "state",
    # Verbi avere
    "avere", "ho", "hai", "ha", "abbiamo", "avete", "hanno",
    "avevo", "avevi", "aveva", "avevamo", "avevate", "avevano",
    "ebbi", "avesti", "ebbe", "avemmo", "aveste", "ebbero",
    "avrò", "avrai", "avrà", "avremo", "avrete", "avranno",
    "abbia", "abbiate", "abbiano", "avessi", "avesse", "avessero",
    "avuto", "avuta", "avuti", "avute",
    # Verbi fare
    "fare", "faccio", "fai", "fa", "facciamo", "fate", "fanno",
    "facevo", "facevi", "faceva", "facevamo", "facevate", "facevano",
    "feci", "facesti", "fece", "facemmo", "faceste", "fecero",
    "farò", "farai", "farà", "faremo", "farete", "faranno",
    "fatto", "fatta", "fatti", "fatte",
    # Verbi andare
    "andare", "vado", "vai", "va", "andiamo", "andate", "vanno",
    "andavo", "andavi", "andava", "andavamo", "andavate", "andavano",
    "andrò", "andrai", "andrà", "andremo", "andrete", "andranno",
    "andato", "andata", "andati",
    # Verbi dire
    "dire", "dico", "dici", "dice", "diciamo", "dite", "dicono",
    "dicevo", "dicevi", "diceva", "dicevamo", "dicevate", "dicevano",
    "dirò", "dirai", "dirà", "diremo", "direte", "diranno",
    "detto", "detta", "detti", "dette",
    # Verbi vedere
    "vedere", "vedo", "vedi", "vede", "vediamo", "vedete", "vedono",
    "vedevo", "vedevi", "vedeva", "vedrò", "vedrà",
    "visto", "vista", "visti", "viste",
    # Verbi venire
    "venire", "vengo", "vieni", "viene", "veniamo", "venite", "vengono",
    "venuto", "venuta", "venuti",
    # Verbi modali
    "potere", "posso", "puoi", "può", "possiamo", "potete", "possono",
    "potuto", "potevo", "potevi", "poteva", "potevamo", "potevate", "potevano",
    "potrei", "potresti", "potrebbe", "potremmo", "potreste", "potrebbero",
    "dovere", "devo", "devi", "deve", "dobbiamo", "dovete", "devono",
    "dovuto", "dovevo", "doveva", "dovrei", "dovresti", "dovrebbe",
    "volere", "voglio", "vuoi", "vuole", "vogliamo", "volete", "vogliono",
    "voluto", "volevo", "volevi", "voleva", "vorrei", "vorresti", "vorrebbe",
    "sapere", "so", "sai", "sa", "sappiamo", "sapete", "sanno",
    # Esclamazioni
    "ah", "eh", "oh", "uh", "mah", "boh", "beh", "bah",
    "ahi", "ehi", "uhm", "mmm", "hmm", "uff", "ops",
    "haha", "ahah", "ahaha", "lol", "lmao", "rofl", "xd",
    "ok", "okok", "okay", "ko", "wow", "vabbe", "vabbè",
    "ciao", "salve", "buongiorno", "buonasera", "buonanotte",
    "grazie", "prego", "scusa", "scusami", "scusate", "dai",
    # Vulgarities (no value)
    "cazzo", "minchia", "merda", "fanculo", "vaffanculo",
    "cesso", "cretino", "stronzo", "stronza", "coglione", "coglioni",
    # Web
    "https", "http", "www", "com", "html", "org", "net",
    # English
    "the", "a", "an", "and", "or", "but", "if", "then", "else",
    "in", "on", "at", "to", "for", "of", "with", "by", "from",
    "is", "are", "was", "were", "be", "been", "being", "am",
    "have", "has", "had", "having",
    "do", "does", "did", "doing", "done",
    "will", "would", "could", "should", "may", "might", "must", "shall", "can",
    "not", "no", "yes", "yep", "yeah", "nope", "nah",
    "it", "its", "this", "that", "these", "those",
    "he", "she", "they", "we", "you", "i", "me", "him", "her", "us", "them",
    "my", "your", "his", "our", "their",
    "what", "which", "who", "whom", "whose", "when", "where", "why", "how",
    "all", "each", "every", "both", "few", "many", "more", "most", "other",
    "some", "such", "than", "too", "very", "just", "also", "only",
    "same", "so", "now", "ever", "never", "often",
    "really", "actually", "basically", "literally", "obviously",
    "totally", "completely", "absolutely", "definitely",
})

BRANDS: frozenset[str] = frozenset({
    "spotify", "netflix", "youtube", "instagram", "facebook", "twitter", "tiktok",
    "snapchat", "whatsapp", "telegram", "discord", "twitch", "reddit", "linkedin",
    "google", "apple", "microsoft", "amazon", "meta", "samsung", "huawei",
    "xiaomi", "iphone", "android", "macbook", "ipad", "airpods", "ubuntu",
    "github", "gitlab", "stackoverflow",
    "ferrari", "lamborghini", "porsche", "bmw", "audi", "mercedes", "fiat",
    "alfa", "lancia", "maserati", "tesla", "volkswagen", "peugeot", "renault",
    "toyota", "honda", "yamaha", "ducati", "kawasaki",
    "nike", "adidas", "puma", "gucci", "prada", "louis", "vuitton", "chanel",
    "dior", "armani", "versace", "supreme", "balenciaga", "fendi", "hermes",
    "rolex", "rayban",
    "playstation", "xbox", "nintendo", "steam", "epic", "rockstar", "ubisoft",
    "blizzard", "riot", "valorant", "fortnite", "minecraft", "fifa",
    "mcdonald", "burgerking", "starbucks", "nutella", "ferrero",
    "disney", "primevideo", "crunchyroll",
    "juventus", "milan", "inter", "roma", "napoli", "lazio", "atalanta",
    "barcelona", "real", "madrid", "chelsea", "arsenal", "liverpool",
    "manchester", "psg", "bayern", "dortmund",
})

NICKNAMES: frozenset[str] = frozenset({
    "amore", "amo", "tesoro", "tata", "stellina", "stella",
    "cuore", "cuoricino", "principessa", "regina", "angelo", "angioletto",
    "bimba", "bimbo", "vita", "anima", "passione", "ciccio", "ciccia",
    "bro", "fra", "frà", "frate", "fratm", "zio", "compà", "boss",
    "tato", "tatone", "babe", "baby", "honey", "darling", "love", "luv",
    "dude", "bud", "buddy", "mate", "fam",
})

EMOJI_TOPICS: dict[str, str] = {
    "gaming": "🎮🕹🎯🏆🎰",
    "musica": "🎵🎶🎤🎧🎸🎹🥁",
    "sport": "⚽🏀🏈⚾🎾🏐🏉🥊⛹🏃🏋🚴🏄🏌",
    "cibo": "🍕🍔🍟🌭🌮🍝🍜🍣🍱🍙🍰🍩🍪🍫🍦🍻🍷🍺",
    "tech": "💻📱⌨🖱💾📡🤖🛰",
    "studio": "📚📖📝🎓✏✒📐📏🔬🔭",
    "viaggio": "✈🚗🚕🚙🚌🚲🛴🏝🏖🗺🧳",
    "amore": "❤🧡💛💚💙💜🖤🤍💕💖💗💘💝😘😍🥰",
}

TOPICS: dict[str, list[str]] = {
    "gaming": [
        "fortnite", "minecraft", "fifa", "cod", "warzone", "callofduty", "pubg",
        "lol", "league", "valorant", "csgo", "counter", "strike", "dota", "wow",
        "playstation", "xbox", "nintendo", "switch", "steam", "epic", "twitch",
        "gioco", "giochi", "partita", "partite", "online", "multiplayer", "ranked",
        "lobby", "match", "boss", "level", "livello", "skin", "loot", "kill",
        "fps", "rpg", "moba", "battle", "royale", "clash", "supercell",
        "console", "respawn", "noob", "pro", "sniper",
    ],
    "musica": [
        "spotify", "playlist", "concerto", "album", "canzone", "canzoni", "brano",
        "musica", "musicale", "cantante", "band", "rock", "pop", "rap",
        "trap", "techno", "house", "rave", "festival", "live", "tour", "disco",
        "vinile", "youtube", "soundcloud", "deezer", "tidal",
        "cuffie", "biglietto", "biglietti", "palco",
    ],
    "sport": [
        "calcio", "tennis", "basket", "pallavolo", "rugby", "nuoto", "corsa",
        "running", "palestra", "gym", "fitness", "allenamento", "allenare",
        "bicicletta", "bici", "ciclismo", "sci", "snowboard", "atletica",
        "marathon", "maratona", "campionato", "torneo", "squadra", "partita",
        "stadio", "campo", "juventus", "inter", "milan", "barcelona",
    ],
    "tech": [
        "computer", "laptop", "programmare", "programmazione", "codice",
        "github", "linux", "windows", "ubuntu", "kali",
        "python", "javascript", "react", "node", "docker", "server", "cloud",
        "developer", "coder", "framework", "library", "database",
        "api", "rest", "json", "html", "css", "vim", "vscode",
    ],
    "studio": [
        "università", "studiare", "studio", "esame", "esami", "lezione", "lezioni",
        "professore", "prof", "tesi", "laurea", "facoltà", "corso",
        "appunti", "libri", "scuola", "compiti", "compito", "voto",
        "valutazione", "matricola", "ingegneria", "medicina",
    ],
    "cibo": [
        "pizza", "pasta", "pranzo", "cena", "colazione", "ristorante",
        "caffè", "vino", "birra", "cocktail", "drink", "aperitivo", "spritz",
        "carbonara", "amatriciana", "lasagne", "gelato", "dolce", "dessert",
        "kebab", "burger", "sushi", "ramen", "panino", "pizzeria",
    ],
}


# ═══════════════════════════════════════════════════════════════════════════
# LEAKED PASSWORD PATTERNS — riconosce password citate direttamente in chat
# ═══════════════════════════════════════════════════════════════════════════
# Cattura il valore della password (gruppo 1) da frasi tipiche IT/EN.
# La validazione successiva filtra i falsi positivi (aggettivi, parole comuni).

LEAKED_PASSWORD_PATTERNS = [
    # IT: "(la mia) password/pwd/pin/codice è X" + varianti :=
    re.compile(
        r"(?:la\s+)?(?:mia\s+|tua\s+|sua\s+|nuova\s+|vecchia\s+)?"
        r"(?:password|pass|pwd|psw|pswd|chiave|codice|pin)"
        r"\s*[:=]\s*[\"'`]?([^\s\"'`]{4,30})",
        re.IGNORECASE,
    ),
    re.compile(
        r"(?:la\s+)?(?:mia\s+|tua\s+|sua\s+|nuova\s+|vecchia\s+)?"
        r"(?:password|pass|pwd|psw|chiave|pin|codice)"
        r"\s+(?:è|e'|sara|sarà|era)\s+[\"'`]?([^\s\"'`]{4,30})",
        re.IGNORECASE,
    ),
    # IT: "ho cambiato/messo/settato (la pwd) in/con X"
    re.compile(
        r"\bho\s+(?:cambiato|messo|settato|impostato|fatto|scelto|usato)\s+"
        r"(?:la\s+)?(?:password|pwd|psw|chiave|pin|codice)?\s*"
        r"(?:in|con|come|=)\s*[\"'`]?([^\s\"'`]{4,30})",
        re.IGNORECASE,
    ),
    # EN: "(my) password/pwd/pin: X" + varianti
    re.compile(
        r"(?:my\s+|the\s+|new\s+|old\s+)?"
        r"(?:password|pass|pwd|psw|key|pin|code|passcode)"
        r"\s*[:=]\s*[\"'`]?([^\s\"'`]{4,30})",
        re.IGNORECASE,
    ),
    re.compile(
        r"(?:my\s+|the\s+|new\s+)?"
        r"(?:password|pass|pwd|psw|key|pin|code)"
        r"\s+is\s+[\"'`]?([^\s\"'`]{4,30})",
        re.IGNORECASE,
    ),
    re.compile(
        r"\bi\s+(?:set|changed|made|chose|used|put)\s+"
        r"(?:my\s+)?(?:password|pwd|psw|key|pin|code)\s+"
        r"(?:to|as|=|into)\s+[\"'`]?([^\s\"'`]{4,30})",
        re.IGNORECASE,
    ),
]

# Falsi positivi: parole che seguono "la mia password è ..." ma non sono pwd.
PASSWORD_FALSE_POSITIVES: frozenset[str] = frozenset({
    # Aggettivi IT che descrivono la password
    "sicura", "debole", "facile", "difficile", "semplice", "complessa",
    "buona", "brutta", "lunga", "corta", "banale", "robusta", "blindata",
    "scaduta", "vecchia", "nuova", "uguale", "diversa", "stessa", "solita",
    "sicurissima", "facilissima", "lunghissima", "potente", "corta",
    "scoperta", "rubata", "compromessa", "leakata",
    # Risposte vaghe IT
    "ok", "boh", "niente", "nada", "vuota", "niente", "uguale",
    "qualcosa", "qualunque",
    # EN adjectives
    "strong", "weak", "easy", "hard", "secure", "insecure", "good", "bad",
    "long", "short", "complex", "simple", "same", "different", "compromised",
    "stolen", "leaked", "expired", "the", "a", "an", "old", "new",
    # Generic
    "ciao", "hello", "test", "prova", "tutto", "everything", "nothing",
})


# ═══════════════════════════════════════════════════════════════════════════
# DATACLASS: Token con metadata completi
# ═══════════════════════════════════════════════════════════════════════════

@dataclass
class Token:
    """Rappresenta un token estratto con metadata completi.

    Sources possibili:
      - 'username': estratto da user_display_name (alta confidenza)
      - 'mention': @mentioned (alta confidenza)
      - 'mid_sentence': appare dentro una frase (medio-alta)
      - 'sentence_start': appare a inizio frase (bassa, possibile false positive)
    """
    text: str                                  # forma originale
    normalized: str                            # lowercase
    frequency: int = 0
    msg_indexes: set[int] = field(default_factory=set)
    title_case: bool = False
    has_digit: bool = False
    has_mid_sentence: bool = False             # appare almeno una volta NON a inizio frase
    sources: set[str] = field(default_factory=set)

    @property
    def confidence(self) -> float:
        """Score 0-1 di quanto è significativo come token classificabile."""
        score = 0.0
        # Frequency contribution
        if self.frequency >= 10:
            score += 0.4
        elif self.frequency >= 5:
            score += 0.3
        elif self.frequency >= 2:
            score += 0.15
        # Source contributions
        if "mention" in self.sources or "username" in self.sources:
            score += 0.5
        if self.has_mid_sentence and self.title_case:
            score += 0.3  # capitalized mid-sentence = likely proper noun
        if self.title_case and not self.has_mid_sentence:
            score -= 0.2  # only at sentence start = likely false positive
        return max(0.0, min(1.0, score))


# ═══════════════════════════════════════════════════════════════════════════
# HELPER FUNCTIONS
# ═══════════════════════════════════════════════════════════════════════════

def _is_spam_pattern(word: str) -> bool:
    """Detect ahaha, lolol, eeeee patterns."""
    if len(word) < 4:
        return False
    if re.search(r"(.)\1{2,}", word):
        return True
    if len(set(word.lower())) <= 2:
        return True
    return False


def _consolidate_plurals(counter: Counter) -> Counter:
    """Merge Italian plural/singular variants. Canonical = most frequent."""
    result = Counter()
    used = set()

    for word, count in counter.most_common():
        if word in used:
            continue

        variants = []
        if word.endswith("o") and len(word) >= 4:
            variants.append(word[:-1] + "i")
        elif word.endswith("a") and len(word) >= 4:
            variants.append(word[:-1] + "e")
        elif word.endswith("i") and len(word) >= 4:
            variants.append(word[:-1] + "o")
            variants.append(word[:-1] + "e")
        elif word.endswith("e") and len(word) >= 4:
            variants.append(word[:-1] + "a")
            variants.append(word[:-1] + "i")

        merged_count = count
        canonical = word
        max_count = count

        for variant in variants:
            if variant in counter and variant != word and variant not in used:
                merged_count += counter[variant]
                used.add(variant)
                if counter[variant] > max_count:
                    canonical = variant
                    max_count = counter[variant]

        result[canonical] = merged_count
        used.add(word)

    return result


# ═══════════════════════════════════════════════════════════════════════════
# CLASS: TextAnalyzer (pipeline centralizzata)
# ═══════════════════════════════════════════════════════════════════════════

class TextAnalyzer:
    """Pipeline di analisi testo con tokenizzazione single-pass + caching.

    Usage:
        analyzer = TextAnalyzer(messages)
        features = analyzer.extract_features()
        results = analyzer.search("amore")
        co_occur = analyzer.co_occurrences("gatto")
    """

    # Pre-compiled regex
    SENTENCE_RE = re.compile(r"(?<=[.!?])\s+")
    WORD_RE = re.compile(r"\b[\w']+\b", re.UNICODE)
    YEAR_RE = re.compile(r"\b(19[4-9]\d|20[0-3]\d)\b")
    NUMBER_RE = re.compile(r"\b(\d{2,8})\b")
    DATE_RE = re.compile(r"\b(\d{1,2}[/\-.]\d{1,2}[/\-.]\d{2,4})\b")
    AT_MENTION_RE = re.compile(r"@(\w{3,})")
    PHONE_RE_IT = re.compile(r"\b(?:\+?39[\s.\-]?)?3\d{2}[\s.\-]?\d{6,7}\b")
    PHONE_RE_INTL = re.compile(r"\b\+\d{1,3}[\s.\-]?\d{7,11}\b")
    AGE_RE = re.compile(r"\bho\s+(\d{1,2})\s+ann[oi]\b", re.IGNORECASE)
    PROPER_NOUN_RE = re.compile(r"\b([A-ZÀÈÌÒÙ][a-zàèìòù]{2,})\b")

    def __init__(self, messages: list[dict],
                 *, aggregates: dict | None = None,
                 author_filter: str | None = None):
        """`aggregates` e' il dict {users, forwards, mentions} caricato da
        extractor.load_aggregates(). Se presenti, le estrazioni preferiscono
        questi dati pre-calcolati invece di rifare regex/NER da zero."""
        self.messages = messages
        self.tokens: dict[str, Token] = {}
        self._tokenized: bool = False
        self._all_text: str | None = None
        self.current_year: int = datetime.now().year
        self.aggregates: dict = aggregates or {}
        self.author_filter: str | None = author_filter

    # ─── Cached properties ──────────────────────────────────────────────

    @staticmethod
    def _full_text(msg: dict) -> str:
        """Restituisce TUTTO il testo associato a un msg: message + ocr_text
        (da TIH OCR enrichment) + transcription (da Whisper). Cosi' NER,
        keyword, leaked_passwords ecc. lavorano anche sul contenuto delle
        immagini e dei messaggi vocali, non solo sul testo digitato.
        """
        parts = [msg.get("message") or ""]
        if msg.get("ocr_text"):
            parts.append(msg["ocr_text"])
        if msg.get("transcription"):
            parts.append(msg["transcription"])
        return " ".join(p for p in parts if p)

    @property
    def all_text(self) -> str:
        if self._all_text is None:
            self._all_text = " ".join(self._full_text(m) for m in self.messages)
        return self._all_text

    # ─── Normalization ──────────────────────────────────────────────────

    @staticmethod
    def normalize(text: str) -> str:
        """Replace apostrofi/smart-quotes per tokenizzazione corretta."""
        for ch in ("'", "’", "‘", "ʼ", "‛"):
            text = text.replace(ch, " ")
        text = text.replace("“", '"').replace("”", '"')
        return text

    # ─── Tokenization ───────────────────────────────────────────────────

    def tokenize(self) -> None:
        """Single-pass tokenization. Cached: re-call is no-op."""
        if self._tokenized:
            return

        self.tokens.clear()
        for idx, msg in enumerate(self.messages):
            self._tokenize_message(idx, msg)
        self._tokenized = True

    def _tokenize_message(self, idx: int, msg: dict) -> None:
        # Username tokens (high confidence)
        udn = msg.get("user_display_name", "")
        for part in re.split(r"\W+", udn):
            cleaned = re.sub(r"[^\w]", "", part)
            if len(cleaned) >= 3:
                self._add_token(cleaned, idx, sources={"username"})

        # Includi anche ocr_text e transcription (TIH enrichment), cosi' i
        # token estratti da immagini OCR-ed e audio trascritti finiscono
        # nel grafo dei token alla pari del testo digitato.
        text = self._full_text(msg)
        if not text:
            return

        normalized = self.normalize(text)

        # @mentions
        for mention in self.AT_MENTION_RE.findall(normalized):
            self._add_token(mention, idx, sources={"mention"})

        # Sentence-by-sentence
        sentences = self.SENTENCE_RE.split(normalized)
        for sent in sentences:
            if not sent.strip():
                continue
            words = list(self.WORD_RE.finditer(sent))
            for i, m in enumerate(words):
                word = m.group(0).strip("'")
                if not word or len(word) < 2:
                    continue
                is_start = (i == 0)
                source = "sentence_start" if is_start else "mid_sentence"
                self._add_token(word, idx, sources={source})

    def _add_token(self, text: str, msg_idx: int, sources: set[str]) -> None:
        """Add or update a token in the index."""
        normalized = text.lower()
        if normalized in self.tokens:
            tok = self.tokens[normalized]
            tok.frequency += 1
            tok.msg_indexes.add(msg_idx)
            tok.sources |= sources
            if "mid_sentence" in sources:
                tok.has_mid_sentence = True
        else:
            self.tokens[normalized] = Token(
                text=text,
                normalized=normalized,
                frequency=1,
                msg_indexes={msg_idx},
                title_case=text[0].isupper() if text else False,
                has_digit=any(c.isdigit() for c in text),
                has_mid_sentence="mid_sentence" in sources,
                sources=set(sources),
            )

    # ═══════════════════════════════════════════════════════════════════════
    # EXTRACTION METHODS (per categoria)
    # ═══════════════════════════════════════════════════════════════════════

    def extract_features(self, author_filter: str | None = None) -> dict:
        """Run full pipeline. Returns dict compatible with old extractor API."""
        if author_filter:
            af = author_filter.lower()
            self.messages = [m for m in self.messages
                             if af in m.get("user_display_name", "").lower()]
            # Reset cache
            self._tokenized = False
            self._all_text = None

        self.tokenize()

        out = {
            "names": self.extract_names(),
            "dates": self.extract_dates(),
            "numbers": self.extract_numbers(),
            "phones": self.extract_phones(),
            "ages_birth_years": self.extract_ages_birthyears(),
            "animals": self.extract_animals(),
            "keywords": self.extract_keywords(),
            "brands": self.extract_brands(),
            "nicknames": self.extract_nicknames(),
            "phrases": self.extract_bigrams(),
            "topics": self.extract_topics(),
            "emojis": self.extract_emojis_enriched(),
            "authors": self.extract_authors(),
            "message_count": len(self.messages),
        }

        # ── Campi TIH-enriched: presenti SOLO se i dati arrivano dal nuovo TIH ──
        if self._has_ner_data():
            ner_persons = self.extract_ner_persons()
            ner_locations = self.extract_ner_locations()
            ner_orgs = self.extract_ner_orgs()
            if ner_persons:
                out["ner_persons"] = ner_persons
                # Fonde i nomi NER coi nomi heuristic (NER e' piu' preciso)
                out["names"] = self._merge_unique(ner_persons, out["names"])
            if ner_locations:
                out["ner_locations"] = ner_locations
            if ner_orgs:
                out["ner_orgs"] = ner_orgs

        gps_cities = self.extract_gps_cities()
        if gps_cities:
            out["gps_cities"] = gps_cities

        emoji_keywords = self.extract_emoji_keywords()
        if emoji_keywords:
            out["emoji_keywords"] = emoji_keywords

        pre_mentions = self.extract_pre_mentions()
        if pre_mentions:
            out["mentions"] = pre_mentions

        fwd_topics = self.extract_forward_topics()
        if fwd_topics:
            out["forward_topics"] = fwd_topics

        # Leaked passwords: presente solo se ne troviamo almeno una
        leaked = self.extract_leaked_passwords()
        if leaked:
            out["leaked_passwords"] = leaked

        return out

    @staticmethod
    def _merge_unique(primary: list[str], secondary: list[str]) -> list[str]:
        """Concatena due liste preservando ordine e rimuovendo duplicati case-insensitive."""
        seen: set = set()
        out: list[str] = []
        for item in list(primary) + list(secondary):
            key = item.lower()
            if key not in seen:
                seen.add(key)
                out.append(item)
        return out

    def extract_names(self, top_n: int = 30, min_freq: int = 2) -> list[str]:
        """Estrae nomi propri con confidence-based ranking."""
        self.tokenize()

        candidates: list[tuple[str, float]] = []
        for tok in self.tokens.values():
            # Skip stopwords e spam
            if tok.normalized in STOPWORDS:
                continue
            if _is_spam_pattern(tok.text):
                continue
            # Skip se non title-case e non da mention/username
            if not tok.title_case:
                if not (tok.sources & {"mention", "username"}):
                    continue
            # Filter false positive: solo a inizio frase E freq < 5 → drop
            if tok.title_case and not tok.has_mid_sentence:
                if not (tok.sources & {"mention", "username"}) and tok.frequency < 5:
                    continue
            if tok.frequency < min_freq:
                continue

            score = tok.confidence
            if "username" in tok.sources or "mention" in tok.sources:
                score += 0.5
            if tok.has_mid_sentence:
                score += 0.2

            candidates.append((tok.text, score))

        candidates.sort(key=lambda x: -x[1])
        seen: set[str] = set()
        result: list[str] = []
        for text, _ in candidates:
            key = text.lower()
            if key not in seen:
                seen.add(key)
                result.append(text)
                if len(result) >= top_n:
                    break
        return result

    def extract_dates(self) -> list[str]:
        """Anni e date dd/mm/yyyy."""
        dates: set[str] = set()
        for msg in self.messages:
            text = self._full_text(msg)
            for year in self.YEAR_RE.findall(text):
                dates.add(year)
            for date in self.DATE_RE.findall(text):
                dates.add(date)
        return sorted(dates)

    def extract_numbers(self, top_n: int = 20, min_freq: int = 2) -> list[str]:
        """Numeri ricorrenti, escludendo anni."""
        counter: Counter = Counter()
        year_set = set(self.YEAR_RE.findall(self.all_text))
        for msg in self.messages:
            text = self._full_text(msg)
            for num in self.NUMBER_RE.findall(text):
                if num not in year_set:
                    counter[num] += 1
        return [n for n, c in counter.most_common(top_n) if c >= min_freq]

    def extract_phones(self) -> list[str]:
        """Telefoni con varianti corte (last 4/6 digits)."""
        found: set[str] = set()
        for msg in self.messages:
            text = self._full_text(msg)
            for match in self.PHONE_RE_IT.findall(text) + self.PHONE_RE_INTL.findall(text):
                clean = re.sub(r"[\s.\-]", "", match)
                if len(clean) >= 9:
                    found.add(clean)
                    if len(clean) > 4:
                        found.add(clean[-4:])
                    if len(clean) > 6:
                        found.add(clean[-6:])
        return sorted(found)

    def extract_ages_birthyears(self) -> list[str]:
        """'ho 25 anni' → birth_year + short_year + age."""
        found: set[str] = set()
        for msg in self.messages:
            text = self._full_text(msg)
            for match in self.AGE_RE.findall(text):
                try:
                    age = int(match)
                    if 10 <= age <= 99:
                        birth_year = self.current_year - age
                        found.add(str(birth_year))
                        found.add(str(birth_year)[2:])
                        found.add(str(age))
                except ValueError:
                    pass
        return sorted(found)

    def extract_animals(self) -> list[str]:
        """Animali con plurali consolidati."""
        self.tokenize()
        counter: Counter = Counter()
        for tok in self.tokens.values():
            if tok.normalized in ANIMALS:
                counter[tok.normalized] += tok.frequency
        consolidated = _consolidate_plurals(counter)
        return [w for w, c in consolidated.most_common() if c >= 1]

    def extract_leaked_passwords(self, top_n: int = 30) -> list[str]:
        """Estrae password citate direttamente nel testo.

        Riconosce pattern tipo "la mia pwd è X", "password: X", "i changed
        my pin to X", ecc. Filtra falsi positivi (aggettivi tipo 'sicura',
        'debole') e parole troppo comuni che non sono plausibili come pwd.

        Score altissimo nel generator (CATEGORY_BASE_SCORE.leaked_passwords)
        perche' sono candidati direttamente prelevati dal testo.
        """
        self.tokenize()
        found: dict[str, int] = {}
        for pat in LEAKED_PASSWORD_PATTERNS:
            for m in pat.finditer(self.all_text):
                # Strip solo punteggiatura di fine-frase (mai ! ? che possono
                # essere caratteri legittimi di una password).
                cand = m.group(1).strip().rstrip(".,;:)\"']")
                if not cand or len(cand) < 4 or len(cand) > 30:
                    continue
                if cand.lower() in PASSWORD_FALSE_POSITIVES:
                    continue
                # Se il candidato è una parola comune molto frequente nel chat
                # senza cifre/simboli, probabilmente è solo una parola normale
                # ripresa per caso dalla regex (es. "...la pwd è cosa fai?").
                tok = self.tokens.get(cand.lower())
                if tok and not tok.has_digit and tok.frequency > 5:
                    plausible = any(c.isupper() for c in cand) or any(
                        not c.isalnum() for c in cand
                    )
                    if not plausible:
                        continue
                found[cand] = found.get(cand, 0) + 1
        return [k for k, _ in sorted(
            found.items(), key=lambda kv: (-kv[1], kv[0])
        )][:top_n]

    def extract_keywords(self, top_n: int = 50, min_freq: int = 2,
                         exclude_names: list[str] | None = None) -> list[str]:
        """Top keyword con stopwords + spam filter + stemming + exclusion nomi."""
        self.tokenize()

        # Pre-computa set di esclusione: nomi già catturati in altre categorie
        if exclude_names is None:
            exclude_names = self.extract_names()
        names_set = {n.lower() for n in exclude_names}

        counter: Counter = Counter()
        for tok in self.tokens.values():
            # Esclusioni
            if tok.normalized in STOPWORDS:
                continue
            if tok.normalized in ANIMALS or tok.normalized in BRANDS or tok.normalized in NICKNAMES:
                continue
            if tok.normalized in names_set:
                continue  # già un nome proprio
            # Skip token derivati da username/mention (sono nomi)
            if tok.sources & {"username", "mention"}:
                continue
            # Skip token title-case visti mid-sentence (probabili nomi propri)
            if tok.title_case and tok.has_mid_sentence:
                continue
            if _is_spam_pattern(tok.text):
                continue
            if tok.has_digit:
                continue
            if len(tok.normalized) < 4:
                continue
            # Solo parole alfabetiche
            if not re.match(r"^[a-zàèìòùáéíóú]+$", tok.normalized):
                continue
            counter[tok.normalized] += tok.frequency

        consolidated = _consolidate_plurals(counter)
        return [w for w, c in consolidated.most_common(top_n) if c >= min_freq]

    def extract_brands(self, top_n: int = 20) -> list[str]:
        """Brand riconosciuti."""
        self.tokenize()
        counter: Counter = Counter()
        for tok in self.tokens.values():
            if tok.normalized in BRANDS:
                counter[tok.normalized] += tok.frequency
        return [w for w, c in counter.most_common(top_n) if c >= 1]

    def extract_nicknames(self, top_n: int = 15) -> list[str]:
        """Soprannomi affettuosi."""
        self.tokenize()
        counter: Counter = Counter()
        for tok in self.tokens.values():
            if tok.normalized in NICKNAMES:
                counter[tok.normalized] += tok.frequency
        return [w for w, c in counter.most_common(top_n) if c >= 1]

    def extract_bigrams(self, min_freq: int = 3, top_n: int = 15) -> list[str]:
        """Bigrammi frequenti escludendo stopwords."""
        counter: Counter = Counter()
        for msg in self.messages:
            text = self.normalize(self._full_text(msg)).lower()
            words = re.findall(r"\b[a-zàèìòùáéíóú]{3,}\b", text)
            words = [w for w in words if w not in STOPWORDS]
            for i in range(len(words) - 1):
                bigram = f"{words[i]} {words[i+1]}"
                counter[bigram] += 1
        return [b for b, c in counter.most_common(top_n) if c >= min_freq]

    def extract_topics(self) -> dict[str, int]:
        """Topic via keyword + emoji match."""
        self.tokenize()
        detected: dict[str, int] = {}

        # Keyword-based
        word_set = {tok.normalized for tok in self.tokens.values()}
        for topic, kws in TOPICS.items():
            matches = sum(1 for kw in kws if kw in word_set)
            if matches >= 3:
                detected[topic] = matches

        # Emoji boost
        for topic, emojis in EMOJI_TOPICS.items():
            count = sum(1 for c in self.all_text if c in emojis)
            if count >= 3:
                detected[topic] = detected.get(topic, 0) + count // 2

        return dict(sorted(detected.items(), key=lambda x: -x[1]))

    def extract_emojis(self, top_n: int = 20) -> list[str]:
        """Emoji più frequenti."""
        counter: Counter = Counter()
        for c in self.all_text:
            cp = ord(c)
            if (0x1F000 <= cp <= 0x1FFFF) or (0x2600 <= cp <= 0x27BF):
                counter[c] += 1
        return [e for e, _ in counter.most_common(top_n)]

    def extract_authors(self) -> list[str]:
        """Lista autori unici."""
        return sorted({m.get("user_display_name", "") for m in self.messages
                       if m.get("user_display_name")})

    # ═══════════════════════════════════════════════════════════════════════
    # NUOVI METODI: dati arricchiti da TIH (NER, EXIF, reactions, mentions)
    # ═══════════════════════════════════════════════════════════════════════

    def _has_ner_data(self) -> bool:
        return any(m.get("ner_entities") for m in self.messages)

    @staticmethod
    def _ner_text_valid(text: str) -> bool:
        """Filtra falsi positivi NER: URL, caratteri speciali, ripetizioni, troppo corti/lunghi."""
        if not text or len(text) < 2 or len(text) > 40:
            return False
        # No URL
        if "http" in text.lower() or "/" in text or "www." in text.lower():
            return False
        # Solo lettere / spazi / apostrofo / accenti
        if not re.match(r"^[A-Za-zÀ-ÿ' \-\.]+$", text):
            return False
        # No ripetizioni "ahahaha" / "ggggg"
        if _is_spam_pattern(text.lower()):
            return False
        # No tutto in una stessa lettera
        if len(set(text.lower().replace(" ", ""))) < 2:
            return False
        return True

    def _collect_ner(self, label: str, top_n: int, min_freq: int) -> list[str]:
        counter: Counter = Counter()
        for m in self.messages:
            for ent in (m.get("ner_entities") or []):
                if ent.get("label") != label:
                    continue
                text = (ent.get("text") or "").strip()
                if not self._ner_text_valid(text):
                    continue
                counter[text] += 1
        return [w for w, c in counter.most_common(top_n) if c >= min_freq]

    def extract_ner_persons(self, top_n: int = 30, min_freq: int = 1) -> list[str]:
        """Persone (PER) pre-estratte da TIH/spaCy. Piu' precisi di regex."""
        return self._collect_ner("PER", top_n, min_freq)

    def extract_ner_locations(self, top_n: int = 20, min_freq: int = 1) -> list[str]:
        """Luoghi (LOC) pre-estratti da TIH. Citta', regioni, posti."""
        return self._collect_ner("LOC", top_n, min_freq)

    def extract_ner_orgs(self, top_n: int = 15, min_freq: int = 1) -> list[str]:
        """Organizzazioni (ORG) pre-estratte da TIH: aziende, enti, brand non in dizionario."""
        return self._collect_ner("ORG", top_n, min_freq)

    def extract_gps_cities(self) -> list[str]:
        """Citta' rilevate da EXIF GPS delle foto via reverse geocoding offline."""
        try:
            from osint.geo_intel import reverse_geocode
        except ImportError:
            return []
        seen: set[str] = set()
        out: list[str] = []
        for m in self.messages:
            exif = m.get("exif") or {}
            coords = exif.get("gps_coords") or {}
            lat = coords.get("lat")
            lon = coords.get("lon")
            if lat is None or lon is None:
                continue
            city = reverse_geocode(lat, lon)
            if city and city["name"] not in seen:
                seen.add(city["name"])
                out.append(city["name"])
        return out

    def extract_pre_mentions(self, top_n: int = 20) -> list[str]:
        """Menzioni @user pre-estratte da TIH. Top per count nel mention_map dell'autore filtrato."""
        # Se filtro su un author_uid specifico, leggo il suo mention_map
        mention_map = self.aggregates.get("mentions") or {}
        if not isinstance(mention_map, dict):
            return []
        if self.author_filter and self.author_filter.startswith(("tg:", "wa:")):
            entries = mention_map.get(self.author_filter, [])
        else:
            # Aggregato totale del canale
            agg: Counter = Counter()
            for _uid, lst in mention_map.items():
                if not isinstance(lst, list):
                    continue
                for e in lst:
                    target = (e.get("target") or "").strip()
                    if target:
                        agg[target] += int(e.get("count", 0))
            entries = [{"target": k, "count": v} for k, v in agg.most_common(top_n)]
        out: list[str] = []
        for e in entries[:top_n]:
            target = (e.get("target") or "").lstrip("@").strip()
            if target and target not in out:
                out.append(target)
        return out

    def extract_emojis_enriched(self, top_n: int = 20) -> list[str]:
        """Emoji combinando: emoji nel testo + reactions_summary nei messaggi
        + reactions_received da _users.json (firma emotiva del target)."""
        counter: Counter = Counter()

        # 1. Emoji nel testo (vecchio comportamento)
        for c in self.all_text:
            cp = ord(c)
            if (0x1F000 <= cp <= 0x1FFFF) or (0x2600 <= cp <= 0x27BF):
                counter[c] += 1

        # 2. reactions_summary nei messaggi (emoji ricevute sui propri messaggi)
        for m in self.messages:
            for r in (m.get("reactions_summary") or []):
                emoji = r.get("emoji")
                count = int(r.get("count", 0))
                if emoji and not emoji.startswith("custom:") and count > 0:
                    counter[emoji] += count

        # 3. reactions_received da _users.json (se filtriamo su uno specifico author_uid)
        users = self.aggregates.get("users") or {}
        if self.author_filter and self.author_filter.startswith(("tg:", "wa:")):
            profile = users.get(self.author_filter, {})
            for emoji, count in (profile.get("reactions_received") or {}).items():
                if not emoji.startswith("custom:"):
                    counter[emoji] += int(count)

        return [e for e, _ in counter.most_common(top_n)]

    def extract_emoji_keywords(self, max_keywords: int = 25) -> list[str]:
        """Traduce le top emoji del target in parole IT/EN candidate per la wordlist.

        Esempio: target con tante reazioni ⚽ → ['calcio', 'football', 'soccer'].
        Le emoji da sole non sono usate in password (la maggior parte dei sistemi
        non le accetta), ma la loro semantica si'.
        """
        try:
            from osint.emoji_words import expand_emoji_list
        except ImportError:
            return []
        emojis = self.extract_emojis_enriched(top_n=15)
        return expand_emoji_list(emojis, max_keywords=max_keywords)

    def extract_forward_topics(self) -> list[str]:
        """Nomi dei canali/utenti da cui forwarda il target (topic-hint).

        Esempio: forwarda spesso da '@InterFans' → keyword 'inter', 'interfans'.
        """
        fwd_map = self.aggregates.get("forwards") or {}
        if not isinstance(fwd_map, dict):
            return []
        out: list[str] = []
        seen: set[str] = set()

        if self.author_filter and self.author_filter.startswith(("tg:", "wa:")):
            sources = fwd_map.get(self.author_filter, [])
        else:
            # Aggrega tutti gli autori del canale
            agg: Counter = Counter()
            for _uid, lst in fwd_map.items():
                if not isinstance(lst, list):
                    continue
                for e in lst:
                    name = (e.get("source_name") or "").strip()
                    if name:
                        agg[name] += int(e.get("count", 0))
            sources = [{"source_name": k, "count": v} for k, v in agg.most_common(20)]

        for s in sources:
            name = (s.get("source_name") or "").strip()
            if not name or name in seen:
                continue
            # Pulisci: rimuovi @, _, spazi → lowercase
            cleaned = re.sub(r"[^a-zA-Z0-9]", "", name).lower()
            if cleaned and len(cleaned) >= 3 and cleaned not in seen:
                seen.add(cleaned)
                out.append(cleaned)
        return out

    # ═══════════════════════════════════════════════════════════════════════
    # SEARCH & CONTEXT
    # ═══════════════════════════════════════════════════════════════════════

    def search(self, query: str, max_results: int = 50, context_chars: int = 60) -> list[dict]:
        """Cerca un termine nei messaggi. Ritorna match con contesto."""
        results: list[dict] = []
        if not query:
            return results
        q = query.lower()

        for idx, msg in enumerate(self.messages):
            text = self._full_text(msg)
            text_lower = text.lower()

            start = 0
            while True:
                pos = text_lower.find(q, start)
                if pos == -1:
                    break

                ctx_start = max(0, pos - context_chars)
                ctx_end = min(len(text), pos + len(query) + context_chars)

                results.append({
                    "msg_idx": idx,
                    "author": msg.get("user_display_name", ""),
                    "date": msg.get("date", ""),
                    "context_before": text[ctx_start:pos],
                    "match": text[pos:pos + len(query)],
                    "context_after": text[pos + len(query):ctx_end],
                })

                start = pos + 1
                if len(results) >= max_results:
                    return results
        return results

    def co_occurrences(self, term: str, window: int = 5, top_n: int = 15) -> list[tuple[str, int]]:
        """Parole che appaiono entro `window` parole da `term`."""
        if not term:
            return []
        term_lower = term.lower()
        co: Counter = Counter()

        for msg in self.messages:
            text = self.normalize(self._full_text(msg)).lower()
            words = re.findall(r"\b[a-zàèìòùáéíóú]{2,}\b", text)
            for i, w in enumerate(words):
                if w == term_lower:
                    s = max(0, i - window)
                    e = min(len(words), i + window + 1)
                    for j in range(s, e):
                        if j == i:
                            continue
                        other = words[j]
                        if (len(other) >= 3 and other not in STOPWORDS
                                and other != term_lower):
                            co[other] += 1
        return co.most_common(top_n)
