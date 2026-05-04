// HORCRUX · Frontend App

const app = {
  state: {
    channels: [],
    selectedChannel: null,
    selectedAuthor: null,
    channelAuthors: [],
    isGroup: false,
    multiChannel: false,
    features: null,
    generatedLevel: "easy",
    countDebounceTimer: null,
  },

  async init() {
    await this.loadChannels();
    this.attachEventListeners();

    // Auto-select channel from query parameter (Mihawk integration)
    const urlParams = new URLSearchParams(window.location.search);
    const channelParam = urlParams.get("channel");
    if (channelParam) {
      const ch = this.state.channels.find(c => c.id === channelParam);
      if (ch) {
        this.selectChannel(ch.id, ch.name);
      }
    }
  },

  async loadChannels() {
    try {
      const res = await fetch("/api/channels");
      this.state.channels = await res.json();
      this.renderChannels();
    } catch (e) {
      console.error("Error loading channels:", e);
      document.getElementById("channelsList").innerHTML = "<p>Errore nel caricamento</p>";
    }
  },

  renderChannels() {
    const list = document.getElementById("channelsList");
    if (!this.state.channels.length) {
      list.innerHTML = "<p style='color: var(--text-dim); padding: 20px 0;'>Nessun canale</p>";
      return;
    }
    list.innerHTML = this.state.channels
      .map(ch => `<div class="channel-item" data-channel-id="${ch.id}" data-channel-name="${ch.name}">
        ${ch.name}
        <div style="font-size: 10px; color: var(--text-dim);">
          ${ch.message_count} msg ${ch.is_group ? '· 👥 GRUPPO' : ''} ${ch.has_wordlist ? '· ✓' : ''}
        </div>
      </div>`)
      .join("");

    document.querySelectorAll(".channel-item").forEach(el => {
      el.addEventListener("click", () => this.selectChannel(el.dataset.channelId, el.dataset.channelName));
    });
  },

  selectChannel(channelId, channelName) {
    this.state.selectedChannel = channelId;
    this.state.selectedAuthor = null;
    this.state.multiChannel = false;
    document.querySelectorAll(".channel-item").forEach(el => el.classList.remove("active"));
    document.querySelector(`[data-channel-id="${channelId}"]`).classList.add("active");

    document.getElementById("mainView").classList.add("hidden");
    document.getElementById("contentView").classList.remove("hidden");
    document.getElementById("channelName").textContent = channelName;

    const ch = this.state.channels.find(c => c.id === channelId);
    document.getElementById("messageCount").textContent = ch.message_count;

    this.state.isGroup = ch.is_group;
    this.state.channelAuthors = ch.authors || [];

    const selectorSection = document.getElementById("userSelectorSection");
    const userSelect = document.getElementById("userSelect");
    document.getElementById("multiChannelCheckbox").checked = false;

    if (this.state.isGroup && this.state.channelAuthors.length > 1) {
      selectorSection.classList.remove("hidden");
      userSelect.innerHTML = '<option value="">-- Tutti gli utenti --</option>';
      this.state.channelAuthors.forEach(author => {
        const option = document.createElement("option");
        option.value = author;
        option.textContent = author;
        userSelect.appendChild(option);
      });
      document.getElementById("userHint").textContent =
        `${this.state.channelAuthors.length} partecipanti.`;
    } else {
      selectorSection.classList.add("hidden");
    }

    // Hide all dynamic sections
    ["multiChannelBanner", "topicsSection", "featuresSection",
     "generatorSection", "outputSection", "statsSection", "crackSection"]
      .forEach(id => document.getElementById(id).classList.add("hidden"));
  },

  attachEventListeners() {
    document.getElementById("extractBtn").addEventListener("click", () => this.extract());
    document.getElementById("generateBtn").addEventListener("click", () => this.generate());
    document.getElementById("crackBtn").addEventListener("click", () => this.crack());
    document.getElementById("saveProfileBtn").addEventListener("click", () => this.saveProfile());
    document.getElementById("loadProfileBtn").addEventListener("click", () => this.loadProfile());
    document.getElementById("searchBtn").addEventListener("click", () => this.search());
    document.getElementById("enrichOsintBtn").addEventListener("click", () => this.enrichOsint());
    document.getElementById("addOsintTokensBtn").addEventListener("click", () => this.addOsintTokens());
    document.getElementById("socialCheckBtn").addEventListener("click", () => this.socialCheck());

    // ── Quick OSINT inline lookups (Smart Wizard) ──
    document.querySelectorAll(".quick-btn").forEach(btn => {
      btn.addEventListener("click", () => this.quickOsintLookup(btn.dataset.quick));
    });

    // ── Standalone mode (no chat) ──
    const standaloneBtn = document.getElementById("standaloneBtn");
    if (standaloneBtn) {
      standaloneBtn.addEventListener("click", () => this.enterStandaloneMode());
    }

    // ── Summary card toggle + listeners (Smart Wizard recap) ──
    const summaryHeader = document.querySelector(".summary-header");
    if (summaryHeader) {
      summaryHeader.addEventListener("click", () => {
        document.getElementById("featuresSummary").classList.toggle("collapsed");
      });
    }
    // Aggiorna riepilogo quando cambiano settings (leet/excludes)
    ["leetLevelSelect", "excludeCommonCheck", "excludeExtraInput", "manualKeysInput"].forEach(id => {
      const el = document.getElementById(id);
      if (el) {
        el.addEventListener("input", () => this.renderFeaturesSummary());
        el.addEventListener("change", () => this.renderFeaturesSummary());
      }
    });

    document.getElementById("searchInput").addEventListener("keypress", (e) => {
      if (e.key === "Enter") {
        e.preventDefault();
        this.search();
      }
    });

    document.getElementById("socialUsernameInput").addEventListener("keypress", (e) => {
      if (e.key === "Enter") {
        e.preventDefault();
        this.socialCheck();
      }
    });

    // Online tools tabs
    document.querySelectorAll(".tool-tab").forEach(tab => {
      tab.addEventListener("click", () => {
        document.querySelectorAll(".tool-tab").forEach(t => t.classList.remove("active"));
        tab.classList.add("active");
        this.state_osint.activeTool = tab.dataset.tool;
        this.updateToolUI();
      });
    });

    document.getElementById("toolRunBtn").addEventListener("click", () => this.runTool());
    document.getElementById("toolInput").addEventListener("keypress", (e) => {
      if (e.key === "Enter") {
        e.preventDefault();
        this.runTool();
      }
    });

    document.getElementById("userSelect").addEventListener("change", (e) => {
      this.state.selectedAuthor = e.target.value || null;
    });

    document.getElementById("multiChannelCheckbox").addEventListener("change", (e) => {
      this.state.multiChannel = e.target.checked;
    });

    document.querySelectorAll("input[name='level']").forEach(radio => {
      radio.addEventListener("change", (e) => {
        this.state.generatedLevel = e.target.value;
        this.updateLiveCounter();
      });
    });

    document.getElementById("manualKeysInput").addEventListener("input", () => {
      this.updateLiveCounter();
    });

    // Export buttons
    document.querySelectorAll(".export-actions button").forEach(btn => {
      btn.addEventListener("click", () => {
        const format = btn.dataset.format;
        if (format && this.state.selectedChannel) {
          window.location.href = `/api/export/${this.state.selectedChannel}/${format}`;
        }
      });
    });
  },

  async extract() {
    if (!this.state.selectedChannel) return;

    const btn = document.getElementById("extractBtn");
    btn.disabled = true;
    btn.textContent = "Estrazione in corso…";

    try {
      let features;
      if (this.state.multiChannel && this.state.selectedAuthor) {
        // Multi-channel merge mode
        const res = await fetch("/api/extract-multi", {
          method: "POST",
          headers: {"Content-Type": "application/json"},
          body: JSON.stringify({
            author: this.state.selectedAuthor,
            primary_channel: this.state.selectedChannel,
          }),
        });
        features = await res.json();
        if (!res.ok) throw new Error(features.error || "Errore multi-channel");
        this.renderMultiChannelBanner(features.matched_channels || []);
      } else {
        // Single channel mode
        let url = `/api/extract?channel=${this.state.selectedChannel}`;
        if (this.state.selectedAuthor) {
          url += `&author=${encodeURIComponent(this.state.selectedAuthor)}`;
        }
        const res = await fetch(url);
        features = await res.json();
        document.getElementById("multiChannelBanner").classList.add("hidden");
      }

      this.state.features = features;
      this.renderTopics(features.topics || {});
      this.renderFeatures(features);

      document.getElementById("featuresSection").classList.remove("hidden");
      document.getElementById("osintSection").classList.remove("hidden");
      document.getElementById("generatorSection").classList.remove("hidden");
      document.getElementById("outputSection").classList.add("hidden");
      document.getElementById("statsSection").classList.add("hidden");
      document.getElementById("crackSection").classList.add("hidden");

      this.updateLiveCounter();
    } catch (e) {
      toast("Errore durante l'estrazione: " + e.message, "info");
    } finally {
      btn.disabled = false;
      btn.textContent = "Estrai Features";
    }
  },

  renderMultiChannelBanner(matched) {
    const banner = document.getElementById("multiChannelBanner");
    const list = document.getElementById("matchedChannelsList");
    if (matched.length > 0) {
      list.innerHTML = matched.map(ch =>
        `<span class="matched-ch">${ch.name} <small>(${ch.message_count} msg)</small></span>`
      ).join("");
      banner.classList.remove("hidden");
    } else {
      banner.classList.add("hidden");
    }
  },

  renderTopics(topics) {
    const section = document.getElementById("topicsSection");
    const container = document.getElementById("topicsTags");

    const entries = Object.entries(topics || {});
    if (entries.length === 0) {
      section.classList.add("hidden");
      return;
    }

    container.innerHTML = entries
      .map(([topic, count]) =>
        `<div class="topic-badge">${topic}<span class="count">${count}</span></div>`
      ).join("");
    section.classList.remove("hidden");
  },

  renderFeatures(features) {
    const renderTags = (items, containerId, category, isAnimal = false) => {
      const container = document.getElementById(containerId);
      if (!items || items.length === 0) {
        container.innerHTML = "<span style='color: var(--text-dim);'>-</span>";
        return;
      }
      container.innerHTML = items
        .map((item, idx) => `
          <div class="tag${isAnimal ? ' animal' : ''}">
            ${item}
            <button class="tag-remove" data-category="${category}" data-index="${idx}" title="Rimuovi">✕</button>
          </div>
        `)
        .join("");

      container.querySelectorAll(".tag-remove").forEach(btn => {
        btn.addEventListener("click", (e) => {
          e.preventDefault();
          const cat = btn.dataset.category;
          const idx = parseInt(btn.dataset.index);
          if (this.state.features[cat]) {
            this.state.features[cat].splice(idx, 1);
            this.renderFeatures(this.state.features);
            this.updateLiveCounter();
          }
        });
      });
    };

    renderTags(features.names, "namesTags", "names");
    renderTags(features.dates, "datesTags", "dates");
    renderTags(features.animals, "animalsTags", "animals", true);
    renderTags(features.numbers, "numbersTags", "numbers");
    renderTags(features.phones, "phonesTags", "phones");
    renderTags(features.ages_birth_years, "agesTags", "ages_birth_years");
    renderTags(features.keywords, "keywordsTags", "keywords");
    renderTags(features.brands, "brandsTags", "brands");
    renderTags(features.nicknames, "nicknamesTags", "nicknames");
    renderTags(features.phrases, "phrasesTags", "phrases");
    renderTags(features.emojis, "emojiTags", "emojis");
    // ── TIH-enriched features (rendering condizionale, vuote se TIH vecchio) ──
    renderTags(features.ner_persons, "nerPersonsTags", "ner_persons");
    renderTags(features.ner_locations, "nerLocationsTags", "ner_locations");
    renderTags(features.ner_orgs, "nerOrgsTags", "ner_orgs");
    renderTags(features.gps_cities, "gpsCitiesTags", "gps_cities");
    renderTags(features.mentions, "mentionsTags", "mentions");
    renderTags(features.forward_topics, "forwardTopicsTags", "forward_topics");
    renderTags(features.emoji_keywords, "emojiKeywordsTags", "emoji_keywords");

    this.attachAddTagHandlers();
    this.renderFeaturesSummary();
  },

  // ── Riepilogo features pre-generazione (Smart Wizard) ──
  renderFeaturesSummary() {
    const wrap = document.getElementById("featuresSummary");
    if (!wrap || !this.state.features) return;
    const rowsEl = document.getElementById("summaryRows");
    const setEl = document.getElementById("summarySettings");

    // Categorie con label + container ID per scroll-to + flag tih (TIH-enriched)
    const cats = [
      { key: "names",            label: "Nomi",                    target: "namesTags" },
      { key: "dates",            label: "Date / Anni",             target: "datesTags" },
      { key: "animals",          label: "Animali",                 target: "animalsTags" },
      { key: "numbers",          label: "Numeri",                  target: "numbersTags" },
      { key: "phones",           label: "Telefoni",                target: "phonesTags" },
      { key: "ages_birth_years", label: "Anni nascita",            target: "agesTags" },
      { key: "keywords",         label: "Keywords",                target: "keywordsTags" },
      { key: "brands",           label: "Brand",                   target: "brandsTags" },
      { key: "nicknames",        label: "Soprannomi",              target: "nicknamesTags" },
      { key: "phrases",          label: "Frasi",                   target: "phrasesTags" },
      { key: "emojis",           label: "Emoji",                   target: "emojiTags" },
      { key: "ner_persons",      label: "Persone (NER)",           target: "nerPersonsTags",     tih: true },
      { key: "ner_locations",    label: "Luoghi (NER)",            target: "nerLocationsTags",   tih: true },
      { key: "ner_orgs",         label: "Organizzazioni (NER)",    target: "nerOrgsTags",        tih: true },
      { key: "gps_cities",       label: "Citta GPS",               target: "gpsCitiesTags",      tih: true },
      { key: "mentions",         label: "Menzioni",                target: "mentionsTags",       tih: true },
      { key: "forward_topics",   label: "Forward sources",         target: "forwardTopicsTags",  tih: true },
      { key: "emoji_keywords",   label: "Keywords da emoji",       target: "emojiKeywordsTags",  tih: true },
    ];

    let html = "";
    let nonEmpty = 0;
    for (const c of cats) {
      const items = this.state.features[c.key] || [];
      if (!Array.isArray(items) || items.length === 0) continue;
      nonEmpty++;
      const previewItems = items.slice(0, 4).join(" · ");
      const more = items.length > 4 ? ` +${items.length - 4}` : "";
      const tihClass = c.tih ? " tih" : "";
      html += `<div class="summary-row${tihClass}">
        <span class="summary-cat">${c.label}</span>
        <span class="summary-count">${items.length}</span>
        <span class="summary-preview" title="${this._escAttr(items.join(', '))}">${this._escHtml(previewItems)}${more}</span>
        <button class="summary-edit" data-target="${c.target}">✎ modifica</button>
      </div>`;
    }
    if (nonEmpty === 0) {
      html = '<div class="summary-empty">Nessuna feature compilata. Aggiungi tag manualmente o usa Quick OSINT.</div>';
    }
    rowsEl.innerHTML = html;

    // Hook edit buttons → scroll alla feature card
    rowsEl.querySelectorAll(".summary-edit").forEach(btn => {
      btn.addEventListener("click", (e) => {
        e.stopPropagation();
        const tgt = document.getElementById(btn.dataset.target);
        if (tgt) {
          tgt.scrollIntoView({behavior: "smooth", block: "center"});
          tgt.parentElement.style.transition = "box-shadow .3s";
          tgt.parentElement.style.boxShadow = "0 0 0 2px var(--accent)";
          setTimeout(() => { tgt.parentElement.style.boxShadow = ""; }, 1200);
        }
      });
    });

    // Settings line
    const leetSel = document.getElementById("leetLevelSelect");
    const leetVal = leetSel ? leetSel.value : "auto";
    const exCommonEl = document.getElementById("excludeCommonCheck");
    const exCommon = exCommonEl ? exCommonEl.checked : true;
    const exExtraEl = document.getElementById("excludeExtraInput");
    const exExtraCount = exExtraEl
      ? exExtraEl.value.split("\n").map(s => s.trim()).filter(s => s && !s.startsWith("#")).length
      : 0;
    const manualKeysCount = (document.getElementById("manualKeysInput")?.value || "")
      .split(",").map(k => k.trim()).filter(k => k.length > 0).length;
    setEl.innerHTML = `
      <span>🔡 Livello: <strong>${this.state.generatedLevel || "medium"}</strong></span>
      <span>🎲 Leet: <strong>${leetVal}</strong></span>
      <span>🚫 Common: <strong>${exCommon ? "ON" : "OFF"}</strong></span>
      <span>📝 Custom excl: <strong>${exExtraCount}</strong></span>
      <span>🔑 Manual keys: <strong>${manualKeysCount}</strong></span>
    `;
  },

  _escHtml(s) {
    return String(s).replace(/[&<>"']/g, c => ({"&":"&amp;","<":"&lt;",">":"&gt;",'"':"&quot;","'":"&#39;"}[c]));
  },
  _escAttr(s) {
    return String(s).replace(/"/g, "&quot;");
  },

  attachAddTagHandlers() {
    document.querySelectorAll(".add-tag-btn").forEach(btn => {
      // Remove old handler by cloning
      const newBtn = btn.cloneNode(true);
      btn.parentNode.replaceChild(newBtn, btn);
    });

    document.querySelectorAll(".add-tag-btn").forEach(btn => {
      btn.addEventListener("click", () => {
        const category = btn.dataset.category;
        const input = document.querySelector(`.add-tag-input[data-category="${category}"]`);
        const value = input.value.trim();

        if (!value) return;

        if (!this.state.features[category]) {
          this.state.features[category] = [];
        }

        const tokens = value.split(/\s+/).filter(t => t.length > 0);
        tokens.forEach(token => {
          if (!this.state.features[category].includes(token)) {
            this.state.features[category].push(token);
          }
        });

        input.value = "";
        this.renderFeatures(this.state.features);
        this.updateLiveCounter();
      });
    });

    document.querySelectorAll(".add-tag-input").forEach(input => {
      input.addEventListener("keypress", (e) => {
        if (e.key === "Enter") {
          e.preventDefault();
          const btn = document.querySelector(`.add-tag-btn[data-category="${input.dataset.category}"]`);
          btn.click();
        }
      });
    });
  },

  // ── Live Counter (Task #5) ────────────────────────────────────────────
  updateLiveCounter() {
    if (this.state.countDebounceTimer) {
      clearTimeout(this.state.countDebounceTimer);
    }
    this.state.countDebounceTimer = setTimeout(async () => {
      if (!this.state.features) return;

      const counterEl = document.getElementById("liveCounter");
      counterEl.textContent = "...";

      try {
        const manualKeysText = document.getElementById("manualKeysInput").value;
        const manualKeys = manualKeysText.split(",").map(k => k.trim()).filter(k => k.length > 0);
        const leetSel = document.getElementById("leetLevelSelect");
        const leetLevel = leetSel ? leetSel.value : "auto";
        const excludeCommonEl = document.getElementById("excludeCommonCheck");
        const excludeCommon = excludeCommonEl ? excludeCommonEl.checked : true;
        const excludeExtraText = (document.getElementById("excludeExtraInput") || {}).value || "";
        const excludeExtra = excludeExtraText
          .split("\n").map(s => s.trim())
          .filter(s => s.length > 0 && !s.startsWith("#"));

        const res = await fetch("/api/count", {
          method: "POST",
          headers: {"Content-Type": "application/json"},
          body: JSON.stringify({
            features: this.state.features,
            level: this.state.generatedLevel,
            manual_keys: manualKeys,
            leet_level: leetLevel,
            exclude_common: excludeCommon,
            exclude_extra: excludeExtra,
          }),
        });
        const result = await res.json();
        counterEl.textContent = result.count !== undefined ? result.count.toLocaleString() : "?";
      } catch (e) {
        counterEl.textContent = "?";
      }
    }, 300);
  },

  async generate() {
    if (!this.state.selectedChannel || !this.state.features) return;

    const btn = document.getElementById("generateBtn");
    btn.disabled = true;
    btn.textContent = "Generazione in corso…";

    try {
      const manualKeysText = document.getElementById("manualKeysInput").value;
      const manualKeys = manualKeysText.split(",").map(k => k.trim()).filter(k => k.length > 0);

      // ── Mutazioni / Esclusioni avanzate (Smart Wizard) ──
      const leetSel = document.getElementById("leetLevelSelect");
      const leetLevel = leetSel ? leetSel.value : "auto";
      const excludeCommonEl = document.getElementById("excludeCommonCheck");
      const excludeCommon = excludeCommonEl ? excludeCommonEl.checked : true;
      const excludeExtraText = (document.getElementById("excludeExtraInput") || {}).value || "";
      const excludeExtra = excludeExtraText
        .split("\n")
        .map(s => s.trim())
        .filter(s => s.length > 0 && !s.startsWith("#"));

      const payload = {
        channel: this.state.selectedChannel,
        level: this.state.generatedLevel,
        manual_keys: manualKeys,
        features: this.state.features,
        leet_level: leetLevel,
        exclude_common: excludeCommon,
        exclude_extra: excludeExtra,
      };
      if (this.state.selectedChannel === "_standalone" && this.state.standaloneTarget) {
        payload.target_name = this.state.standaloneTarget;
      }

      const res = await fetch("/api/generate", {
        method: "POST",
        headers: {"Content-Type": "application/json"},
        body: JSON.stringify(payload),
      });

      const result = await res.json();
      if (!res.ok) throw new Error(result.error || "Errore");

      document.getElementById("wordlistCount").textContent = result.count;
      document.getElementById("wordlistLevel").textContent = this.state.generatedLevel.toUpperCase();
      document.getElementById("wordlistPreview").textContent = result.preview.join("\n");

      document.getElementById("outputSection").classList.remove("hidden");

      // Load stats
      await this.loadStats();
      // Show crack section now that wordlist exists
      document.getElementById("crackSection").classList.remove("hidden");
    } catch (e) {
      toast("Errore: " + e.message, "error");
    } finally {
      btn.disabled = false;
      btn.textContent = "Genera Wordlist";
    }
  },

  // ── Stats Dashboard (Task #6) ─────────────────────────────────────────
  async loadStats() {
    try {
      const res = await fetch(`/api/stats/${this.state.selectedChannel}`);
      const stats = await res.json();
      if (!res.ok) return;

      document.getElementById("statTotal").textContent = stats.total.toLocaleString();
      document.getElementById("statAvgLength").textContent = stats.avg_length;
      document.getElementById("statLeet").textContent = stats.with_leet_pct + "%";
      document.getElementById("statSpecial").textContent = stats.with_special_pct + "%";
      document.getElementById("statUpper").textContent = stats.with_upper_pct + "%";
      document.getElementById("statDigit").textContent = stats.with_digit_pct + "%";

      // Length bars
      const buckets = stats.length_buckets;
      const max = Math.max(...Object.values(buckets));
      const bars = document.getElementById("lengthBars");
      bars.innerHTML = Object.entries(buckets).map(([range, count]) => {
        const pct = max > 0 ? (count / max) * 100 : 0;
        return `
          <div class="length-bar">
            <div class="length-bar-label">${range}</div>
            <div class="length-bar-fill" style="width: ${pct}%"></div>
            <div class="length-bar-count">${count.toLocaleString()}</div>
          </div>
        `;
      }).join("");

      document.getElementById("statsSection").classList.remove("hidden");
    } catch (e) {
      console.error("Stats error:", e);
    }
  },

  // ── Cracking Simulation (Task #9) ─────────────────────────────────────
  async crack() {
    if (!this.state.selectedChannel) return;

    const hashType = document.getElementById("hashType").value;
    const targetHash = document.getElementById("targetHash").value.trim();

    if (!targetHash) {
      toast("Inserisci un hash da craccare", "warning");
      return;
    }

    const btn = document.getElementById("crackBtn");
    btn.disabled = true;
    btn.textContent = "Cracking in corso…";

    const resultBox = document.getElementById("crackResult");
    resultBox.classList.add("hidden");

    try {
      const res = await fetch("/api/crack", {
        method: "POST",
        headers: {"Content-Type": "application/json"},
        body: JSON.stringify({
          channel: this.state.selectedChannel,
          hash_type: hashType,
          hash: targetHash,
        }),
      });
      const result = await res.json();
      if (!res.ok) throw new Error(result.error || "Errore");

      resultBox.classList.remove("hidden");
      if (result.cracked) {
        resultBox.classList.remove("failure");
        resultBox.classList.add("success");
        resultBox.innerHTML = `
          <strong>✅ HASH CRACCATO!</strong>
          Password trovata: <span class="crack-pwd">${result.password}</span><br>
          Tentativi: ${result.attempts.toLocaleString()} / ${result.total.toLocaleString()}
          (${result.percentage}% della wordlist)
        `;
      } else {
        resultBox.classList.remove("success");
        resultBox.classList.add("failure");
        resultBox.innerHTML = `
          <strong>❌ Hash non trovato</strong>
          Tentativi: ${result.attempts.toLocaleString()} / ${result.total.toLocaleString()}<br>
          La password non è nella wordlist generata. Prova ad espandere il livello (Hard) o aggiungi keyword manuali.
        `;
      }
    } catch (e) {
      toast("Errore: " + e.message, "error");
    } finally {
      btn.disabled = false;
      btn.textContent = "🚀 Tenta crack";
    }
  },

  // ── Save/Load Profile (Task #8) ───────────────────────────────────────
  async saveProfile() {
    if (!this.state.selectedChannel || !this.state.features) return;

    try {
      const res = await fetch("/api/profile/save", {
        method: "POST",
        headers: {"Content-Type": "application/json"},
        body: JSON.stringify({
          channel: this.state.selectedChannel,
          features: this.state.features,
          name: "default",
        }),
      });
      const result = await res.json();
      if (res.ok) {
        toast("Profilo salvato!", "success");
      } else {
        toast("Errore: " + (result.error || "", "error"));
      }
    } catch (e) {
      toast("Errore: " + e.message, "error");
    }
  },

  async loadProfile() {
    if (!this.state.selectedChannel) return;

    try {
      const res = await fetch(`/api/profile/load/${this.state.selectedChannel}`);
      const result = await res.json();
      if (!res.ok) {
        toast("Nessun profilo salvato per questo canale", "warning");
        return;
      }
      this.state.features = result.features;
      this.renderTopics(this.state.features.topics || {});
      this.renderFeatures(this.state.features);
      this.updateLiveCounter();
      toast("✅ Profilo caricato! Saved at: " + result.saved_at, "info");
    } catch (e) {
      toast("Errore: " + e.message, "error");
    }
  },

  // ── Search messages with context (Task #12) ───────────────────────────
  async search() {
    if (!this.state.selectedChannel) {
      toast("Seleziona prima un canale", "warning");
      return;
    }
    const query = document.getElementById("searchInput").value.trim();
    if (!query || query.length < 2) {
      toast("Inserisci almeno 2 caratteri", "warning");
      return;
    }

    const btn = document.getElementById("searchBtn");
    btn.disabled = true;
    btn.textContent = "Ricerca…";

    try {
      const res = await fetch("/api/search", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          channel: this.state.selectedChannel,
          query: query,
          author: this.state.selectedAuthor,
          max_results: 30,
        }),
      });
      const result = await res.json();
      if (!res.ok) throw new Error(result.error || "Errore");

      this.renderSearchResults(query, result);
    } catch (e) {
      toast("Errore: " + e.message, "error");
    } finally {
      btn.disabled = false;
      btn.textContent = "Cerca";
    }
  },

  renderSearchResults(query, result) {
    const container = document.getElementById("searchResults");
    container.classList.remove("hidden");

    let html = `<div class="search-summary">
      <strong>${result.total_matches}</strong> match per "<strong>${this.escapeHtml(query)}</strong>"`;

    if (result.co_occurrences && result.co_occurrences.length > 0) {
      html += `<div class="search-cooccur">
        <strong>Parole correlate:</strong> `;
      html += result.co_occurrences
        .map(c => `<span class="search-cooccur-tag" data-word="${this.escapeHtml(c.word)}">${this.escapeHtml(c.word)}<span class="count">×${c.count}</span></span>`)
        .join("");
      html += `</div>`;
    }
    html += `</div>`;

    if (result.results.length === 0) {
      html += `<div style="color: var(--text-dim); padding: 12px; font-style: italic;">
        Nessun risultato trovato.
      </div>`;
    } else {
      const queryEsc = this.escapeHtml(query);
      const queryRegex = new RegExp(this.escapeRegex(query), "gi");
      for (const r of result.results) {
        const dateStr = r.date ? r.date.slice(0, 10) : "";
        const fullCtx = (r.context_before + r.match + r.context_after);
        const escaped = this.escapeHtml(fullCtx);
        const highlighted = escaped.replace(queryRegex, m => `<mark>${m}</mark>`);
        html += `<div class="search-result-item">
          <div class="search-result-meta">
            <span class="author">${this.escapeHtml(r.author || "?")}</span>
            <span>${dateStr}</span>
          </div>
          <div class="search-result-context">…${highlighted}…</div>
        </div>`;
      }
    }

    container.innerHTML = html;

    // Click on co-occurrence tag → search that word
    container.querySelectorAll(".search-cooccur-tag").forEach(tag => {
      tag.addEventListener("click", () => {
        const word = tag.dataset.word;
        document.getElementById("searchInput").value = word;
        this.search();
      });
    });
  },

  escapeHtml(s) {
    const map = { "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#039;" };
    return String(s).replace(/[&<>"']/g, c => map[c]);
  },

  escapeRegex(s) {
    return String(s).replace(/[.*+?^${}()|[\]\\]/g, "\\$&");
  },

  // ── OSINT Enrichment (Stage 3) ────────────────────────────────────────
  state_osint: { tokens: [], lastResult: null, activeTool: "whois", lastToolTokens: [] },

  // Tool-specific configurations
  tool_configs: {
    "whois":       { placeholder: "es. example.com",         hint: "Dominio (TLD .com .it .org ecc)" },
    "dns":         { placeholder: "es. example.com",         hint: "Dominio per record A/MX/NS/TXT" },
    "ip-geo":      { placeholder: "es. 8.8.8.8 o google.com", hint: "IP o dominio per geolocalizzazione" },
    "wayback":     { placeholder: "es. mario_rossi.it",      hint: "Username/dominio archiviato" },
    "email-rep":   { placeholder: "es. utente@example.com",  hint: "Email per check reputazione/breach" },
    "github-user": { placeholder: "es. torvalds",            hint: "Username GitHub" },
    "reddit-user": { placeholder: "es. spez",                hint: "Username Reddit" },
    "cf":          { placeholder: "es. RSSMRC85A01H501Z",    hint: "Codice fiscale italiano (16 char)" },
  },

  // ── Standalone mode (genera wordlist senza chat) ──
  enterStandaloneMode() {
    const targetName = prompt("Nome del target (per il file di output):", "target");
    if (!targetName) return;

    this.state.selectedChannel = "_standalone";
    this.state.standaloneTarget = targetName;
    // Inizializza features vuote per tutte le categorie
    this.state.features = {
      names: [], dates: [], animals: [], numbers: [], phones: [],
      ages_birth_years: [], keywords: [], brands: [], nicknames: [],
      phrases: [], emojis: [], topics: {},
      ner_persons: [], ner_locations: [], ner_orgs: [],
      gps_cities: [], mentions: [], forward_topics: [], emoji_keywords: [],
    };
    this.state.generatedLevel = "medium";

    // Rivela UI senza chat
    document.getElementById("mainView").classList.add("hidden");
    document.getElementById("contentView").classList.remove("hidden");
    document.getElementById("channelName").textContent = `🆕 Standalone · ${targetName}`;
    document.getElementById("messageCount").textContent = "n/a";
    // Nascondi search/extract
    document.getElementById("extractBtn").classList.add("hidden");
    const userSel = document.getElementById("userSelectorSection");
    if (userSel) userSel.classList.add("hidden");

    // Mostra direttamente features + osint + generator
    document.getElementById("featuresSection").classList.remove("hidden");
    document.getElementById("osintSection").classList.remove("hidden");
    document.getElementById("generatorSection").classList.remove("hidden");

    this.renderFeatures(this.state.features);
    this.updateLiveCounter();
    toast(`Standalone mode attivata per "${targetName}". Compila i campi o usa Quick OSINT.`, "info");

    // Highlight standalone button
    document.querySelectorAll(".channel-item").forEach(el => el.classList.remove("active"));
    document.getElementById("standaloneBtn").classList.add("active");
  },

  // ── Quick OSINT lookups (input mirato → token aggiunti alle feature card) ──
  async quickOsintLookup(kind) {
    const inputs = {
      phone: { id: "quickPhoneInput", endpoint: "/api/osint/phone", body: (v) => ({phone: v}), tokenField: "password_tokens", target: "phones" },
      email: { id: "quickEmailInput", endpoint: "/api/osint/email", body: (v) => ({email: v}), target: "keywords" },
      location: { id: "quickLocationInput", endpoint: "/api/osint/locations", body: (v) => ({text: v}), target: "gps_cities" },
      cf: { id: "quickCfInput", endpoint: "/api/osint/codice-fiscale", body: (v) => ({cf: v}), target: "ages_birth_years" },
      username: { id: "quickUsernameInput", endpoint: "/api/osint/usernames", body: (v) => {
        const parts = v.trim().split(/\s+/);
        return {nome: parts[0] || "", cognome: parts[1] || "", anno: parts[2] || ""};
      }, target: "names" },
    };
    const cfg = inputs[kind];
    if (!cfg) return;
    const inputEl = document.getElementById(cfg.id);
    const value = (inputEl.value || "").trim();
    if (!value) {
      toast("Inserisci un valore prima di fare lookup", "warning");
      return;
    }
    const resBox = document.getElementById("quickOsintResult");
    resBox.classList.add("show");
    resBox.textContent = "⏳ Lookup in corso…";

    try {
      const res = await fetch(cfg.endpoint, {
        method: "POST",
        headers: {"Content-Type": "application/json"},
        body: JSON.stringify(cfg.body(value)),
      });
      const data = await res.json();
      if (!res.ok) throw new Error(data.error || "Errore lookup");

      // Estrazione token unificata
      let tokens = [];
      if (kind === "phone") {
        tokens = data.password_tokens || [];
      } else if (kind === "email") {
        tokens = (data.emails && data.emails[0] && data.emails[0].password_tokens) || data.all_password_tokens || [];
      } else if (kind === "location") {
        const locs = data.locations || [];
        tokens = locs.map(l => l.name || l.city || "").filter(Boolean);
      } else if (kind === "cf") {
        // CF parser ritorna `tokens` (date/anni)
        tokens = data.tokens || [];
      } else if (kind === "username") {
        tokens = data.usernames || data.variants || [];
      }

      // Add to features
      let added = 0;
      if (this.state.features && tokens.length > 0) {
        if (!this.state.features[cfg.target]) {
          this.state.features[cfg.target] = [];
        }
        const existing = new Set(this.state.features[cfg.target].map(s => s.toLowerCase()));
        for (const t of tokens) {
          if (!existing.has(t.toLowerCase())) {
            this.state.features[cfg.target].push(t);
            existing.add(t.toLowerCase());
            added++;
          }
        }
        this.renderFeatures(this.state.features);
        this.updateLiveCounter();
      }

      resBox.textContent = `✓ Lookup ${kind} completato\n\nToken trovati: ${tokens.length}\nAggiunti: ${added}\n\n${tokens.slice(0, 15).join("\n")}${tokens.length > 15 ? "\n…" : ""}`;
      toast(`+${added} token aggiunti a "${cfg.target}"`, "success");
    } catch (e) {
      resBox.textContent = "✗ " + e.message;
      toast("Errore: " + e.message, "error");
    }
  },

  async enrichOsint() {
    if (!this.state.features) {
      toast("Estrai prima le features", "warning");
      return;
    }
    const btn = document.getElementById("enrichOsintBtn");
    btn.disabled = true;
    btn.textContent = "🪄 Arricchimento in corso…";

    try {
      const res = await fetch("/api/osint/enrich-features", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          channel: this.state.selectedChannel,
          features: this.state.features,
        }),
      });
      const result = await res.json();
      if (!res.ok) throw new Error(result.error || "Errore enrich");

      this.state_osint.lastResult = result;
      this.state_osint.tokens = result.added_tokens || [];
      this.renderOsintResults(result);
    } catch (e) {
      toast("Errore: " + e.message, "error");
    } finally {
      btn.disabled = false;
      btn.textContent = "🪄 Arricchisci automaticamente";
    }
  },

  renderOsintResults(result) {
    document.getElementById("osintResults").classList.remove("hidden");

    // Phones
    const phonesEl = document.getElementById("osintPhones");
    if (!result.phones || result.phones.length === 0) {
      phonesEl.innerHTML = '<div class="empty">Nessun telefono rilevato</div>';
    } else {
      phonesEl.innerHTML = result.phones.map(p => {
        const badges = [];
        if (p.country) badges.push(`<span class="badge">${this.escapeHtml(p.country)}</span>`);
        if (p.operator) badges.push(`<span class="badge">${this.escapeHtml(p.operator)}</span>`);
        if (p.area) badges.push(`<span class="badge">${this.escapeHtml(p.area)}</span>`);
        if (p.type && p.type !== "unknown") badges.push(`<span class="badge">${p.type}</span>`);
        return `<div class="osint-phone-item">
          <div class="phone-num">${this.escapeHtml(p.raw)}</div>
          <div class="phone-meta">${badges.join("")} · last4: <code>${this.escapeHtml(p.last4 || "?")}</code></div>
        </div>`;
      }).join("");
    }

    // Locations
    const locsEl = document.getElementById("osintLocations");
    if (!result.locations || result.locations.length === 0) {
      locsEl.innerHTML = '<div class="empty">Nessun luogo riconosciuto</div>';
    } else {
      locsEl.innerHTML = result.locations.slice(0, 15).map(l => {
        const meta = l.province
          ? `${l.province} · ${l.region} · CAP ${l.cap || "?"}`
          : (l.country || "");
        return `<div class="osint-loc-item">
          <span class="loc-name">${this.escapeHtml(l.name)}</span>
          <span class="loc-meta">${this.escapeHtml(meta)}</span>
        </div>`;
      }).join("");
    }

    // Usernames
    const usersEl = document.getElementById("osintUsernames");
    if (!result.usernames || result.usernames.length === 0) {
      usersEl.innerHTML = '<div class="empty">Inserisci nome+cognome+anno per generare</div>';
    } else {
      usersEl.innerHTML = `<div class="osint-usernames-list">${
        result.usernames.slice(0, 40).map(u =>
          `<span class="osint-username" onclick="document.getElementById('socialUsernameInput').value='${this.escapeHtml(u)}'">${this.escapeHtml(u)}</span>`
        ).join("")
      }</div>`;
    }

    // Emails
    const emailsEl = document.getElementById("osintEmails");
    if (!result.emails || result.emails.length === 0) {
      emailsEl.innerHTML = '<div class="empty">Nessuna email rilevata nei messaggi</div>';
    } else {
      emailsEl.innerHTML = result.emails.slice(0, 10).map(e => `
        <div class="osint-email-item">
          <div class="email">${this.escapeHtml(e.email)}</div>
          <div class="email-meta">
            ${this.escapeHtml(e.provider || "?")} · pattern: ${this.escapeHtml(e.pattern || "?")}
          </div>
        </div>
      `).join("");
    }

    // Summary
    const summaryEl = document.getElementById("osintSummary");
    summaryEl.innerHTML = `
      <strong>${(result.added_tokens || []).length}</strong>
      tokens estratti dall'OSINT enrichment, pronti per essere aggiunti alla wordlist.
    `;

    // Show "Add to wordlist" button if tokens exist
    const addBtn = document.getElementById("addOsintTokensBtn");
    if ((result.added_tokens || []).length > 0) {
      addBtn.classList.remove("hidden");
    } else {
      addBtn.classList.add("hidden");
    }
  },

  addOsintTokens() {
    const tokens = this.state_osint.tokens || [];
    if (tokens.length === 0) {
      toast("Nessun token da aggiungere", "warning");
      return;
    }
    if (!this.state.features.keywords) this.state.features.keywords = [];

    let added = 0;
    for (const t of tokens) {
      // Distribute by length/type
      const target = (t.length === 4 && /^\d+$/.test(t)) || (t.length === 6 && /^\d+$/.test(t))
        ? "numbers"
        : "keywords";
      if (!this.state.features[target]) this.state.features[target] = [];
      if (!this.state.features[target].includes(t)) {
        this.state.features[target].push(t);
        added++;
      }
    }

    this.renderFeatures(this.state.features);
    this.updateLiveCounter();
    toast(`✅ ${added} tokens aggiunti alla wordlist (${tokens.length - added} duplicati skippati, "info")`);
  },

  async socialCheck() {
    const username = document.getElementById("socialUsernameInput").value.trim();
    if (!username || username.length < 3) {
      toast("Inserisci uno username (min 3 caratteri)", "warning");
      return;
    }

    const btn = document.getElementById("socialCheckBtn");
    btn.disabled = true;
    btn.textContent = "🔍 Check in corso… (può richiedere 30s)";

    try {
      const res = await fetch("/api/osint/social-check", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ username, timeout: 8 }),
      });
      const result = await res.json();
      if (!res.ok) throw new Error(result.error || "Errore");

      this.renderSocialResults(result);
    } catch (e) {
      toast("Errore: " + e.message, "error");
    } finally {
      btn.disabled = false;
      btn.textContent = "🚀 Check";
    }
  },

  // ── Online Tools (Stage 3.5) ───────────────────────────────────────
  updateToolUI() {
    const cfg = this.tool_configs[this.state_osint.activeTool] || {};
    document.getElementById("toolInput").placeholder = cfg.placeholder || "";
    document.getElementById("toolHint").innerHTML = cfg.hint || "";
    document.getElementById("toolInput").value = "";
    document.getElementById("toolResult").classList.add("hidden");
  },

  async runTool() {
    const tool = this.state_osint.activeTool;
    const value = document.getElementById("toolInput").value.trim();
    if (!value) {
      toast("Inserisci un valore", "warning");
      return;
    }

    const btn = document.getElementById("toolRunBtn");
    btn.disabled = true;
    btn.textContent = "⏳ Esecuzione...";

    const resultEl = document.getElementById("toolResult");
    resultEl.classList.remove("hidden", "error");
    resultEl.innerHTML = '<div style="color: var(--text-dim);">Caricamento...</div>';

    try {
      const payloadKey = {
        "whois": "domain", "dns": "domain", "ip-geo": "ip",
        "wayback": "query", "email-rep": "email",
        "github-user": "username", "reddit-user": "username",
        "cf": "cf",
      }[tool];

      const res = await fetch(`/api/osint/${tool}`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ [payloadKey]: value }),
      });
      const data = await res.json();

      if (data.error) {
        resultEl.classList.add("error");
        resultEl.innerHTML = `<strong>❌ Errore:</strong> ${this.escapeHtml(data.error)}`;
        return;
      }

      this.renderToolResult(tool, data);
    } catch (e) {
      resultEl.classList.add("error");
      resultEl.innerHTML = `<strong>❌ Network error:</strong> ${this.escapeHtml(e.message)}`;
    } finally {
      btn.disabled = false;
      btn.textContent = "▶ Esegui";
    }
  },

  renderToolResult(tool, data) {
    const resultEl = document.getElementById("toolResult");
    let html = "";
    let tokens = [];

    if (tool === "whois") {
      html += `<h4>WHOIS · ${this.escapeHtml(data.domain)}</h4>`;
      const fields = ["registrar", "creation_date", "expiration_date", "updated_date", "registrant_country"];
      fields.forEach(f => {
        if (data[f]) {
          html += this.kvRow(f, data[f]);
        }
      });
      if (data.name_servers) {
        html += this.kvRow("name_servers", data.name_servers.join(", "));
      }
      tokens = data.tokens || [];
    }

    else if (tool === "dns") {
      html += `<h4>DNS · ${this.escapeHtml(data.domain)}</h4>`;
      Object.entries(data.records || {}).forEach(([rtype, recs]) => {
        html += this.kvRow(rtype, recs.join(", "));
      });
      if (Object.keys(data.records || {}).length === 0) {
        html += `<div style="color: var(--text-dim);">Nessun record trovato</div>`;
      }
    }

    else if (tool === "ip-geo") {
      html += `<h4>IP Geolocation · ${this.escapeHtml(data.ip)}</h4>`;
      ["city", "region", "country", "country_code", "postal", "timezone", "org"].forEach(f => {
        if (data[f]) html += this.kvRow(f, data[f]);
      });
      if (data.lat && data.lon) {
        html += this.kvRow("coords",
          `${data.lat}, ${data.lon} <a href="https://www.openstreetmap.org/?mlat=${data.lat}&mlon=${data.lon}&zoom=12" target="_blank" style="color:var(--accent)">map ↗</a>`);
      }
      tokens = data.tokens || [];
    }

    else if (tool === "wayback") {
      html += `<h4>Wayback Machine · "${this.escapeHtml(data.query)}"</h4>`;
      html += `<div class="tool-kv"><div class="key">Total snapshots</div><div class="val">${data.total || 0}</div></div>`;
      const snaps = data.snapshots || [];
      if (snaps.length === 0) {
        html += `<div style="color: var(--text-dim); margin-top: 8px;">Nessuna pagina archiviata</div>`;
      } else {
        html += `<div style="margin-top: 8px;">`;
        snaps.slice(0, 15).forEach(s => {
          const ts = s.timestamp || "";
          const date = ts.length >= 8 ? `${ts.slice(0,4)}-${ts.slice(4,6)}-${ts.slice(6,8)}` : ts;
          html += `<div class="wayback-snap">
            <span class="ts">${date}</span>
            <a href="${this.escapeHtml(s.archive_url)}" target="_blank">${this.escapeHtml(s.url)}</a>
          </div>`;
        });
        html += `</div>`;
      }
    }

    else if (tool === "email-rep") {
      html += `<h4>Email Reputation · ${this.escapeHtml(data.email)}</h4>`;
      html += this.kvRow("reputation", `<span style="color:${data.reputation === 'high' ? 'var(--green)' : (data.reputation === 'low' ? 'var(--red)' : 'var(--accent)')}">${data.reputation || "?"}</span>`);
      html += this.kvRow("suspicious", data.suspicious ? "⚠️ Yes" : "✅ No");
      html += this.kvRow("references", data.references);
      const det = data.details || {};
      html += `<div style="margin-top: 8px;"><strong>Details:</strong></div>`;
      html += this.kvRow("blacklisted", det.blacklisted ? "⚠️ Yes" : "No");
      html += this.kvRow("malicious", det.malicious_activity ? "⚠️ Yes" : "No");
      html += this.kvRow("creds_leaked", det.credentials_leaked ? "🔓 Yes" : "No");
      html += this.kvRow("data_breach", det.data_breach ? "🔓 Yes" : "No");
      html += this.kvRow("first_seen", det.first_seen || "?");
      html += this.kvRow("last_seen", det.last_seen || "?");
      if (det.profiles && det.profiles.length > 0) {
        html += this.kvRow("profiles", det.profiles.join(", "));
      }
    }

    else if (tool === "github-user") {
      if (!data.exists) {
        html += `<div>👤 User <strong>${this.escapeHtml(data.username || "?")}</strong> non trovato su GitHub</div>`;
      } else {
        html += `<h4>GitHub · @${this.escapeHtml(data.username)}</h4>`;
        ["name", "bio", "company", "location", "blog", "email", "twitter",
         "public_repos", "followers", "created_at"].forEach(f => {
          if (data[f]) html += this.kvRow(f, data[f]);
        });
        if (data.html_url) {
          html += this.kvRow("profile", `<a href="${this.escapeHtml(data.html_url)}" target="_blank" style="color:var(--accent)">${this.escapeHtml(data.html_url)} ↗</a>`);
        }
      }
      tokens = data.tokens || [];
    }

    else if (tool === "reddit-user") {
      if (!data.exists) {
        html += `<div>👤 User <strong>${this.escapeHtml(data.username || "?")}</strong> non trovato su Reddit</div>`;
      } else {
        html += `<h4>Reddit · u/${this.escapeHtml(data.username)}</h4>`;
        html += this.kvRow("created_year", data.created_year || "?");
        html += this.kvRow("comment_karma", data.comment_karma);
        html += this.kvRow("link_karma", data.link_karma);
        html += this.kvRow("verified", data.verified ? "✅" : "❌");
        if (data.html_url) {
          html += this.kvRow("profile", `<a href="${this.escapeHtml(data.html_url)}" target="_blank" style="color:var(--accent)">${this.escapeHtml(data.html_url)} ↗</a>`);
        }
      }
      tokens = data.tokens || [];
    }

    else if (tool === "cf") {
      if (!data.valid) {
        html += `<div>❌ Codice fiscale non valido</div>`;
      } else {
        html += `<h4>Codice Fiscale · ${this.escapeHtml(data.cf)}</h4>`;
        html += this.kvRow("data_nascita", data.data_nascita);
        html += this.kvRow("anno", data.anno_nascita);
        html += this.kvRow("mese", `${data.mese} (${data.mese_nome})`);
        html += this.kvRow("giorno", data.giorno);
        html += this.kvRow("sesso", data.sesso);
        html += this.kvRow("codice_comune", data.codice_comune);
      }
      tokens = data.tokens || [];
    }

    // Tokens banner if any
    if (tokens && tokens.length > 0) {
      this.state_osint.lastToolTokens = tokens;
      html += `<div class="tool-tokens-banner">
        <span>📦 <strong>${tokens.length}</strong> tokens estratti: ${
          tokens.slice(0, 8).map(t => `<span class="tool-list-item">${this.escapeHtml(t)}</span>`).join(" ")
        }${tokens.length > 8 ? " ..." : ""}</span>
        <button onclick="app.addToolTokensToWordlist()">+ Aggiungi al wordlist</button>
      </div>`;
    }

    resultEl.innerHTML = html;
  },

  kvRow(key, value) {
    const valStr = value === null || value === undefined || value === "" ? "(vuoto)" : value;
    const cls = (value === null || value === undefined || value === "") ? "empty" : "";
    return `<div class="tool-kv"><div class="key">${this.escapeHtml(key)}</div><div class="val ${cls}">${valStr}</div></div>`;
  },

  addToolTokensToWordlist() {
    const tokens = this.state_osint.lastToolTokens || [];
    if (tokens.length === 0 || !this.state.features) {
      toast("Nessun token o features non estratte", "warning");
      return;
    }
    if (!this.state.features.keywords) this.state.features.keywords = [];

    let added = 0;
    for (const t of tokens) {
      const target = /^\d+$/.test(t) && t.length <= 8 ? "numbers" : "keywords";
      if (!this.state.features[target]) this.state.features[target] = [];
      if (!this.state.features[target].includes(t)) {
        this.state.features[target].push(t);
        added++;
      }
    }
    this.renderFeatures(this.state.features);
    this.updateLiveCounter();
    toast(`✅ ${added} tokens aggiunti (${tokens.length - added} duplicati, "info")`);
  },

  renderSocialResults(result) {
    const container = document.getElementById("socialResults");
    container.classList.remove("hidden");

    let html = `<div class="social-summary">
      Username <strong>${this.escapeHtml(result.username)}</strong> trovato su
      <span class="found-count">${result.found_count}</span>
      di ${result.total_checked} siti controllati.
    </div>`;

    html += `<div class="social-results-grid">`;
    for (const r of result.results) {
      const cls = r.found === true ? "found" : (r.found === false ? "notfound" : "unknown");
      const icon = r.found === true ? "✅" : (r.found === false ? "❌" : "❓");
      const status = r.error ? `(${this.escapeHtml(r.error)})` : (r.status || "?");
      html += `<a class="social-result-item ${cls}" href="${this.escapeHtml(r.url)}"
                  target="_blank" rel="noopener">
        <span class="icon">${icon}</span>
        <span class="name">${this.escapeHtml(r.site)}</span>
        <span class="cat">${this.escapeHtml(r.category || "")}</span>
      </a>`;
    }
    html += `</div>`;

    container.innerHTML = html;
  },
};

document.addEventListener("DOMContentLoaded", () => app.init());
