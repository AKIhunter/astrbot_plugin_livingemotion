import { t } from "./i18n.mjs";
import { node, button } from "./dom.mjs";

export const EXPERIENCE_TABS = ["settings", "diary", "dream"];
let animations = [];
export function cancelPageTurn() {
  animations.forEach(animation => animation.cancel());
  animations = [];
}
export function turnPage(previous, next, targets) {
  cancelPageTurn();
  if (previous === next || matchMedia("(prefers-reduced-motion: reduce)").matches) return;
  for (const target of targets.filter(target => target && !target.hidden)) {
    if (typeof target.animate !== "function") continue;
    const animation = target.animate([
      { opacity: .25 }, { opacity: 1 },
    ], { duration: 140, easing: "ease-out" });
    animations.push(animation);
  }
}
export function selectExperienceTab(tabs, selected) {
  tabs.style.setProperty("--tab-index", EXPERIENCE_TABS.indexOf(selected));
  for (const tab of tabs.querySelectorAll('[role="tab"]')) {
    const active = tab.dataset.recordKind === selected;
    tab.setAttribute("aria-selected", String(active));
    tab.tabIndex = active ? 0 : -1;
  }
}
export function experienceTabs(selected, select) {
  const tabs = node("div", undefined, "sub-tabs experience-tabs");
  tabs.setAttribute("role", "tablist");
  tabs.setAttribute("aria-label", t("日记与梦境"));
  const labels = { settings: t("设置"), diary: t("日记"), dream: t("梦境") };
  const indicator = node("span", undefined, "experience-tab-indicator");
  indicator.setAttribute("aria-hidden", "true"); tabs.append(indicator);
  for (const key of EXPERIENCE_TABS) {
    const tab = button(labels[key], () => select(key));
    tab.id = `experience-tab-${key}`;
    tab.dataset.recordKind = key;
    tab.setAttribute("role", "tab");
    tab.setAttribute("aria-selected", String(selected === key));
    tab.setAttribute("aria-controls", `experience-panel-${key}`);
    tab.tabIndex = selected === key ? 0 : -1;
    tabs.append(tab);
  }
  tabs.addEventListener("keydown", event => {
    if (!["ArrowLeft", "ArrowRight", "Home", "End"].includes(event.key)) return;
    event.preventDefault();
    const index = EXPERIENCE_TABS.indexOf(tabs.querySelector('[aria-selected="true"]').dataset.recordKind);
    select(event.key === "Home" ? "settings" : event.key === "End" ? "dream" :
      EXPERIENCE_TABS[(index + (event.key === "ArrowRight" ? 1 : 2)) % 3]);
  });
  selectExperienceTab(tabs, selected);
  return tabs;
}
