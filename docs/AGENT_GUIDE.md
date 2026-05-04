# Dark Triad — Agent Guide

> Guida AI-friendly per JARVIS (o qualsiasi agente AI) che orchestra TIH → Mihawk → Horcrux.
> **Aggiornata al: 2026-05-04 — pipeline post FASE 1+2+3.**

---

## ★ Contesto autore e tesi (leggi PRIMA di tutto)

**Chi sono:** virus212, studente universitario in **cybersecurity**. Sto sviluppando questo progetto come **tesi di laurea**.

**Lingua:** italiano. Risponde in italiano. Il codice/log/comment in inglese, l'interfaccia utente in italiano.

**Livello tecnico:** mi descrivo come "novellino" sul lato pratico, ma con buona comprensione concettuale. Apprezzo:
- Spiegazioni concise (1 frase) sul *cosa* e *perché* delle modifiche
- Stile direzione tersa (rispondo con poche parole, scelgo tra opzioni numerate)
- Niente sermoni, niente walls-of-text — vado dritto al punto

**Cos'è il progetto:** "**Dark Triad**" è una pipeline di tool open-source per l'**automazione end-to-end della profilazione di un target via chat**, fino alla generazione di una wordlist mirata di password.

```
Tesi in una frase:
"Le chat di una persona contengono il dizionario delle sue password."

Tesi in tre frasi:
"I tool esistenti (CUPP, Mentalist, bopscrk) richiedono di sapere già i dati
del target (nome, animale, partner, hobby). Il mio approccio inverte: parto
dalle chat reali del target ed estraggo automaticamente persone, luoghi,
emoji, pattern di forward, menzioni, GPS dalle foto. Da questa profilazione
genero una wordlist molto più rappresentativa del lessico personale del
target rispetto a un dizionario manuale."
```

**Perché è innovativo (per la commissione di tesi):**
- Nessun tool esistente combina extraction + analysis + wordlist gen in pipeline integrata
- `author_uid` cross-chat è una soluzione originale al problema di re-identificare lo stesso utente in canali diversi con username/display name diversi
- Reverse-geocoding offline + emoji-to-words translator + dynamic Hashcat rules sono feature che CUPP/Mentalist non hanno
- Italian-first NER (spaCy `it_core_news_sm`) → risultati migliori su target italiani rispetto a regex generiche

**Stato sviluppo:**
- ✅ FASE 1 TIH (estrazione + arricchimento dati)
- ✅ FASE 2 Mihawk (visualizzazione + analisi cross-chat)
- ✅ FASE 3 Horcrux (generazione wordlist + Smart Wizard + standalone mode)
- 🟡 FASE 4 JARVIS (questo doc serve a costruirlo) — NON iniziata
- 🟡 FASE 5 Documentazione finale + benchmark vs CUPP per la tesi

**Cosa farà JARVIS quando lo costruiremo:**
- Leggerà questo guide all'avvio per capire la pipeline
- Userà Claude API (preferenza dell'autore) per ragionare sui dati
- Endpoint Mihawk → costruisce profilo target → seleziona feature ottimali → chiama Horcrux
- UI semplice: "dammi questo target → wordlist ottimizzata in output"
- Spiegherà il ragionamento ("ho scelto queste keyword perché...")

**Considerazioni etiche per la tesi:**
- Tutti i tool hanno disclaimer di uso autorizzato (vedi README di ciascuno)
- Il progetto è esplicitamente per **ricerca + pentesting autorizzato + analisi delle proprie chat**
- Output (wordlist) usa solo dati pubblici / di proprietà dell'utente / con consenso

**Repository GitHub:**
- https://github.com/virus212/The-Invisible-Hand
- https://github.com/virus212/Mihawk
- https://github.com/virus212/horcrux

**Scelte di stile da rispettare quando lavori sul progetto:**
- Modifiche chirurgiche, non rewrite di interi file
- Backward compatibility: dati estratti col vecchio TIH devono continuare a funzionare
- Test funzionali leggeri (un curl/script sintetico) > test unitari pesanti
- README aggiornati con sezione "Novità v2.0" — mantenere lo stile già esistente
- Commit message in inglese, descrittivi, senza emoji nel titolo

---

## 0. Pipeline overview

```
┌─────────────────┐      ┌──────────────┐      ┌────────────────┐      ┌──────────┐
│ TheInvisibleHand│ ───▶ │   Mihawk     │ ───▶ │     JARVIS     │ ───▶ │ Horcrux  │
│   (TIH, :5050)  │      │   (:5000)    │      │   (futuro AI)  │      │  (:5100) │
│                 │      │              │      │                │      │          │
│ Estrae chat     │      │ Visualizza + │      │ Sceglie i dati │      │ Genera   │
│ Telegram/WA     │      │ analizza     │      │ giusti per il  │      │ wordlist │
│ + EXIF, NER,    │      │ + cross-chat │      │ profilo target │      │ password │
│   reazioni,     │      │   profili    │      │                │      │          │
│   menzioni,     │      │              │      │                │      │          │
│   forwards,     │      │              │      │                │      │          │
│   author UID    │      │              │      │                │      │          │
└─────────────────┘      └──────────────┘      └────────────────┘      └──────────┘
        │                       │                                             │
        ▼                       ▼                                             ▼
   File system:           File system:                                  File system:
   chat-folder/           (legge da TIH                                 manual_wordlists/
     messages.json          output)                                       <target>.txt
     _users.json
     _forward_map.json
     _mentions_map.json
     attachments/
```

**Auth condivisa:** Token SSO HMAC-firmato in `/tmp/.toji_sso.json` con TTL 12h.
Login una sola volta su un tool, gli altri due ti riconoscono.

**Credenziali default:** `toji` / `lilliv` (override via env `TOJI_USER`/`TOJI_PASS` o per-tool).

---

## 1. TheInvisibleHand (TIH) — Estrazione

**Path:** `/root/Desktop/TheInvisibleHand/`
**Porta:** `5050`
**Comando avvio:** `python3 web_app.py` (oppure `.venv/bin/python web_app.py`)
**Stack:** Flask + Telethon

### 1.1 Input
- **Telegram:** sessione live via Telethon (login con OTP la prima volta)
- **WhatsApp:** file `.zip` esportato dall'app WA
- **Filtri estrazione:** keyword, sender, range date, limit messaggi

### 1.2 Output per ogni canale estratto
```
<output_root>/<NomeChat>/
├── _label.txt                  # nome leggibile chat
├── _progress.json              # checkpoint resume
├── messages.json               # lista messaggi (vedi schema sotto)
├── _users.json                 # profilo aggregato per author_uid
├── _forward_map.json           # author_uid → [chi forwarda da chi, count]
├── _mentions_map.json          # author_uid → [chi menziona, count]
└── attachments/
    ├── images/   <msg_id>_<file>
    ├── videos/   ...
    ├── documents/ ...
    ├── audio/    ...
    └── stickers/ ...
```

### 1.3 Schema messages.json (singolo elemento)
```json
{
  "_": "Message",
  "id": 12345,
  "date": "2024-03-12T14:30:00+00:00",
  "message": "Ciao Marco, ti ho mandato la foto",
  "user_display_name": "Lucia",
  "from_id": {"_": "PeerUser", "user_id": 660381754},
  "peer_id": {"_": "PeerChannel", "channel_id": 12345},
  "author_uid": "tg:user:660381754",            // STABILE — usalo per identificare l'utente
  "attachment_path": "attachments/images/12345_photo.jpg",
  "exif": {                                      // SOLO se foto ha EXIF
    "gps_coords": {"lat": 45.4064, "lon": 11.8768},
    "shot_date": "2024:03:12 14:30:00",
    "device": "Apple iPhone 14"
  },
  "ner_entities": [                              // NER spaCy IT (su msg.message)
    {"text": "Marco", "label": "PER"},
    {"text": "Padova", "label": "LOC"},
    {"text": "Telecom Italia", "label": "ORG"}
  ],
  "mentions": [                                  // @username + inline mention
    {"text": "@marco_r", "user_id": null},
    {"text": "Luca", "user_id": 12345}
  ],
  "forwarded_from": {                            // SOLO se forward
    "type": "channel",                           // user|channel|chat|anonymous
    "source_uid": "tg:channel:1430070602",
    "name": "InterFans"
  },
  "reactions_summary": [                         // SOLO se reazioni
    {"emoji": "👍", "count": 5},
    {"emoji": "❤️", "count": 3}
  ]
}
```

### 1.4 Schema author_uid
- `tg:user:<id>` — Telegram utente (id stabile)
- `tg:channel:<id>` — Telegram canale broadcast
- `tg:chat:<id>` — Telegram gruppo
- `wa:name:<sanitized_name>` — WhatsApp dal .zip (no telefono nei .zip)
- `wa:phone:<E164>` — WhatsApp dal `.crypt15` (TODO: feature 1.6, RINVIATA)

### 1.5 Schema _users.json
```json
{
  "tg:user:660381754": {
    "author_uid": "tg:user:660381754",
    "display_names": ["Lucia", "Lucia M.", "luchina_99"],
    "username_history": ["lucia99", "lulu_22"],
    "first_seen": "2020-06-13T07:07:25+00:00",
    "last_seen": "2026-05-04T18:00:00+00:00",
    "message_count": 1547,
    "media_count": 89,
    "reactions_received": {"👍": 45, "❤️": 23, "🔥": 12}
  }
}
```

### 1.6 Schema _forward_map.json
```json
{
  "tg:user:660381754": [
    {"source_uid": "tg:channel:1430070602", "source_name": "InterFans", "count": 6},
    {"source_uid": null, "source_name": "Hidden Channel", "count": 3}
  ]
}
```

### 1.7 Schema _mentions_map.json
```json
{
  "tg:user:660381754": [
    {"target": "@luca", "user_id": null, "count": 12},
    {"target": "Mario", "user_id": 99887766, "count": 4}
  ]
}
```

### 1.8 API endpoints (per orchestrazione AI)
- `GET /api/chats` — lista dialog Telegram
- `POST /api/download` body `{chat_id, options}` → avvia estrazione, ritorna `{job_id}`
- `GET /api/jobs` — stato di tutti i job
- `GET /api/progress/stream` (SSE) — eventi live
- `POST /api/jobs/<id>/<action>` — pause|resume|stop|restart
- `POST /api/whatsapp/import` (multipart `.zip`)

### 1.9 Default output dir
```
~/Desktop/Mihawk---chat-explorer-and-analyzer-main/
```
(controllato da env `INVISIBLEHAND_OUTPUT_DIR`)

---

## 2. Mihawk — Visualizzazione + analisi

**Path:** `/root/Desktop/Mihawk---chat-explorer-and-analyzer-main/`
**Porta:** `5000`
**Comando avvio:** `python3 web_app.py`
**Stack:** Flask + Vanilla JS

### 2.1 Input
- Cartelle canali prodotte da TIH (legge `messages.json` + i file aggregate)
- **Auto-discovery:** scansiona `APP_DIR` per sottocartelle con `messages.json`

### 2.2 API endpoints (per JARVIS)
| Endpoint | Metodo | Risposta |
|----------|--------|----------|
| `/api/channels` | GET | `[{id, name, count, has_wordlist}]` |
| `/api/messages?channel=X&page=N&author=Y&date_from=&date_to=` | GET | `{total, pages, messages: [...]}` |
| `/api/search?q=regex&channel=X&author=Y` | GET | `{total, results: [{...msg, snippet}]}` |
| `/api/context/<channel>/<msg_id>?size=10` | GET | `{target_index, messages: [...]}` |
| `/api/stats?channel=X` | GET | `{total_messages, unique_authors, top_authors, by_year}` |
| `/api/authors?channel=X&q=partial` | GET | `[{name, count}]` |
| `/api/refresh` | POST | rescans dir |
| `/api/summary/<channel>` | GET | **NUOVO** — sintesi canale (vedi 2.3) |
| `/api/user/<author_uid>` | GET | **NUOVO** — profilo cross-chat (vedi 2.4) |
| `/api/heatmap/<channel\|_all>/<author_uid>` | GET | **NUOVO** — griglia attività (vedi 2.5) |
| `/media/<channel>/<subdir>/<file>` | GET | serve attachment binario |

### 2.3 GET /api/summary/<channel>
Risposta:
```json
{
  "channel": "Omar",
  "top_persons":   [["Marco", 12], ["Lucia", 8]],
  "top_locations": [["Padova", 6], ["Milano", 3]],
  "top_orgs":      [["Telecom Italia", 2]],
  "top_mentions":  [["@luca", 23], ["Mario", 8]],
  "top_forwards":  [["InterFans", 6], ["RoyaleAPI", 3]],
  "top_emojis":    [["👍", 45], ["❤️", 23]],
  "users_count": 12
}
```

### 2.4 GET /api/user/<author_uid>
Aggregato cross-chat scansionando TUTTI i `_users.json`:
```json
{
  "author_uid": "tg:user:660381754",
  "display_names": [...],
  "username_history": [...],
  "first_seen": "...", "last_seen": "...",
  "total_messages": 1547,
  "total_media": 89,
  "channels": [{"channel_id", "channel_name", "messages", "media", "first_seen", "last_seen"}],
  "top_emojis": [["👍", 100], ...],
  "top_mentions_made": [["@luca", 12], ...],
  "top_forwards_from": [["InterFans", 6], ...]
}
```

### 2.5 GET /api/heatmap/<channel_or__all>/<author_uid>
```json
{"grid": [[0,0,...,5,3,0],[...]], "total": 51, "max_cell": 20}
```
Griglia 7×24: `grid[weekday][hour]` (weekday 0=lunedì).

### 2.6 Messaggio API (response shape)
Mihawk arricchisce ogni msg con `media` strutturato + propaga TIH fields:
```json
{
  "id": 12345,
  "author": "Lucia",
  "date": "2024-03-12T14:30:00",
  "date_ts": 1710257400,
  "text": "...",
  "channel": "Omar",
  "channel_name": "Omar",
  "media": {"type": "photo", "url": "/media/Omar/images/123_photo.jpg"},
  "author_uid": "tg:user:660381754",
  "exif": {...}, "ner_entities": [...], "mentions": [...],
  "forwarded_from": {...}, "reactions_summary": [...]
}
```

---

## 3. Horcrux — Generazione wordlist password

**Path:** `/root/Desktop/Horcrux/`
**Porta:** `5100`
**Comando avvio:** `.venv/bin/python web_app.py`
**Stack:** Flask + Vanilla JS + spaCy + 9 moduli OSINT

### 3.1 Modalità d'uso
1. **Auto da chat:** seleziona canale → estrae feature → genera
2. **Manual wizard:** `/manual` — 16 campi (nome, partner, animali, ecc.)
3. **Standalone (NUOVO):** nessuna chat, compila manualmente o via OSINT inline → genera

### 3.2 Flusso classico (auto)
```
GET  /api/channels                                 # lista canali disponibili
GET  /api/extract?channel=X&author=optional_uid    # estrae features (TIH-enriched)
POST /api/count                                    # live count
POST /api/generate                                 # genera + salva wordlist.txt
GET  /api/export/<channel>/<fmt>                   # txt|hashcat|john|json
```

### 3.3 Schema features estratte da `/api/extract`
```json
{
  "names": ["Marco", "Lucia"],
  "dates": ["1995", "2024"],
  "numbers": [...],
  "phones": [...],
  "ages_birth_years": ["1995", "95"],
  "animals": ["cane", "gatto"],
  "keywords": [...],
  "brands": ["spotify", "ferrari"],
  "nicknames": ["amore"],
  "phrases": ["amore mio"],
  "topics": {"gaming": 5, "amore": 3},
  "emojis": ["👍", "❤️"],
  "authors": ["Lucia"],
  "message_count": 1547,
  // ── Campi nuovi (presenti se TIH ha estratto coi dati arricchiti) ──
  "ner_persons":   ["Marco", "Lucia"],     // PER spaCy
  "ner_locations": ["Padova", "Milano"],   // LOC spaCy
  "ner_orgs":      ["Telecom Italia"],     // ORG spaCy
  "gps_cities":    ["padova"],             // reverse-geocode da exif.gps_coords
  "mentions":      ["luca", "mario"],      // top mentions made by author
  "forward_topics":["interfans"],          // canali da cui forwarda
  "emoji_keywords":["calcio", "fuoco"]     // top emoji tradotte in IT/EN
}
```

### 3.4 POST /api/generate (corpo richiesta)
```json
{
  "channel": "Omar",                  // oppure "_standalone"
  "level": "easy|medium|hard",
  "manual_keys": ["extra1", "extra2"],
  "features": { ... },                // optional, override
  "leet_level": "auto|off|base|advanced",
  "exclude_common": true,
  "exclude_extra": ["mario1990", "ciao123"],
  "target_name": "mario"              // SOLO in modalità _standalone
}
```
Risposta:
```json
{
  "count": 1553,
  "drop_stats": {"too_short": 169, "common": 14, "user_excluded": 2, ...},
  "preview": ["Marco", "marco1", "Marco@", ...],   // top 30
  "saved": "/path/to/wordlist.txt"
}
```

### 3.5 Modalità Standalone (no chat)
Il client manda `channel: "_standalone"` + `features` precompilato + `target_name`. La wordlist va in `manual_wordlists/<target>.txt`. Utile per JARVIS quando ha solo dati OSINT, no archive chat.

### 3.6 Score categorie (per JARVIS che vuole capire ranking)
Score base usato per il sort probabilistico:
```python
{
  "names": 0.95, "ner_persons": 0.92, "nicknames": 0.85, "animals": 0.85,
  "ages_birth_years": 0.85, "dates": 0.80, "gps_cities": 0.78,
  "brands": 0.70, "ner_orgs": 0.65, "ner_locations": 0.62,
  "phones": 0.60, "mentions": 0.58, "topics": 0.55, "emoji_keywords": 0.52,
  "keywords": 0.50, "forward_topics": 0.45, "numbers": 0.40, "emojis": 0.30
}
```

### 3.7 OSINT API endpoints
| Endpoint | Body | Output |
|----------|------|--------|
| `POST /api/osint/phone` | `{phone}` | operatore IT, country, password_tokens |
| `POST /api/osint/email` | `{email}` o `{text}` | provider, pattern, password_tokens |
| `POST /api/osint/locations` | `{text}` | città IT rilevate |
| `POST /api/osint/usernames` | `{nome, cognome, anno, nickname}` | 80+ varianti |
| `POST /api/osint/social-check` | `{username, sites}` | check 35+ siti |
| `POST /api/osint/whois` | `{domain}` | WHOIS info |
| `POST /api/osint/dns` | `{domain}` | A/AAAA/MX/NS records |
| `POST /api/osint/ip-geo` | `{ip}` | geolocation |
| `POST /api/osint/wayback` | `{url}` | snapshot list |
| `POST /api/osint/email-rep` | `{email}` | reputation (EmailRep API) |
| `POST /api/osint/github-user` | `{username}` | profilo |
| `POST /api/osint/reddit-user` | `{username}` | profilo |
| `POST /api/osint/codice-fiscale` | `{cf}` | parse: data nascita, comune, tokens |
| `POST /api/exclusion/parse` | `{text}` | normalizza wordlist esclusione |

### 3.8 File generati per canale
```
<channel>/
├── wordlist.txt                  # output ultimo .generate
├── _horcrux_profile.json          # features modificate dall'utente
└── _horcrux_history/              # archivio generazioni passate
    └── 2026-05-04T18-00-00_medium_3247.txt
```

---

## 4. Workflow tipici per JARVIS

### 4.1 Profilare un target a partire da author_uid noto
```bash
# 1. Profilo cross-chat
GET /api/user/tg:user:660381754                     # Mihawk

# 2. Pattern attività
GET /api/heatmap/_all/tg:user:660381754             # Mihawk

# 3. Feature estratte sui canali in cui appare
GET /api/extract?channel=Omar&author=tg:user:660381754   # Horcrux

# 4. Generazione wordlist
POST /api/generate {channel: "Omar", author_uid: "tg:user:660381754", level: "medium"}
```

### 4.2 Profilare da OSINT puro (no chat)
```bash
# 1. Lookup vari
POST /api/osint/phone {phone: "+39 333 1234567"}
POST /api/osint/codice-fiscale {cf: "RSSMRA85M01H501Z"}
POST /api/osint/locations {text: "Padova Milano"}

# 2. Genera in standalone
POST /api/generate {
  channel: "_standalone",
  target_name: "mario",
  features: {names: ["Mario"], ages_birth_years: ["1985"], ...}
}
```

### 4.3 Sintesi rapida di un canale per orientarsi
```bash
GET /api/summary/Omar                  # Mihawk top persons/locations/forwards/emoji
```

---

## 5. Constraint e gotchas per AI

- **NON re-estrarre** se i campi TIH-enriched sono già in `messages.json` → leggi direttamente `ner_entities`, `exif`, ecc.
- **author_uid è la chiave universale** — usa sempre quello, NON `user_display_name` (può cambiare nel tempo).
- **Standalone mode** richiede `target_name` non vuoto, altrimenti 400.
- **Backward compat:** canali estratti col vecchio TIH non hanno `_users.json` né i campi enriched. Il codice degrada gracefully (campi semplicemente assenti).
- **Rate limit Horcrux:** 30 req/min su `/api/generate`, `/api/count`. Usare `/api/count` per preview, non chiamare `/api/generate` ogni keystroke.
- **Exclusion list:** max 50.000 voci, max 5 MB di testo grezzo.
- **NER false positives:** il modello `it_core_news_sm` ha rumore (es. "Cmq" classificato come PER). Filtrare a posteriori se serve.
- **Reverse geocoding GPS:** funziona solo entro 30 km dalle ~60 città IT/UE embedded. Foto fuori → `gps_cities` vuoto.
- **EXIF GPS è raro** in foto WhatsApp/Telegram (di solito strippano metadata). Aspettati `exif: null` per la maggioranza.

---

## 6. Versioning / cambiamenti recenti

**v2.0 (2026-05-04):** TIH/Mihawk/Horcrux uniti via `author_uid`. Aggiunti EXIF, NER, reazioni, forward tracing, mentions, emoji translator, leet avanzato, wordlist exclusion, standalone mode, smart wizard summary panel.

**Roadmap:**
- 1.5 Whisper trascrizione audio (RINVIATO)
- 1.6 WhatsApp `.crypt15` decrypt (RINVIATO)
- FASE 4: JARVIS AI orchestrator (questo documento serve a costruirlo)
