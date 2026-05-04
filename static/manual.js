// HORCRUX · Manual Wizard

const wizard = {
  current: 0,
  totalSteps: 0,
  data: {},
  level: "medium",
  generatedTarget: null,
  osintTokens: [],         // Token raw raccolti via OSINT
  osintPrefills: {},       // Map field → value derivati da OSINT
  osintLastResults: null,

  init() {
    const steps = document.querySelectorAll(".wizard-step");
    this.totalSteps = steps.length;
    document.getElementById("progressTotal").textContent = this.totalSteps;

    this.attachListeners();
    this.updateUI();
    // Focus first input
    const firstInput = steps[0].querySelector(".step-input");
    if (firstInput) firstInput.focus();
  },

  attachListeners() {
    document.getElementById("nextBtn").addEventListener("click", () => this.next());
    document.getElementById("backBtn").addEventListener("click", () => this.back());
    document.getElementById("skipBtn").addEventListener("click", () => this.skip());
    document.getElementById("downloadManualBtn").addEventListener("click", () => this.download());
    document.getElementById("restartBtn").addEventListener("click", () => this.restart());
    document.getElementById("openOsintBtn").addEventListener("click", () => this.openOsintModal());

    // Close modal on backdrop click
    document.getElementById("osintModal").addEventListener("click", (e) => {
      if (e.target.id === "osintModal") this.closeOsintModal();
    });

    document.querySelectorAll('input[name="manualLevel"]').forEach(radio => {
      radio.addEventListener("change", e => {
        this.level = e.target.value;
      });
    });

    // Enter to advance (single-input fields only)
    document.addEventListener("keydown", e => {
      if (e.key === "Enter" && !e.shiftKey) {
        const active = document.querySelector(".wizard-step.active");
        if (!active) return;
        const input = active.querySelector(".step-input");
        if (input && input.tagName === "INPUT") {
          e.preventDefault();
          this.next();
        }
      }
    });
  },

  saveCurrent() {
    const active = document.querySelector(".wizard-step.active");
    if (!active) return;
    const input = active.querySelector(".step-input");
    if (input) {
      const field = input.dataset.field;
      const val = input.value.trim();
      if (val) this.data[field] = val;
      else delete this.data[field];
    }
  },

  showStep(idx) {
    document.querySelectorAll(".wizard-step").forEach(s => s.classList.remove("active"));
    document.querySelector(`.wizard-step[data-step="${idx}"]`).classList.add("active");

    // Restore value if user goes back
    const active = document.querySelector(".wizard-step.active");
    const input = active?.querySelector(".step-input");
    if (input) {
      const field = input.dataset.field;
      input.value = this.data[field] || "";
      setTimeout(() => input.focus(), 200);
    }

    this.updateUI();

    // If reached last step, build summary
    if (idx === this.totalSteps - 1) {
      this.buildSummary();
    }
  },

  updateUI() {
    const idx = this.current;
    document.getElementById("progressCurrent").textContent = idx + 1;
    document.getElementById("progressFill").style.width = `${((idx + 1) / this.totalSteps) * 100}%`;

    const activeStep = document.querySelector(`.wizard-step[data-step="${idx}"]`);
    const label = activeStep?.dataset.label || "";
    document.getElementById("progressLabel").textContent = label;

    document.getElementById("backBtn").disabled = (idx === 0);

    const isLast = (idx === this.totalSteps - 1);
    const nextBtn = document.getElementById("nextBtn");
    nextBtn.textContent = isLast ? "⚡ Genera Wordlist" : "Avanti →";
    document.getElementById("skipBtn").style.display = isLast ? "none" : "";
  },

  next() {
    this.saveCurrent();

    if (this.current === this.totalSteps - 1) {
      // Last step → generate
      this.generate();
      return;
    }

    this.current++;
    this.showStep(this.current);
  },

  skip() {
    // Don't save current value
    const active = document.querySelector(".wizard-step.active");
    const input = active?.querySelector(".step-input");
    if (input) {
      const field = input.dataset.field;
      delete this.data[field];
    }

    if (this.current < this.totalSteps - 1) {
      this.current++;
      this.showStep(this.current);
    }
  },

  back() {
    this.saveCurrent();
    if (this.current > 0) {
      this.current--;
      this.showStep(this.current);
    }
  },

  buildSummary() {
    const summary = document.getElementById("summaryBox");
    const labels = {
      target_name: "🎯 Target",
      nome: "👤 Nome",
      cognome: "📛 Cognome",
      soprannomi: "💕 Soprannomi",
      anno_nascita: "🎂 Anno nascita",
      date_importanti: "📅 Date importanti",
      numeri: "🔢 Numeri",
      telefono: "📞 Telefono",
      famiglia: "👨‍👩‍👧 Famiglia",
      partner: "💞 Partner",
      animali: "🐾 Animali",
      hobby: "🎨 Hobby",
      squadra: "⚽ Squadra",
      brands: "🏷️ Brand",
      luoghi: "📍 Luoghi",
      parole_speciali: "✨ Speciali",
    };

    let html = "";
    for (const [field, label] of Object.entries(labels)) {
      const val = this.data[field];
      const cls = val ? "" : " empty";
      const display = val || "(non impostato)";
      html += `<div class="summary-row">
        <div class="summary-key">${label}</div>
        <div class="summary-val${cls}">${this.escape(display)}</div>
      </div>`;
    }

    const filledCount = Object.keys(this.data).filter(k => this.data[k]).length;
    summary.innerHTML = `<div style="margin-bottom: 12px; color: var(--accent); font-weight: bold;">
      ${filledCount} / ${Object.keys(labels).length} campi compilati
    </div>` + html;
  },

  escape(s) {
    return String(s).replace(/[&<>"']/g, c => ({
      "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#039;"
    }[c]));
  },

  async generate() {
    this.saveCurrent();

    if (Object.keys(this.data).length === 0) {
      toast("Inserisci almeno un campo prima di generare!", "warning");
      return;
    }

    const targetName = this.data.target_name || "wordlist_manuale";
    const fields = { ...this.data };
    delete fields.target_name;

    const nextBtn = document.getElementById("nextBtn");
    nextBtn.disabled = true;
    nextBtn.textContent = "⏳ Generazione...";

    try {
      const res = await fetch("/api/manual-generate", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          level: this.level,
          target_name: targetName,
          fields: fields,
          osint_tokens: this.osintTokens || [],
        }),
      });

      const result = await res.json();
      if (!res.ok) throw new Error(result.error || "Errore generazione");

      this.generatedTarget = result.target;
      this.showResult(result);
    } catch (e) {
      toast("Errore: " + e.message, "error");
      nextBtn.disabled = false;
      nextBtn.textContent = "⚡ Genera Wordlist";
    }
  },

  showResult(result) {
    document.querySelectorAll(".wizard-step").forEach(s => s.classList.remove("active"));
    document.getElementById("wizardNav").style.display = "none";

    const resultSection = document.getElementById("resultSection");
    document.getElementById("resultCount").textContent = result.count.toLocaleString();
    document.getElementById("resultLevel").textContent = this.level.toUpperCase();
    document.getElementById("resultPreview").textContent = (result.preview || []).join("\n");
    resultSection.classList.add("active");

    document.getElementById("progressFill").style.width = "100%";
    document.getElementById("progressLabel").textContent = "Completato ✓";
  },

  download() {
    if (!this.generatedTarget) return;
    window.location.href = `/api/manual-download/${this.generatedTarget}`;
  },

  restart() {
    this.current = 0;
    this.data = {};
    this.generatedTarget = null;
    this.osintTokens = [];
    this.osintPrefills = {};
    this.osintLastResults = null;

    document.querySelectorAll(".wizard-step .step-input").forEach(i => i.value = "");
    document.getElementById("resultSection").classList.remove("active");
    document.getElementById("wizardNav").style.display = "";
    document.getElementById("osintBanner").classList.add("hidden");

    const nextBtn = document.getElementById("nextBtn");
    nextBtn.disabled = false;

    this.showStep(0);
  },

  // ── OSINT Auto-fill ──────────────────────────────────────────────────
  openOsintModal() {
    document.getElementById("osintModal").classList.remove("hidden");
  },

  closeOsintModal() {
    document.getElementById("osintModal").classList.add("hidden");
  },

  resetOsintResults() {
    document.getElementById("osintResultsPanel").classList.add("hidden");
    document.getElementById("osintResultsList").innerHTML = "";
    document.getElementById("osintResultsSummary").innerHTML = "";
    document.getElementById("osintPrefillList").innerHTML = "";
    this.osintLastResults = null;
  },

  async runOsintLookup() {
    const cf = document.getElementById("osintCfInput").value.trim();
    const github = document.getElementById("osintGithubInput").value.trim();
    const reddit = document.getElementById("osintRedditInput").value.trim();
    const email = document.getElementById("osintEmailInput").value.trim();
    const phone = document.getElementById("osintPhoneInput").value.trim();
    const domain = document.getElementById("osintDomainInput").value.trim();

    if (!cf && !github && !reddit && !email && !phone && !domain) {
      toast("Inserisci almeno un campo", "warning");
      return;
    }

    const btn = document.getElementById("osintRunBtn");
    btn.disabled = true;
    btn.textContent = "⏳ Lookup in corso...";

    const results = [];
    const prefills = {};
    const tokens = [];

    const addResult = (src, success, label, extra) => {
      results.push({ src, success, label, extra });
    };

    // Lancia tutte le API in parallelo
    const promises = [];

    if (cf) {
      promises.push(this.callApi("/api/osint/codice-fiscale", { cf }).then(r => {
        if (r && r.valid) {
          addResult("Codice Fiscale", true, `${r.data_nascita} · sesso ${r.sesso} · comune ${r.codice_comune}`);
          if (r.anno_nascita) prefills.anno_nascita = String(r.anno_nascita);
          // Date importanti: aggiungi data nascita
          const existing = prefills.date_importanti ? prefills.date_importanti + ", " : "";
          prefills.date_importanti = existing + r.data_nascita;
          (r.tokens || []).forEach(t => tokens.push(t));
        } else if (r && r.error) {
          addResult("Codice Fiscale", false, r.error);
        }
      }));
    }

    if (github) {
      promises.push(this.callApi("/api/osint/github-user", { username: github }).then(r => {
        if (r && r.exists) {
          const parts = [];
          if (r.name) parts.push(r.name);
          if (r.location) parts.push(`📍 ${r.location}`);
          if (r.company) parts.push(`🏢 ${r.company}`);
          if (r.created_at) parts.push(`@${r.created_at.slice(0,4)}`);
          addResult("GitHub", true, `@${r.username} · ${parts.join(" · ")}`);

          // Prefill: nome+cognome from name
          if (r.name) {
            const nameParts = r.name.split(/\s+/);
            if (nameParts.length >= 1 && !prefills.nome) prefills.nome = nameParts[0];
            if (nameParts.length >= 2 && !prefills.cognome) prefills.cognome = nameParts.slice(1).join(" ");
          }
          if (r.location) {
            const existing = prefills.luoghi ? prefills.luoghi + ", " : "";
            prefills.luoghi = existing + r.location.split(",")[0].trim();
          }
          if (r.company) {
            const existing = prefills.brands ? prefills.brands + ", " : "";
            prefills.brands = existing + r.company.replace(/[@]/g, "");
          }
          (r.tokens || []).forEach(t => tokens.push(t));
        } else if (r && r.exists === false) {
          addResult("GitHub", false, `@${github} non trovato`);
        } else if (r && r.error) {
          addResult("GitHub", false, r.error);
        }
      }));
    }

    if (reddit) {
      promises.push(this.callApi("/api/osint/reddit-user", { username: reddit }).then(r => {
        if (r && r.exists) {
          addResult("Reddit", true, `u/${r.username} · iscritto ${r.created_year || "?"} · karma ${r.comment_karma}/${r.link_karma}`);
          (r.tokens || []).forEach(t => tokens.push(t));
        } else if (r && r.exists === false) {
          addResult("Reddit", false, `u/${reddit} non trovato`);
        }
      }));
    }

    if (email) {
      promises.push(this.callApi("/api/osint/email", { email }).then(r => {
        if (r && r.emails && r.emails.length > 0) {
          const e = r.emails[0];
          addResult("Email", true, `${e.email} · ${e.provider} · pattern: ${e.pattern}`);

          // Prefill da pattern detection
          if (e.parts && e.parts.length >= 1 && e.parts[0].length >= 3) {
            if (!prefills.nome && e.pattern === "nome.cognome") {
              prefills.nome = e.parts[0];
              if (e.parts[1]) prefills.cognome = e.parts[1];
            } else if (!prefills.nome && (e.pattern === "nome+anno" || e.pattern === "nome.anno")) {
              prefills.nome = e.parts[0];
            }
          }
          if (e.year && !prefills.anno_nascita) prefills.anno_nascita = e.year;

          (e.tokens_for_password || []).forEach(t => tokens.push(t));
        } else if (r && r.error) {
          addResult("Email", false, r.error);
        }
      }));
    }

    if (phone) {
      promises.push(this.callApi("/api/osint/phone", { phone }).then(r => {
        if (r && !r.error) {
          const parts = [r.country || "?"];
          if (r.operator) parts.push(`📡 ${r.operator}`);
          if (r.area) parts.push(`📍 ${r.area}`);
          addResult("Telefono", true, `${r.raw} · ${parts.join(" · ")}`);

          if (!prefills.telefono) prefills.telefono = r.clean;
          (r.password_tokens || []).forEach(t => tokens.push(t));
        }
      }));
    }

    if (domain) {
      // Try IP geo first (works for both IP and domain)
      promises.push(this.callApi("/api/osint/ip-geo", { ip: domain }).then(r => {
        if (r && r.country) {
          const parts = [r.city, r.country].filter(Boolean);
          addResult("IP/Domain Geo", true, `${domain} → ${parts.join(", ")}${r.org ? " · " + r.org : ""}`);
          if (r.city) {
            const existing = prefills.luoghi ? prefills.luoghi + ", " : "";
            prefills.luoghi = existing + r.city;
          }
          (r.tokens || []).forEach(t => tokens.push(t));
        } else if (r && r.error) {
          addResult("IP/Domain Geo", false, r.error);
        }
      }));

      // WHOIS in parallel se è un dominio
      if (/^[a-z0-9.\-]+\.[a-z]{2,}$/i.test(domain)) {
        promises.push(this.callApi("/api/osint/whois", { domain }).then(r => {
          if (r && r.registrar) {
            addResult("WHOIS", true, `${r.domain} · ${r.registrar} · creato ${r.creation_date || "?"}`);
            (r.tokens || []).forEach(t => tokens.push(t));
          }
        }));
      }
    }

    // Wait all
    await Promise.all(promises);

    btn.disabled = false;
    btn.textContent = "🪄 Esegui Lookup";

    // Dedupe tokens
    const uniqueTokens = [...new Set(tokens.filter(t => t && String(t).length >= 2))];

    this.osintLastResults = { results, prefills, tokens: uniqueTokens };
    this.renderOsintResults();
  },

  callApi(url, payload) {
    return fetch(url, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(payload),
    }).then(r => r.json()).catch(() => null);
  },

  renderOsintResults() {
    const { results, prefills, tokens } = this.osintLastResults || {};
    const panel = document.getElementById("osintResultsPanel");
    const list = document.getElementById("osintResultsList");
    const summary = document.getElementById("osintResultsSummary");
    const prefillEl = document.getElementById("osintPrefillList");

    // Render results
    list.innerHTML = (results || []).map(r => `
      <div class="osint-result-row ${r.success ? "success" : "error"}">
        <span class="${r.success ? '✅' : '❌'}">${r.success ? "✅" : "❌"}</span>
        <span class="src">${this.escape(r.src)}</span>
        <span>${this.escape(r.label)}</span>
      </div>
    `).join("");

    // Summary
    summary.innerHTML = `
      <strong>${(tokens || []).length}</strong> token estratti per la wordlist ·
      <strong>${Object.keys(prefills || {}).length}</strong> campi auto-compilabili
    `;

    // Prefill list
    const labelMap = {
      nome: "👤 Nome", cognome: "📛 Cognome",
      anno_nascita: "🎂 Anno nascita", date_importanti: "📅 Date",
      luoghi: "📍 Luoghi", brands: "🏷️ Brand",
      telefono: "📞 Telefono", numeri: "🔢 Numeri",
    };

    if (Object.keys(prefills || {}).length === 0) {
      prefillEl.innerHTML = '<div class="prefill-row"><span class="prefill-key" style="color:var(--text-darker);font-style:italic">Nessun campo auto-compilabile</span></div>';
    } else {
      prefillEl.innerHTML = Object.entries(prefills).map(([k, v]) =>
        `<div class="prefill-row">
          <span class="prefill-key">${labelMap[k] || k}</span>
          <span class="prefill-val">${this.escape(v)}</span>
        </div>`
      ).join("");
    }

    panel.classList.remove("hidden");
  },

  applyOsintToWizard() {
    if (!this.osintLastResults) return;

    const { prefills, tokens } = this.osintLastResults;

    // Apply prefills (don't overwrite existing wizard data)
    Object.entries(prefills || {}).forEach(([key, val]) => {
      if (!this.data[key]) {
        this.data[key] = val;
      } else {
        // Merge as comma-separated for multi-value fields
        const multi = ["soprannomi", "date_importanti", "famiglia", "animali",
                       "hobby", "squadra", "brands", "luoghi", "parole_speciali", "numeri"];
        if (multi.includes(key)) {
          const existing = this.data[key];
          if (!existing.includes(val)) {
            this.data[key] = existing + ", " + val;
          }
        }
      }
    });

    // Append OSINT tokens (separate channel: vanno aggiunti come manual_keys lato server)
    this.osintTokens = [...new Set([...(this.osintTokens || []), ...(tokens || [])])];

    // Update banner
    const banner = document.getElementById("osintBanner");
    document.getElementById("osintTokenCount").textContent = this.osintTokens.length;
    banner.classList.remove("hidden");

    // Re-show current step to refresh input value if needed
    this.showStep(this.current);

    // Close modal
    this.closeOsintModal();

    toast(`✅ Applicati ${Object.keys(prefills || {}, "info").length} campi · ${tokens.length} token aggiunti alla wordlist`);
  },
};

document.addEventListener("DOMContentLoaded", () => wizard.init());
