(() => {
  "use strict";
  const key = "livingemotion.theme.v1";
  const root = document.documentElement;
  const system = window.matchMedia("(prefers-color-scheme: dark)");
  const reduced = window.matchMedia("(prefers-reduced-motion: reduce)");
  let manual = null, stored = true, active = null, pending = null;
  try {
    const value = localStorage.getItem(key);
    if (value === "dark" || value === "light") manual = value;
  } catch (_) { stored = false; }
  const desired = () => manual || (system.matches ? "dark" : "light");
  function paint(theme = desired()) {
    root.dataset.leTheme = theme;
    root.style.colorScheme = theme;
    document.querySelectorAll("[data-theme-choice]").forEach(control => {
      control.setAttribute("aria-pressed", String(control.dataset.themeChoice === theme));
    });
    const status = document.getElementById("theme-status");
    if (status) {
      const label = !stored ? "仅本次页面有效" : manual ? "已记住偏好" : "跟随系统";
      status.textContent = window.livingEmotionTranslate ? window.livingEmotionTranslate(label) : label;
    }
  }
  function finish(token) {
    if (active !== token) return;
    active = null;
    delete root.dataset.leTransition;
    if (pending) { const next = pending; pending = null; reveal(next); }
  }
  function reveal(point) {
    const theme = desired();
    if (active) { pending = point; return; }
    if (reduced.matches || root.dataset.leTheme === theme) { paint(); return; }
    const token = {}; active = token;
    const x = point.x, y = point.y;
    const radius = Math.hypot(Math.max(x, innerWidth - x), Math.max(y, innerHeight - y));
    const circles = [`circle(0px at ${x}px ${y}px)`, `circle(${radius}px at ${x}px ${y}px)`];
    root.dataset.leTransition = "running";
    if (typeof document.startViewTransition === "function") {
      try {
        const transition = document.startViewTransition(() => paint(theme));
        token.transition = transition;
        transition.ready.then(async () => {
          if (active !== token) return;
          const animation = root.animate({ clipPath: circles }, {
            duration: 480, easing: "cubic-bezier(.25,1,.5,1)", fill: "both",
            pseudoElement: "::view-transition-new(root)",
          });
          token.animation = animation;
          try { await animation.finished; }
          finally { animation.cancel(); }
          // Release the filled pseudo effect, then wait for native teardown
          // before marking this transition complete or starting the next one.
          await transition.finished;
        }).catch(() => { transition.skipTransition(); paint(theme); }).finally(() => finish(token));
        return;
      } catch (_) { /* A flat, non-interactive cover is the progressive fallback. */ }
    }
    const cover = document.createElement("div");
    cover.className = "theme-cover"; cover.setAttribute("aria-hidden", "true");
    const before = root.dataset.leTheme;
    paint(theme);
    cover.style.background = getComputedStyle(document.body).backgroundColor;
    paint(before);
    document.body.append(cover);
    if (typeof cover.animate !== "function") { paint(); cover.remove(); finish(token); return; }
    token.cover = cover;
    token.animation = cover.animate({ clipPath: circles }, {
      duration: 480, easing: "cubic-bezier(.25,1,.5,1)",
    });
    token.animation.finished.catch(() => {}).finally(() => { paint(pending || reduced.matches ? desired() : theme); cover.remove(); finish(token); });
  }
  paint();
  window.addEventListener("livingemotion:locale", () => paint());
  document.addEventListener("DOMContentLoaded", () => paint(), { once: true });
  document.addEventListener("click", event => {
    const control = event.target.closest("[data-theme-choice]");
    if (!control) return;
    manual = control.dataset.themeChoice;
    try { localStorage.setItem(key, manual); stored = true; } catch (_) { stored = false; }
    const rect = control.getBoundingClientRect();
    reveal({ x: event.detail ? event.clientX : rect.x + rect.width / 2,
      y: event.detail ? event.clientY : rect.y + rect.height / 2 });
  });
  reduced.addEventListener?.("change", () => {
    if (!reduced.matches) return;
    pending = null; active?.transition?.skipTransition(); active?.animation?.cancel(); paint();
  });
  system.addEventListener?.("change", () => { if (!manual) paint(); });
  window.addEventListener("storage", event => {
    if (event.key !== key && event.key !== null) return;
    manual = event.newValue === "dark" || event.newValue === "light" ? event.newValue : null;
    if (active) pending = { x: innerWidth / 2, y: innerHeight / 2 };
    else paint();
  });
})();
