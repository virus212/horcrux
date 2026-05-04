// HORCRUX · Ritual background runes
// Spawn dinamico di simboli rituali che fluttuano sullo schermo.
// Lifetime per rune: 18-25s. Spawn rate: ~0.7 rune/sec.

(() => {
  const SYMBOLS = [
    "✦", "◇", "⬥", "⊹", "✶", "◬", "⊕", "❖", "☥", "✧", "⛤", "⚝",
    "★", "☽", "⚸", "♆", "✺", "⟁", "◈", "⌘", "✷", "❉", "𓂀", "𓁹",
    "☉", "♅", "✵", "⌬", "⛧", "⛥", "⛦", "⛬",
  ];

  const PATHS = [
    "drift-up",       // sale dritto
    "drift-diagonal", // diagonale
    "drift-spiral",   // spirale lenta
    "drift-side",     // ondulato laterale
  ];

  let bg = null;
  let spawning = true;

  function init() {
    bg = document.createElement("div");
    bg.id = "ritualBg";
    bg.className = "ritual-bg-overlay";
    bg.setAttribute("aria-hidden", "true");
    document.body.appendChild(bg);

    // Add big sigil ring on body
    const sigil = document.createElement("div");
    sigil.className = "ritual-sigil-ring";
    sigil.innerHTML = `
      <div class="sigil-circle outer"></div>
      <div class="sigil-circle middle"></div>
      <div class="sigil-circle inner"></div>
      <div class="sigil-glyphs">
        <span style="--i:0">✦</span>
        <span style="--i:1">◇</span>
        <span style="--i:2">⬥</span>
        <span style="--i:3">⊹</span>
        <span style="--i:4">✶</span>
        <span style="--i:5">◬</span>
        <span style="--i:6">⊕</span>
        <span style="--i:7">❖</span>
      </div>
    `;
    document.body.appendChild(sigil);

    // Respect reduced motion
    if (window.matchMedia("(prefers-reduced-motion: reduce)").matches) {
      spawning = false;
      return;
    }

    // Initial burst
    for (let i = 0; i < 6; i++) {
      setTimeout(spawnRune, i * 250);
    }

    // Continuous spawn
    setInterval(() => {
      if (spawning && document.visibilityState === "visible") {
        spawnRune();
      }
    }, 1400);

    // Pause on tab hidden (save resources)
    document.addEventListener("visibilitychange", () => {
      spawning = document.visibilityState === "visible";
    });
  }

  function spawnRune() {
    if (!bg) return;
    const rune = document.createElement("span");
    rune.className = "ritual-rune";

    const sym = SYMBOLS[Math.floor(Math.random() * SYMBOLS.length)];
    const pathClass = PATHS[Math.floor(Math.random() * PATHS.length)];
    rune.classList.add(pathClass);

    rune.textContent = sym;

    // Random spawn position (mostly bottom half, some sides)
    const xPercent = Math.random() * 100;
    const yPercent = 60 + Math.random() * 50;  // start lower-half
    rune.style.left = xPercent + "vw";
    rune.style.top = yPercent + "vh";

    // Random size + duration
    const size = 14 + Math.random() * 30;
    rune.style.fontSize = size + "px";

    const duration = 18 + Math.random() * 8;
    rune.style.animationDuration = duration + "s";

    // Slight color variation
    const hue = Math.random() < 0.15 ? 250 : 0;  // mostly grey, occasionally faint blue
    const opacity = 0.25 + Math.random() * 0.35;
    rune.style.color = hue
      ? `hsla(${hue}, 25%, 80%, ${opacity})`
      : `rgba(${200 + Math.floor(Math.random() * 40)}, ${200 + Math.floor(Math.random() * 40)}, ${210}, ${opacity})`;

    // Glow strength varies
    const glow = 4 + Math.random() * 14;
    rune.style.textShadow = `0 0 ${glow}px rgba(232, 232, 232, ${opacity * 0.8})`;

    bg.appendChild(rune);

    // Remove after animation completes
    setTimeout(() => rune.remove(), duration * 1000 + 500);
  }

  // Init when DOM ready
  if (document.readyState === "loading") {
    document.addEventListener("DOMContentLoaded", init);
  } else {
    init();
  }
})();
