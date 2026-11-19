import { node, button } from "./dom.mjs";

const invalidText = value => Array.from(value).some(c => c.length === 1 &&
  c.charCodeAt(0) >= 0xD800 && c.charCodeAt(0) <= 0xDFFF);

function renderCharacter(section, state, catalog, updateControls) {
  const value = key => Object.hasOwn(state.draft, key) ? state.draft[key] : state.data.config.values[key];
  const article = node("article", undefined, "prompt-entry");
  article.dataset.promptStem = "character";
  const label = node("label", "人物性格", "prompt-switch");
  const toggle = node("input"); toggle.type = "checkbox"; toggle.id = "config-character_prompt_enabled";
  toggle.dataset.editable = "true";
  label.htmlFor = toggle.id; label.append(toggle);
  const select = node("select"); select.id = "config-character_preset"; select.setAttribute("aria-label", "人物性格预置");
  select.dataset.editable = "true";
  for (const [key, item] of Object.entries(catalog.characters)) {
    const option = node("option", item.label); option.value = key; select.append(option);
  }
  const area = node("textarea"); area.id = "config-character-text"; area.rows = 8; area.spellcheck = false;
  area.dataset.editable = "true";
  area.setAttribute("aria-label", "人物性格文字");
  const count = node("p", undefined, "micro"); count.id = area.id + "-count"; area.setAttribute("aria-describedby", count.id);
  function edit(key, val) {
    if (val === state.data.config.values[key]) delete state.draft[key];
    else state.draft[key] = val;
  }
  function edits() { try { return JSON.parse(value("character_preset_texts") || "{}"); } catch { return {}; } }
  function selected() {
    return select.value === "custom" ? value("character_custom_text") || "" :
      edits()[select.value] ?? catalog.characters[select.value].text;
  }
  function paint() {
    const size = Array.from(area.value).length;
    const bad = size > catalog.character_max_chars || invalidText(area.value) || (toggle.checked && !area.value.trim());
    const message = "最多10000字，开启时不能为空，不能含无效字符";
    area.setCustomValidity(bad ? message : "");
    if (bad) state.invalidFields.set("character_text", {value: area.value, message});
    else state.invalidFields.delete("character_text");
    count.textContent = `${size} / ${catalog.character_max_chars} 字${bad ? " · " + message : ""}`;
    area.placeholder = select.value === "custom" ? "由你填写人物性格" : "";
    updateControls();
  }
  function load() { area.value = selected(); paint(); }
  toggle.checked = value("character_prompt_enabled") === true;
  select.value = value("character_preset") || "sarcastic";
  toggle.addEventListener("change", () => { edit("character_prompt_enabled", toggle.checked); paint(); });
  select.addEventListener("change", () => { edit("character_preset", select.value); load(); });
  area.addEventListener("input", () => {
    if (select.value === "custom") edit("character_custom_text", area.value);
    else edit("character_preset_texts", JSON.stringify({...edits(), [select.value]: area.value}));
    paint();
  });
  article._syncPrompt = () => {
    toggle.checked = value("character_prompt_enabled") === true;
    const next = value("character_preset") || "sarcastic";
    if (select.value !== next) { select.value = next; load(); }
    else if (area !== document.activeElement) load();
    else paint();
  };
  article.append(label, node("p", "在本页选择毒舌、可爱、温柔或自定义并保存。开启注入当前文字；关闭保留各自草稿。关系描述与情绪独立影响表达。", "hint"),
    select, area, count, button("恢复当前预置", () => {
      if (select.value === "custom") edit("character_custom_text", "");
      else { const next = {...edits()}; delete next[select.value]; edit("character_preset_texts", JSON.stringify(next)); }
      load();
    }));
  section.append(article); load();
}

export function renderPromptInjection(section, state, updateControls) {
  const catalog = state.data.config.prompt_injection;
  section.append(node("p", "功能提示词为预置，随对应功能提供；普通提示词独立开关，可编辑并统一保存。", "hint"));
  if (!catalog) {
    section.append(node("p", "提示词读取失败，请检查插件版本。", "empty"));
    return;
  }
  if (catalog.characters) renderCharacter(section, state, catalog, updateControls);
  const coreLabel = node("label", "通用说明 · 预置", "prompt-switch");
  const coreToggle = node("input"); coreToggle.type = "checkbox"; coreToggle.id = "config-prompt_core_enabled";
  coreToggle.dataset.editable = "true";
  coreLabel.htmlFor = coreToggle.id; coreLabel.append(coreToggle);
  const currentCore = () => Object.hasOwn(state.draft, "prompt_core_enabled") ? state.draft.prompt_core_enabled : state.data.config.values.prompt_core_enabled;
  coreToggle.checked = currentCore() !== false;
  coreToggle.addEventListener("change", () => {
    if (coreToggle.checked === state.data.config.values.prompt_core_enabled) delete state.draft.prompt_core_enabled;
    else state.draft.prompt_core_enabled = coreToggle.checked;
    updateControls();
  });
  coreLabel.dataset.promptStem = "core";
  coreLabel._syncPrompt = () => { coreToggle.checked = currentCore() !== false; };
  section.append(coreLabel, node("p", "在本页调整。开启注入下方共享、情绪和关系说明；关闭不注入这些说明，动态关系描述仍保留。", "hint"));
  const core = node("details", undefined, "prompt-core");
  core.append(node("summary", "预置提示词"));
  core.open = state.promptReadonlyOpen === true;
  core.addEventListener("toggle", () => { state.promptReadonlyOpen = core.open; });
  for (const item of [...catalog.shared || [], ...catalog.core || []]) {
    const article = node("article", undefined, "prompt-entry");
    article.append(node("h4", item.title), node("p", item.scope, "micro"),
      node("pre", item.text, "prompt-readonly"));
    core.append(article);
  }
  section.append(core, node("h3", "普通提示词"));
  for (const item of catalog.ordinary || []) {
    if (!state.data.config.values[item.stem + "_enabled"] &&
        state.data.config.values[item.stem + "_text"] === item.default) continue;
    const enabledKey = item.stem + "_enabled", textKey = item.stem + "_text";
    const article = node("article", undefined, "prompt-entry");
    const label = node("label", item.title, "prompt-switch");
    const toggle = node("input"); toggle.type = "checkbox";
    toggle.id = "config-" + enabledKey; toggle.dataset.key = enabledKey; toggle.dataset.editable = "true";
    label.htmlFor = toggle.id; label.append(toggle);
    const area = node("textarea"); area.rows = 5; area.spellcheck = false;
    area.id = "config-" + textKey; area.dataset.key = textKey; area.dataset.editable = "true";
    area.setAttribute("aria-label", item.title + " · 提示词");
    const count = node("p", undefined, "micro"); count.id = area.id + "-count";
    area.setAttribute("aria-describedby", count.id);
    const value = key => Object.hasOwn(state.draft, key) ? state.draft[key] : state.data.config.values[key];
    toggle.checked = value(enabledKey) === true;
    area.value = value(textKey) ?? item.default;
    function paint() {
      const size = Array.from(area.value).length;
      const invalid = size > catalog.max_chars || (toggle.checked && !area.value.trim());
      area.setCustomValidity(invalid ? "文本最多2000字，开启时不能为空" : "");
      if (invalid) state.invalidFields.set(textKey, { value: area.value, message: "文本最多2000字，开启时不能为空" });
      else state.invalidFields.delete(textKey);
      count.textContent = `${size} / ${catalog.max_chars} 字 · ${area.value === item.default ? "预置" : "自定义"}${invalid ? " · 文本最多2000字，开启时不能为空" : ""}`;
      updateControls();
    }
    function edit(key, val) {
      if (JSON.stringify(val) === JSON.stringify(state.data.config.values[key])) delete state.draft[key];
      else state.draft[key] = val;
      paint();
    }
    toggle.addEventListener("change", () => edit(enabledKey, toggle.checked));
    area.addEventListener("input", () => edit(textKey, area.value));
    article.append(label, node("p", "开启后在本页编辑并保存，普通主回复追加本项；关闭保留文本。功能指令始终按原功能提供。", "hint"),
      area, count, button("恢复预置", () => { area.value = item.default; edit(textKey, area.value); }));
    article.dataset.promptStem = item.stem;
    article._syncPrompt = () => {
      if (!Object.hasOwn(state.draft, enabledKey)) toggle.checked = state.data.config.values[enabledKey] === true;
      if (!Object.hasOwn(state.draft, textKey) && area !== document.activeElement) area.value = state.data.config.values[textKey] ?? item.default;
      paint();
    };
    section.append(article); paint();
  }
}

export function syncPromptInjection(root) {
  root.querySelectorAll("[data-prompt-stem]").forEach(article => article._syncPrompt?.());
}
