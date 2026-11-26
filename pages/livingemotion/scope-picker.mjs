import { t } from "./i18n.mjs?v=eff0d6f932b0";
import { node } from "./dom.mjs?v=eff0d6f932b0";
import { list, text } from "./model.mjs?v=eff0d6f932b0";

export const SCOPE_SUGGESTION_LIMIT = 10;
export function scopeSuggestions(contexts, personaId, query = "") {
  const term = query.trim().toLocaleLowerCase();
  return list(contexts).filter(item => item?.persona_id === personaId &&
    ["private", "group"].includes(item.view_scope) &&
    (!term || [item.account_id, item.scene_id, item.nickname, item.label]
      .some(value => text(value, "").toLocaleLowerCase().includes(term))))
    .sort((a, b) => Number(b.account_id === query.trim()) - Number(a.account_id === query.trim()) ||
      Number(b.view_scope === "private") - Number(a.view_scope === "private"))
    .slice(0, SCOPE_SUGGESTION_LIMIT);
}

// 用户维度：同一 QQ 的私聊与各群合成一项；其余字段取自该 QQ 最近更新的会话（宿主顺序）。
export function personSuggestions(contexts, personaId, query = "") {
  const term = query.trim().toLocaleLowerCase(), people = new Map();
  for (const item of list(contexts)) {
    if (item?.persona_id !== personaId || !item.person_id || !["private", "group"].includes(item.view_scope)) continue;
    const person = people.get(item.person_id);
    if (person) person.scenes.push(item.view_scope);
    else people.set(item.person_id, { ...item, id: item.person_id, scenes: [item.view_scope] });
  }
  const rank = item => Number(item.account_id !== query.trim());
  return [...people.values()]
    .filter(item => !term || [item.account_id, item.nickname, item.label]
      .some(value => text(value, "").toLocaleLowerCase().includes(term)))
    .map((item, index) => ({ item, index }))
    .sort((a, b) => rank(a.item) - rank(b.item) || a.index - b.index)
    .slice(0, SCOPE_SUGGESTION_LIMIT).map(entry => entry.item);
}

export function personSceneLabel(item) {
  const groups = item.scenes.length - item.scenes.filter(kind => kind === "private").length;
  return [item.scenes.includes("private") ? t("私聊") : "", groups ? t("{0} 个群聊", [groups]) : ""]
    .filter(Boolean).join(" + ") || t("群聊");
}

export function contextEmotionPicker({ contexts, selection, disabled, onSelect, dimension = "conversation" }) {
  const byPerson = dimension === "user";
  const form = node("form", undefined, "context-emotion-picker");
  form.style.cssText = "display:flex;align-items:center;gap:12px;flex-wrap:wrap";
  const search = node("input");
  search.id = "context-emotion-query"; search.type = "search"; search.maxLength = 200;
  search.placeholder = t("输入账号 ID 或昵称");
  search.setAttribute("aria-label", t("查找会话对象"));
  search.style.cssText = "min-width:0;max-width:100%";
  const picker = node("select"); picker.id = "context-emotion-picker";
  picker.style.maxWidth = "100%";
  const label = node("label", t("会话对象")); label.htmlFor = picker.id;
  const hint = node("span", "", "micro"); hint.setAttribute("aria-live", "polite");
  let suggestions = [];
  const selected = () => byPerson
    ? personSuggestions(contexts, selection.persona_id).find(item => item.id === selection.context_id)
    : list(contexts).find(item => item.id === selection.context_id && item.persona_id === selection.persona_id);
  const render = () => {
    suggestions = byPerson ? personSuggestions(contexts, selection.persona_id, search.value)
      : scopeSuggestions(contexts, selection.persona_id, search.value);
    // 已选对象即使不在最近十条中，也占用一个候选名额；刷新不丢选中项。
    const current = selected();
    if (!search.value.trim() && current && !suggestions.some(item => item.id === current.id)) {
      suggestions = [current, ...suggestions].slice(0, SCOPE_SUGGESTION_LIMIT);
    }
    picker.replaceChildren();
    const all = node("option", t("人格总体 · 不含对象情绪")); all.value = ""; picker.append(all);
    for (const item of suggestions) {
      const scene = byPerson ? personSceneLabel(item)
        : `${item.view_scope === "private" ? t("私聊") : t("群聊")} / ${item.scene_id}`;
      const option = node("option", `${text(item.nickname, item.account_id)} · ${item.account_id} · ${scene}`);
      option.value = item.id; picker.append(option);
    }
    picker.value = suggestions.some(item => item.id === selection.context_id) ? selection.context_id : "";
    hint.textContent = search.value.trim() && !suggestions.length ? t("没有匹配的会话对象") : "";
  };
  const choose = context => onSelect(context ? {
    persona_id: selection.persona_id, view_scope: context.view_scope,
    platform: context.platform, context_id: context.id,
  } : { persona_id: selection.persona_id, view_scope: "global" });
  search.addEventListener("input", render);
  picker.addEventListener("change", () => choose(suggestions.find(item => item.id === picker.value)));
  form.addEventListener("submit", event => {
    event.preventDefault();
    const exact = suggestions.filter(item => item.account_id === search.value.trim());
    const target = exact.find(item => item.view_scope === "private") ||
      (exact.length === 1 ? exact[0] : suggestions.length === 1 ? suggestions[0] : null);
    if (target) choose(target);
    else hint.textContent = t(byPerson ? "请从候选中选择具体对象" : "请从候选中选择具体会话");
  });
  search.disabled = picker.disabled = disabled;
  form.append(label, search, picker, hint);
  render();
  return form;
}
