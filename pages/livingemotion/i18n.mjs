import { messages } from "./messages.mjs?v=eff0d6f932b0";
const reverseMessages = new Map(Object.entries(messages).flatMap(([key, values]) => values.map(value => [value, key])));
const storageKey = "livingemotion.locale.v1";
export const locales = ["zh-CN", "en", "ja"];
let language = "zh-CN";
try { const saved = globalThis.localStorage?.getItem(storageKey); if (locales.includes(saved)) language = saved; } catch (_) { /* 存储受限时仍可切换。 */ }
export const locale = () => language;
export function setLocale(value) {
  if (!locales.includes(value)) return;
  language = value;
  try { globalThis.localStorage?.setItem(storageKey, value); } catch (_) { /* 仅本页有效。 */ }
}
export function t(key, values = []) {
  const entry = Object.hasOwn(messages, key) ? messages[key] : null;
  const template = language === "zh-CN" ? key : entry?.[language === "en" ? 0 : 1] ?? key;
  return String(template).replace(/\{(\d+)\}/g, (match, index) => index < values.length ? String(values[index]) : match);
}
export function staticUI(root = document) {
  root.documentElement?.setAttribute("lang", language);
  for (const element of root.querySelectorAll("[data-i18n]")) element.textContent = t(element.dataset.i18n);
  for (const attr of ["aria-label", "title", "placeholder"]) {
    for (const element of root.querySelectorAll(`[data-i18n-${attr}]`)) element.setAttribute(attr, t(element.getAttribute(`data-i18n-${attr}`)));
  }
}
export function controlled(value) {
  if (typeof value !== "string") return value;
  const key = Object.hasOwn(messages, value) ? value : reverseMessages.get(value);
  return key ? t(key) : value;
}
export function resource(value) {
  return new Proxy(value, { get(target, key) {
    const item = Reflect.get(target, key);
    return typeof item === "string" ? controlled(item) : Array.isArray(item) ? item.map(controlled) : item;
  } });
}
