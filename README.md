<div align="center">

<img src="static/stemma.png" alt="Horcrux" width="180" />

# 🜲 Horcrux

**Targeted password wordlist generator from chat archives, manual input, or OSINT lookup.**

*il frammento dell'anima*

[![Python](https://img.shields.io/badge/Python-3.10+-blue.svg?logo=python&logoColor=white)](https://www.python.org/)
[![Flask](https://img.shields.io/badge/Flask-3.0+-000000.svg?logo=flask&logoColor=white)](https://flask.palletsprojects.com/)
[![License](https://img.shields.io/badge/License-MIT-yellow.svg)](LICENSE)
[![Status](https://img.shields.io/badge/Status-active-success.svg)]()
[![Platform](https://img.shields.io/badge/Platform-Linux%20%7C%20macOS-lightgrey.svg)]()

[Quickstart](#-quickstart) · [Features](#-features) · [Architecture](#-architecture) · [API](#-api-reference) · [Security](#-security) · [License](#-license)

</div>

---

## 🆕 Novità v2.5 (2026-05-04)

**PassGPT Hybrid + dialetti italiani + wordlists manager**:

- 🤖 **PassGPT integration (Mode C)** — re-ranking ML hybrid via `javirandor/passgpt-10characters` (~58M params, USENIX 2024). Generazione condizionale + score di "umanità" (log-likelihood). Toggle `use_ml` in UI + API. Lazy load + singleton cache (cold-start ~5-10s solo prima invocazione). CPU-only torch sufficiente. Vedi `ml_generator.py`.
- 🇮🇹 **Italian dialect mutations** — 30+ trasformazioni texting IT (`che→ke`, `perché→xké`, `casa→kasa`, `qualcosa→qualkosa`, ecc.). Le mutazioni si applicano automaticamente in `medium`/`hard`. Cattura il "lessico chat reale" del target. Vedi `IT_DIALECT_MAP` in `generator.py`.
- 📋 **Wordlists Manager** (`/wordlists`) — pagina standalone con tabella di tutte le wordlist generate (channel, count, size, modified, history). Download in 4 formati + delete con doppia conferma e flag `?with_history=1`.
- 📦 **Cross-app proxy** — JARVIS espone `/api/wordlist/<channel>/<fmt>` come proxy verso Horcrux export, così il dashboard JARVIS può scaricare wordlist senza aprire Horcrux.
- 🧠 **`_full_text(msg)` helper in TextAnalyzer** — combina `message + ocr_text + transcription`, così tutte le feature (`names`, `keywords`, `leaked_passwords`, ...) lavorano automaticamente sul testo arricchito (OCR delle immagini, trascrizione audio).

## 🆕 Novità v2.0 (2026-05-04)

**Smart Wizard** — l'auto wizard è stato esteso per essere usabile anche come password generator standalone:

- 🎯 **7 nuove feature TIH-enriched** — persone NER, luoghi NER, organizzazioni, città GPS, menzioni, forward sources, emoji-keywords
- 🆔 **Filtro per `author_uid`** — invece che per nome (es. `tg:user:660381754` resta stabile)
- 🌍 **Reverse geocoding offline** — coordinate GPS dalle foto → città italiana (60+ città in dataset)
- 🔤 **Emoji translator** — ⚽→[calcio,football], 🔥→[fuoco,fire]: le top emoji del target diventano keyword
- 🎲 **Leet substitution avanzata** — base (cifre) o advanced (`@`,`$`,`+`,`9`,`8`,`2`)
- 🚫 **Wordlist exclusion** — filtra password top comuni (rockyou) + upload custom
- ⚡ **Hashcat/John rules dinamiche** — generate dalle feature target (anni rilevati → year-append, topic gaming → `$T$T$V`)
- 🆕 **Modalità Standalone** — funziona senza chat: compili manualmente o via Quick OSINT, generi wordlist
- 🚀 **Quick OSINT inline** — phone/email/CF/location/username lookup direttamente nel wizard, token aggiunti automaticamente
- 📋 **Riepilogo features** pre-generazione — vista compatta con count, preview, edit-shortcut, settings

Per orchestrazione AI vedi **[`/root/Desktop/AGENT_GUIDE.md`](../AGENT_GUIDE.md)**.

---

## 📖 Overview

**Horcrux** is the third tool in a trilogy designed for OSINT-driven password security research:

```
TheInvisibleHand → Mihawk → Horcrux
   (extract)       (index)    (profile + generate)
```

It generates **targeted password wordlists** by analyzing chat archives, accepting manual input via a guided wizard, or performing OSINT lookups on public sources. Built as a thesis project for cybersecurity research, it demonstrates how language patterns and personal data can be weaponized for password attacks — and conversely, how users unknowingly expose themselves.

---

## ✨ Features

### 🔍 Three input modes

|   | Mode | Description |
|---|------|-------------|
| 🔬 | **Auto** | Extracts features from chat archives (Mihawk format) — names, dates, animals, brands, topics, emojis |
| ✍️ | **Manual** | 16-step guided wizard — no chat data required |
| 🌐 | **OSINT** | Auto-fill from `Codice Fiscale`, GitHub username, email, IP, phone — pre-populates all fields |

### 🧠 Smart text analysis pipeline

- Single-pass tokenization with full metadata (frequency, position, sources, confidence)
- 500+ Italian + English stopwords, including verb conjugations
- Italian stemming (consolidates plurals: `gatti+gatto` → `gatto`)
- Spam pattern filter (`ahaha`, `lolol`, repeated chars)
- False-positive filter for proper names (excludes sentence-start-only Title Case)

### 🎯 Probabilistic ranking

Each generated password is scored:

```
score = base_category × position_decay × mutation_decay
```

Top of the wordlist = most likely candidates → faster cracking in time-limited scenarios.

### 🔬 OSINT enrichment

| Offline (no network) | Online (free APIs) |
|----------------------|---------------------|
| 90 country phone codes | WHOIS lookup |
| IT mobile operator detection | DNS records |
| 200+ Italian cities (CAP, province) | IP geolocation |
| Email pattern detection | Wayback Machine search |
| Codice Fiscale parser (DOB extraction) | Email reputation |
| Username variant generator (80+) | GitHub/Reddit profiles |
| | 35-site username availability check |

### 🔓 Built-in cracking simulator

Hash `MD5/SHA1/SHA256/SHA512` against the generated wordlist directly in the UI. Useful for self-testing the wordlist quality.

### 🌒 Other

- **Single Sign-On** across the trilogy (file-based HMAC token in `/tmp/.toji_sso.json`)
- **Live counter** — see wordlist size update as you edit features
- **Stats dashboard** — length distribution, leet %, special chars %, etc.
- **History** — auto-archive each generation with timestamp
- **Export formats** — `.txt`, hashcat rules, john rules, JSON report
- **Path traversal protection**, rate limiting, CSRF, input validation
- **Dark ritual UI** — animated runes, sigil ring, glowing stemma

---

## 🚀 Quickstart

### Prerequisites

- Python 3.10+
- `bash`
- (optional) `whois`, `dig` — for online OSINT tools

### Installation

```bash
git clone git@github.com:virus212/Horcrux.git
cd Horcrux
chmod +x horcrux
./horcrux
```

The launcher will:
1. Auto-create a Python venv
2. Install `Flask`
3. Prompt for the port (default `5100`)
4. Open the browser

### Default credentials

```
user: toji
pass: lilliv
```

⚠️ **Override in production:**

```bash
export HORCRUX_USER="myuser"
export HORCRUX_PASS="$(openssl rand -hex 16)"
export HORCRUX_SECRET="$(openssl rand -hex 32)"
./horcrux
```

---

## 🏗️ Architecture

```
┌────────────────────────────────────────────────────────────────┐
│                      Browser UI                                 │
│              (vanilla JS, no build step)                        │
└─────────────────────────┬──────────────────────────────────────┘
                          │ HTTP/SSE
┌─────────────────────────▼──────────────────────────────────────┐
│                       web_app.py                                │
│        Flask routes · auth · validation · CSRF · rate-limit    │
└──────┬──────────────────┬─────────────────┬───────────────┬────┘
       │                  │                 │               │
       ▼                  ▼                 ▼               ▼
┌─────────────┐   ┌──────────────┐  ┌─────────────┐  ┌──────────┐
│text_analyzer│   │  generator   │  │   osint/    │  │  sso.py  │
│   pipeline  │   │  + scoring   │  │  9 modules  │  │  shared  │
└─────────────┘   └──────────────┘  └─────────────┘  └──────────┘
       │                                  │
       ▼                                  ▼
   messages.json                     Internet APIs
   (Mihawk format)              (whois, ipapi.co, ...)
```

### Key files

| Path | Purpose |
|------|---------|
| `text_analyzer.py` | Core NLP pipeline (tokenize → categorize → score) |
| `generator.py` | Mutation engine + probabilistic ranking |
| `extractor.py` | Thin wrapper for chat archive ingestion |
| `web_app.py` | Flask routes, ~50 endpoints |
| `web_helpers.py` | Decorators (rate-limit, CSRF, cache, logging) |
| `sso.py` | Cross-app HMAC token-based SSO |
| `osint/phone_intel.py` | IT operator + 90 country codes |
| `osint/geo_intel.py` | 200+ Italian cities embedded |
| `osint/email_intel.py` | Pattern detection + 30 providers |
| `osint/username_gen.py` | Generates 80+ username variants |
| `osint/social_check.py` | Sherlock-style 35-site check |
| `osint/online_intel.py` | WHOIS, DNS, IP-geo, Wayback, EmailRep, GitHub, Reddit, CF |

---

## 📡 API Reference

### Channel & extraction

| Method | Endpoint | Description |
|--------|----------|-------------|
| `GET` | `/api/channels` | List Mihawk channels |
| `GET` | `/api/extract?channel=X` | Extract features |
| `POST` | `/api/extract-multi` | Multi-channel author merge |
| `POST` | `/api/count` | Live wordlist count |
| `POST` | `/api/generate` | Generate wordlist |
| `GET` | `/api/stats/<channel>` | Wordlist statistics |
| `POST` | `/api/search` | Search messages with context |
| `GET` | `/api/export/<ch>/<fmt>` | Export `txt\|hashcat\|john\|json` |

### Manual wizard

| Method | Endpoint | Description |
|--------|----------|-------------|
| `GET` | `/manual` | Wizard UI |
| `POST` | `/api/manual-generate` | Generate from manual fields |

### OSINT

| Method | Endpoint | Description |
|--------|----------|-------------|
| `POST` | `/api/osint/phone` | Phone enrichment |
| `POST` | `/api/osint/email` | Email parsing + reputation |
| `POST` | `/api/osint/locations` | Italian geo detection |
| `POST` | `/api/osint/usernames` | Username variants |
| `POST` | `/api/osint/social-check` | 35-site Sherlock-style |
| `POST` | `/api/osint/whois` | WHOIS lookup |
| `POST` | `/api/osint/dns` | DNS records |
| `POST` | `/api/osint/ip-geo` | IP geolocation |
| `POST` | `/api/osint/wayback` | Wayback Machine |
| `POST` | `/api/osint/email-rep` | Email reputation |
| `POST` | `/api/osint/github-user` | GitHub profile |
| `POST` | `/api/osint/reddit-user` | Reddit profile |
| `POST` | `/api/osint/codice-fiscale` | Italian tax code parser |

### Cracking & profile

| Method | Endpoint | Description |
|--------|----------|-------------|
| `POST` | `/api/crack` | Test hash against wordlist |
| `POST` | `/api/profile/save` | Save edited features |
| `GET` | `/api/profile/load/<ch>` | Load saved profile |

---

## ⚙️ Configuration

All settings via environment variables:

| Variable | Default | Description |
|----------|---------|-------------|
| `HORCRUX_PORT` | `5100` | HTTP port |
| `HORCRUX_HOST` | `0.0.0.0` | Bind address |
| `HORCRUX_MIHAWK_DIR` | `~/Desktop/Mihawk-...` | Path to Mihawk channels |
| `HORCRUX_USER` | `toji` | Login username |
| `HORCRUX_PASS` | `lilliv` | Login password |
| `HORCRUX_SECRET` | random | Flask session key |
| `HORCRUX_LOG_DIR` | `~/.horcrux/logs` | Log directory |
| `TOJI_SSO_KEY` | dev key | HMAC SSO key (shared with Mihawk/TIH) |
| `TOJI_SSO_TTL` | `43200` | SSO token TTL (sec) |

### CLI flags

```bash
./horcrux                 # normal start
./horcrux --port 8080     # custom port
./horcrux --install-global # symlink to /usr/local/bin/
./horcrux --help
```

---

## 🔒 Security

- ✅ Path traversal protection (`safe_path()` on all channel paths)
- ✅ Input validation (max length 500 / 50K / 200 elements)
- ✅ Try/except wrapper on all endpoints (`@safe_endpoint`)
- ✅ Rate limiting in-memory: 30 req/min on heavy endpoints
- ✅ CSRF protection (Origin/Referer check on POST)
- ✅ Default credentials warning at startup
- ✅ Logging with rotation (`~/.horcrux/logs/server.log`)
- ✅ Cache invalidation via mtime on `messages.json`
- ✅ HMAC-signed SSO tokens, file perms 0600

> ⚠️ **Do not expose to the public internet without a reverse proxy** (nginx + WSGI). Designed for local/LAN use during research.

---

## 📊 Demo

Generated wordlist for `Marco Rossi`, born 1990:

```
Top 10 (probabilistic ranking):
 1. Marco
 2. Marco1990
 3. Marco90
 4. Rossi
 5. Marco_1990
 6. MarcoRossi
 7. marco90
 8. Marco_90
 9. Marco1990!
10. Marco.1990
```

With OSINT-detected gaming topic added:

```
+ MarcoTTV
+ MarcoPro
+ xXMarcoXx
+ Marco_yt
+ MarcoGamer
```

---

## 💡 Use cases

### 1. Wordlist mirata da chat archive (workflow tipico)
1. Estrai un canale con TheInvisibleHand
2. Apri Mihawk per esplorare e identificare il target (`author_uid`)
3. In Horcrux: seleziona il canale → "Estrai Features" → modifica le card → "Genera Wordlist"
4. Esporta come `.rule` Hashcat per attacco mirato

### 2. Standalone per investigatore (no chat)
Hai solo dati esterni del target (telefono, email, codice fiscale, città)?
1. Click "🆕 Modalità Standalone" + nome target
2. Inserisci i dati noti → "Quick OSINT Lookup" → token aggiunti automaticamente
3. Genera la wordlist (salvata in `manual_wordlists/<target>.txt`)

Ottimo per: penetration testing engagement con info OSINT raccolte da fonti esterne.

### 3. Profilo cross-chat (target appare in più gruppi)
Estrai più canali con TIH → tutti sono linkati via `author_uid`. In Horcrux: filtra per `tg:user:<id>` invece che per nome → feature aggregate da tutti i canali in cui appare.

### 4. Hash cracking simulator integrato
Hai un hash MD5/SHA1/SHA256/SHA512 e vuoi vedere se la tua wordlist lo crackare?
- Genera la wordlist nel canale del target
- Tab "Cracking Simulation" → incolla l'hash → vedi se è incluso

### 5. Benchmark vs CUPP (per la tesi)
Genera una wordlist con Horcrux su un dataset reale + una con CUPP solo da nome+anno. Confronta l'hit rate contro hash leakati. Il vantaggio di Horcrux è proporzionale alla ricchezza dei dati chat disponibili.

---

## 🛠 Troubleshooting

| Problema | Soluzione |
|---|---|
| `extract` ritorna `message_count: 0` | Il filtro autore non matcha. Prova: senza filtro (canale intero), oppure con il display name esatto, oppure con `author_uid` se hai TIH v2.0. |
| Wordlist troppo piccola in Easy | Easy non applica leet/combo. Sali a Medium o Hard. Oppure forza `leet_level: advanced` nei settings avanzati. |
| Hashcat rule export sembra generico | Le regole dinamiche dipendono dalle features detected. Su un canale con poca conversazione (es. 50 msg) ci sono pochi anni/topic da inferire. Più dati = regole più ricche. |
| `gps_cities` sempre vuoto | Il reverse-geocoding lavora solo entro 30 km dalle ~60 città italiane/UE embedded. Foto fuori bounding box → no match. |
| NER produce nomi strani come "Cmq", "Negro" | Limite del modello `it_core_news_sm` (small). Falsi positivi tipici. Per migliorare: scarica `it_core_news_md` o `lg`, ma serve modificare `ner.py` di TIH. |
| Modalità standalone "channel not found" | Il pulsante manda channel `_standalone` automaticamente. Se vedi 404, ricarica la pagina e ri-clicca il bottone Standalone. |
| Live counter sempre `?` | Probabilmente `state.features` vuoto. Premi "Estrai Features" oppure compila a mano almeno una categoria. |
| Telegram credentials richieste | NO — Horcrux non accede a Telegram. Solo TIH lo fa. Horcrux legge dati già estratti da disco. |
| `manual_wordlists/<file>.txt` non trovato | Il salvataggio standalone va in `<HORCRUX_DIR>/manual_wordlists/`. Verifica permessi scrittura. |

---

## 🤝 Sibling projects

| Project | Color | Role |
|---------|-------|------|
| [🩸 **Mihawk**](https://github.com/virus212/Mihawk---chat-explorer-and-analyzer) | red | Chat explorer & analyzer |
| [🌊 **TheInvisibleHand**](https://github.com/virus212/The-Invisible-Hand) | blue | Telegram/WhatsApp extractor |
| 🜲 **Horcrux** *(this repo)* | silver | Wordlist generator |

A unified launcher (`TheDarkTriad`) controls all three.

---

## ⚖️ Ethics

Horcrux is an **educational tool for cybersecurity research and authorized penetration testing**.

✅ **Acceptable use**:
- Personal archives you own
- Authorized pentesting engagements
- Security awareness training
- Academic research

❌ **Forbidden**:
- Unauthorized attacks
- Stalking / harassment
- Privacy violations

The OSINT modules use only **publicly accessible APIs** — same data a human could view manually.

---

## 📝 License

MIT — see [LICENSE](LICENSE).

---

## 👤 Author

**virus212** — *cybersecurity research & thesis project*

If you use Horcrux in research or publish a paper, a citation/credit is appreciated. ⬢
