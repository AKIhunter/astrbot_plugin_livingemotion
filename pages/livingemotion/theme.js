(() => {
  "use strict";
  const key = "livingemotion.theme.v1";
  const root = document.documentElement;
  const system = window.matchMedia("(prefers-color-scheme: dark)");
  let manual = null;
  let stored = true;
  try {
    const value = localStorage.getItem(key);
    if (value === "dark" || value === "light") manual = value;
  } catch (_) { stored = false; }

  function paint() {
    const theme = manual || (system.matches ? "dark" : "light");
    // The host SDK owns data-theme; keep the user's page preference separate.
    root.dataset.leTheme = theme;
    root.style.colorScheme = theme;
    document.querySelectorAll("[data-theme-choice]").forEach(button => {
      button.setAttribute("aria-pressed", String(button.dataset.themeChoice === theme));
    });
    const status = document.getElementById("theme-status");
    if (status) status.textContent = !stored ? "仅本次页面有效" : manual ? "已记住偏好" : "跟随系统";
  }

  // This synchronous script runs before the stylesheet and first content paint.
  paint();
  document.addEventListener("DOMContentLoaded", paint, { once: true });
  document.addEventListener("click", event => {
    const button = event.target.closest("[data-theme-choice]");
    if (!button) return;
    manual = button.dataset.themeChoice;
    try { localStorage.setItem(key, manual); stored = true; } catch (_) { stored = false; }
    paint();
  });
  system.addEventListener?.("change", () => { if (!manual) paint(); });
  window.addEventListener("storage", event => {
    if (event.key !== key && event.key !== null) return;
    manual = event.newValue === "dark" || event.newValue === "light" ? event.newValue : null;
    paint();
  });
})();
