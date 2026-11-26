import { t } from "./i18n.mjs?v=eff0d6f932b0";
import { list, text } from "./model.mjs?v=eff0d6f932b0";
import { jumpToSettingsGroup } from "./settings.mjs?v=draft-errors-20261126";
import { node, button } from "./dom.mjs?v=eff0d6f932b0";

const filled = value => text(value, "").trim() !== "";
// 分区以配置 DTO 的 section 为准；focus 是这一步的第一个相关字段。
const ORDINARY_PROMPTS = ["tone_prompt", "relationship_prompt", "night_prompt"];
// 关系分区的默认值（与 config.py 一致）：任一项改过才算「已配置」。
const DEFAULT_STAGE_NAMES = '["反感","陌生","友好","亲近","独特"]';
const DEFAULT_REFUSAL = [["averse", 90], ["unfamiliar", 60], ["friendly", 30], ["close", 10], ["unique", 5]];
// 键、名称、用在哪。向量模型不是聊天模型：留空是「未配置」，不跟随主模型。
const MODELS = [
  ["provider_id", "默认生成模型", "所有后台任务"],
  ["fallback_provider_id", "备用生成模型", "主模型用不了时"],
  ["emotion_provider_id", "情绪模型", "每轮情绪分析"],
  ["behavior_provider_id", "主动行为模型", "主动找人聊天"],
  ["catchup_provider_id", "补课模型", "醒后补课"],
  ["closing_provider_id", "收尾模型", "睡前晚安"],
  ["diary_provider_id", "日记模型", "日记生成"],
  ["dream_provider_id", "梦境模型", "生成梦境"],
  ["embedding_provider_id", "原生向量模型", "本地向量记忆"],
];
const STEPS = [
  { id: "persona", key: "persona_mode", focus: "#config-persona_mode", title: "人格",
    help: "决定 TA 用哪个人格说话，在「人格与状态模式」分区切换。跟随会话人格（默认）时各聊天用各自的人格；选指定人格后所有聊天固定用同一个人格。",
    configured: values => ["explicit", "none"].includes(values.persona_mode) },
  { id: "relationship", key: "relationship_edit_enabled", focus: "#stage-name-0", title: "关系",
    help: "好感随聊天自动变化，默认只能看、不能改。在「关系」分区可以改关系名称和各档生图婉拒概率；打开「允许在关系页修改好感」后才能手动校正分数，关闭时关系页只读。",
    configured: values => values.relationship_edit_enabled === true || filled(values.relationship_special_description) ||
      (filled(values.relationship_stage_names) && values.relationship_stage_names !== DEFAULT_STAGE_NAMES) ||
      (filled(values.relationship_stage_descriptions) && values.relationship_stage_descriptions !== '["","","",""]') ||
      DEFAULT_REFUSAL.some(([stage, value]) => values[`relationship_image_refusal_${stage}`] !== value) },
  { id: "night", key: "allow_sleep", focus: "#config-allow_sleep", title: "长夜",
    help: "「允许 TA 睡眠」是睡眠和自动作息的总开关，在「长夜」分区，默认开启。关闭后 TA 始终清醒、精力保持 100%；开启时要在「快速开始」分区填好时区，自动作息才会运行。",
    configured: values => values.allow_sleep === false || filled(values.timezone) },
  { id: "prompts", key: "character_prompt_enabled", focus: "#config-character_prompt_enabled", title: "提示词注入",
    help: "都在「提示词注入」分区。人物性格和三条普通提示词（情绪与毒舌、关系与行动边界、作息与收尾）默认关闭，打开才加进回复，关闭不追加；通用说明默认开启，关掉后不再注入情绪和关系说明。",
    configured: values => values.character_prompt_enabled === true || values.prompt_core_enabled === false ||
      ORDINARY_PROMPTS.some(stem => values[`${stem}_enabled`] === true) },
  { id: "style", key: "persona_id", focus: "#config-persona_id", title: "风格摘要",
    help: "在「人格与状态模式」分区、原生人格下拉框下方。可以手写，也可以用「用主模型自动填写」；留空就用原生人格前缀，写了只给本插件用，不改原生人格。",
    configured: () => styleCustom },
  { id: "models", key: "provider_id", focus: "#config-provider_id", title: "模型选择",
    help: "全部留空就是跟随主模型，只在某项需要单独指定时才选。默认生成模型留空时用当前聊天模型；向量模型是另一类模型，只有本地向量记忆需要，留空即未配置。",
    configured: values => MODELS.some(([key]) => filled(values[key])) },
];
// 设置页每 60 秒自动刷新、切换页签都会重建 DOM：展开状态留在模块里，清单不会被自动收起。
let open = false;
// 风格摘要不在配置值里：只跟风格摘要编辑器自己的 data-custom 同步。
let styleCustom = false, view = null, observer = null;

const groupOf = (state, key) => state.data.config.fields.find(field => field.key === key)?.section;
function modelState(state, key) {
  const value = text(state.data.config.values[key], "").trim();
  if (!value) return key === "embedding_provider_id" ? t("未配置") : t("跟随主模型");
  const field = state.data.config.fields.find(item => item.key === key);
  return list(field?.options).find(option => option?.value === value)?.label || value;
}
// 只改状态文字，不重建清单：自动刷新时正在点按的按钮不会丢焦点。
function paint(panel, state) {
  if (!panel) return;
  const values = state.data.config.values;
  for (const step of STEPS) {
    const done = step.configured(values);
    const badge = panel.querySelector(`[data-onboarding-step="${step.id}"] > .status`);
    badge.textContent = done ? t("已配置") : t("默认");
    badge.className = done ? "status good" : "status";
  }
  for (const control of panel.querySelectorAll("[data-onboarding-key]")) {
    control.querySelector(".onboarding-model-state").textContent = modelState(state, control.dataset.onboardingKey);
  }
}
function goTo(root, state, group, selector) {
  jumpToSettingsGroup(root, group, state);
  const section = root.querySelector(`[data-task-group="${group}"]`);
  if (!section) return; // 找不到分区时 jumpToSettingsGroup 已给出控制台提示。
  section.scrollIntoView({ block: "start" });
  section.querySelector(selector)?.focus();
}
function renderModels(root, state) {
  const rows = node("ul", undefined, "onboarding-models");
  for (const [key, name, use] of MODELS) {
    const control = button("", () => goTo(root, state, groupOf(state, key), `#config-${key}`), "onboarding-model");
    control.dataset.onboardingKey = key;
    control.append(node("span", t(name), "onboarding-model-name"), node("span", t(use), "onboarding-model-use"),
      node("span", undefined, "onboarding-model-state"));
    const row = node("li"); row.append(control); rows.append(row);
  }
  return rows;
}
function renderStep(step, index, root, state) {
  const item = node("li", undefined, "onboarding-step"); item.dataset.onboardingStep = step.id;
  const body = node("div", undefined, "onboarding-text");
  body.append(node("h3", `${index + 1}. ${t(step.title)}`), node("p", t(step.help), "hint"));
  const go = button(t("去设置"), () => goTo(root, state, groupOf(state, step.key), step.focus), "onboarding-go");
  go.setAttribute("aria-label", t("去设置：{0}", [t(step.title)]));
  item.append(body, node("span", undefined, "status"), go);
  if (step.id === "models") item.append(renderModels(root, state));
  return item;
}
export function mountOnboarding(jumps, state) {
  const root = jumps.parentElement;
  const panel = node("section", undefined, "onboarding"); panel.id = "onboarding-panel";
  panel.dataset.onboarding = ""; panel.hidden = !open; panel.setAttribute("aria-labelledby", "onboarding-toggle");
  const toggle = button(t("新手引导"), () => {
    open = !open; panel.hidden = !open; toggle.setAttribute("aria-expanded", String(open));
  }, "onboarding-toggle");
  toggle.id = "onboarding-toggle"; toggle.setAttribute("aria-expanded", String(open));
  toggle.setAttribute("aria-controls", panel.id);
  const list = node("ol", undefined, "onboarding-steps");
  list.append(...STEPS.map((step, index) => renderStep(step, index, root, state)));
  panel.append(list);
  jumps.before(toggle, panel);
  paint(panel, state);
  view = { root, state };
  // 风格摘要编辑器读完或保存后会改写 data-custom：据此刷新第 5 步的状态。
  observer ??= new MutationObserver(() => {
    styleCustom = view.root.querySelector(".style-summary-text")?.dataset.custom === "true";
    paint(view.root.querySelector("[data-onboarding]"), view.state);
  });
  observer.observe(root, { attributes: true, attributeFilter: ["data-custom"], subtree: true });
}
export function syncOnboarding(root, state) { paint(root.querySelector("[data-onboarding]"), state); }
