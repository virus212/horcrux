// HORCRUX · Toast notifications system
window.toast = (message, type = "info", duration = 4000) => {
  const container = document.getElementById("toastContainer");
  if (!container) {
    // Fallback to alert if container missing
    alert(message);
    return;
  }

  const t = document.createElement("div");
  t.className = `toast ${type}`;

  const icons = { success: "✅", error: "❌", warning: "⚠️", info: "ℹ️" };
  t.innerHTML = `<span class="icon">${icons[type] || icons.info}</span>
                 <span class="msg">${escapeHtml(message)}</span>`;

  // Click to dismiss
  t.addEventListener("click", () => removeToast(t));

  container.appendChild(t);

  // Auto-remove
  setTimeout(() => removeToast(t), duration);

  function removeToast(el) {
    if (!el || el.classList.contains("fade-out")) return;
    el.classList.add("fade-out");
    setTimeout(() => el.remove(), 320);
  }

  function escapeHtml(s) {
    const map = { "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#039;" };
    return String(s).replace(/[&<>"']/g, c => map[c]);
  }
};
