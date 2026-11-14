import { t, locale } from "../i18n.mjs?v=eff0d6f932b0";
import { node, button, svgNode, labelled } from "../dom.mjs?v=eff0d6f932b0";
import { object, list, text, percent, scopeParams, relationshipStage } from "../model.mjs?v=eff0d6f932b0";
import { pageError } from "../api.mjs?v=eff0d6f932b0";
import { seedPeople, constrain3D, separate3D, createForce3D } from "./force3d.mjs?v=eff0d6f932b0";
export const NODE_CAP = 200;
export const PERSON_RADIUS = 4.5, CENTER_CLEARANCE = 68, PERSON_SPACING = 20;
// 常驻显示名字的子节点数量：按与中心的距离升序取，其余只在悬浮时出现。
export const LABEL_LIMIT = 20;
// 每次挂载的渐变 id 前缀，避免同页多次渲染时 defs id 撞车。
let graphSeq = 0;
// 有正负深度的透视相机。距离与碰撞都在三维模型空间约束。
export const VIEW = { yaw: .34, pitch: -.2, focal: 900, width: 720, height: 420 };
const DEFAULT_VIEW = { yaw: VIEW.yaw, pitch: VIEW.pitch };

export function projectPoint(x, y, z, view = VIEW) {
  const dx = x - 360, dy = y - 210, depth = z;
  const cy = Math.cos(view.yaw), sy = Math.sin(view.yaw);
  const rx = dx * cy + depth * sy;
  const rz = -dx * sy + depth * cy;
  const cp = Math.cos(view.pitch), sp = Math.sin(view.pitch);
  const ry = dy * cp - rz * sp;
  const rz2 = dy * sp + rz * cp;
  const scale = view.focal / Math.max(view.focal * .5, view.focal + rz2);
  // 留出边距，保证默认缩放下旋转后节点不会被画布裁掉。
  return { x: 360 + rx * scale * .78, y: 210 + ry * scale * .78, depth: rz2, scale };
}

export function constrainPerson(item) {
  constrain3D(item);
}
// 好感度归一化：缺失值取中值，避免"没有数据"被误读成"关系很远"。
export function normalizeAffinity(item) {
  const score = relationshipScore(item);
  return score === null ? .5 : Math.max(0, Math.min(1, score / 100));
}
export function spreadPeople(items) {
  return seedPeople(items);
}
export function separatePeople(items, passes = 3) {
  separate3D(items, passes);
}
export function relationshipScore(item) {
  const value = item.score;
  return typeof value === "number" && Number.isFinite(value) && value >= 0 && value <= 100 ? value : null;
}
// 图例项：图形符号用 CSS 类控制，统一在 style.css 里取主题变量。
function legendItem(kind, label) {
  const item = node("span", undefined, `legend-item ${kind}`);
  item.append(node("i", undefined, "legend-mark"), node("span", label));
  return item;
}
// 五维与事件信号用「人话」解释：只说什么时候升、什么时候降，不暴露字段名或公式。
// 信号权重存基准值，页面按当前情绪强度档位等比折算后再展示。
const DIMENSION_NOTES = [
  ["pleasure", "愉悦", "被夸、被关心、聊得开心", "被冒犯、被冷落、气氛变差", "约 30 分钟"],
  ["arousal", "唤醒", "被骂、突发消息、意外惊吓", "安静一段时间、话题变平", "约 20 分钟"],
  ["stress", "压力", "被冒犯、起冲突、被催促", "对方道歉、语气缓和", "约 40 分钟"],
  ["social_need", "社交需求", "被关心、被感谢、对方难过", "收到回复、互动得到满足", "约 60 分钟"],
  ["control", "底气", "模型判断这次对话有把握", "没把握、拿不准时回落", "约 60 分钟到 50%"],
];
const DIMENSION_HELP = {
  pleasure: "被夸、被感谢、被关心会升高；被侮辱、被冷落会下降；没有新互动就慢慢回到基准。",
  arousal: "突发消息、被骂、意外会升高；安静下来后回落最快，所以它波动最明显。",
  stress: "冲突、被指责、被催促会升高；道歉、安抚、话题变轻松会下降。",
  social_need: "被关心、被感谢、对方难过时想靠近，会升高；收到回复、陪伴需求被满足会下降。",
  control: "只由模型判断这次回复有多少把握，本地规则不改它；它只影响页面展示，不参与情绪计算，也不会传给回复模型。",
};
const INTENSITY_GAIN = { gentle: 1.35, normal: 1.6, intense: 2.0 };
const INTENSITY_LABEL = { gentle: "保守", normal: "平常", intense: "激进" };
const RULE_NOTES = [
  ["insult", "侮辱", "本地关键词", -0.14, 0.12, 0.14, 0.04],
  ["praise", "称赞", "本地关键词", 0.12, 0.05, -0.04, -0.02],
  ["constructive_criticism", "建设性批评", "本地关键词", 0.04, 0.03, -0.02, -0.01],
  ["teaching", "教导", "本地关键词", 0.06, 0.04, -0.03, -0.01],
  ["care", "关心", "本地关键词", 0.12, -0.02, -0.06, -0.06],
  ["gratitude", "感谢", "本地关键词", 0.10, 0.02, -0.04, -0.05],
  ["apology", "道歉", "本地关键词", 0.05, -0.04, -0.08, -0.02],
  ["conflict", "冲突", "事件信号", -0.12, 0.12, 0.14, 0.04],
  ["boundary_respected", "边界被尊重", "事件信号", 0.06, -0.02, -0.04, -0.02],
  ["boundary_violated", "边界被冒犯", "事件信号", -0.08, 0.08, 0.12, 0.02],
  ["promise_kept", "说到做到", "事件信号", 0.07, 0.01, -0.03, -0.02],
  ["promise_broken", "食言", "事件信号", -0.08, 0.04, 0.08, 0.02],
  ["sadness", "对方低落", "关键词或模型", 0, 0.03, 0.02, 0.04],
  ["anxiety", "对方焦虑", "关键词或模型", 0, 0.04, 0.03, 0.04],
  ["joy", "对方开心", "关键词或模型", 0.08, 0.04, -0.02, -0.03],
  ["surprise", "意外消息", "关键词或模型", 0.02, 0.12, 0.02, 0.01],
  ["interaction", "普通互动", "兜底默认", 0.01, 0.01, 0, -0.01],
  ["reply_succeeded", "回复发出成功", "TA 的动作", 0.01, 0, 0, -0.02],
];
const RULE_HELP = {
  insult: "被骂或被贬低：心情明显变差、压力上升，也更想有人陪。",
  praise: "被夸或被认可：心情变好，压力下降。",
  constructive_criticism: "对方认真指出问题但态度友善：会有一点不舒服，整体仍算良性互动。",
  teaching: "被耐心讲解或指导：会感到被重视，压力略降。",
  care: "被问候、被照顾：心情变好，压力明显下降。",
  gratitude: "被感谢：心情和陪伴需求都会上升。",
  apology: "对方道歉：压力和负面情绪下降。",
  conflict: "正面起冲突：心情变差，警觉和压力一起上升。",
  boundary_respected: "对方尊重你的边界：心情变好，压力下降。",
  boundary_violated: "边界被冒犯：心情变差、压力上升、警觉提高。",
  promise_kept: "对方说到做到：信任感上升，压力下降。",
  promise_broken: "对方食言：心情变差，警觉和压力上升。",
  sadness: "对方说难过的事：会跟着有点低落，更想陪伴对方。",
  anxiety: "对方焦虑：会跟着紧张，也更想靠近。",
  joy: "对方分享开心的事：会一起开心。",
  surprise: "听到意外消息：会短暂惊讶、警觉。",
  interaction: "普通聊天：一点点正面影响，不会大幅波动。",
  reply_succeeded: "TA 成功发出回复：陪伴需求略降，压力也降一点。",
};
// 基准权重按当前强度档位折算成页面显示的生效值。
const signed = (value, gain) => {
  const scaled = Math.round(value * gain * 100) / 100;
  return scaled === 0 ? "0" : `${scaled > 0 ? "+" : "−"}${Math.abs(scaled).toFixed(2)}`;
};
// TA 页每 60 秒自动刷新会重建 DOM：展开状态存在模块里，避免把用户点开的说明自动收起。
let explainerOpen = false;
const expandedHelp = new Set();
// 问号同时支持悬浮（title）与点开（内联展开），不引入额外弹层依赖。
function helpCell(label, explanation, key) {
  const cell = node("td", undefined, "explainer-help");
  const expanded = expandedHelp.has(key);
  const tip = node("span", explanation, "help-text");
  tip.hidden = !expanded;
  const control = button("?", () => {
    const next = control.getAttribute("aria-expanded") !== "true";
    control.setAttribute("aria-expanded", String(next));
    tip.hidden = !next;
    if (next) expandedHelp.add(key); else expandedHelp.delete(key);
  }, "help-button");
  control.setAttribute("aria-label", t("查看{0}的说明", [label]));
  control.setAttribute("aria-expanded", String(expanded));
  control.title = explanation;
  cell.append(control, tip);
  return cell;
}
function explainerRow(cells, label, explanation, key) {
  const row = node("tr");
  for (const value of cells) row.append(node("td", value));
  row.append(helpCell(label, explanation, key));
  return row;
}
function explainerTable(headers, rows) {
  const table = node("table", undefined, "relationship-explainer-table");
  const head = node("thead"), headRow = node("tr");
  for (const header of headers) headRow.append(node("th", header));
  head.append(headRow);
  const body = node("tbody");
  for (const row of rows) body.append(explainerRow(row.cells, row.label, row.help, row.key));
  table.append(head, body);
  const wrapper = node("div", undefined, "table-wrap"); wrapper.append(table);
  return wrapper;
}
// TA 页底部的可折叠说明；默认收起，不打断主阅读路径。
export function emotionExplainer(intensity = "normal") {
  const gain = INTENSITY_GAIN[intensity] || INTENSITY_GAIN.normal;
  const name = t(INTENSITY_LABEL[intensity] || INTENSITY_LABEL.normal);
  const wrapper = node("details", undefined, "relationship-explainer emotion-explainer");
  wrapper.dataset.emotionExplainer = "";
  wrapper.open = explainerOpen;
  wrapper.addEventListener("toggle", () => { explainerOpen = wrapper.open; });
  wrapper.append(node("summary", t("情绪与五维指标说明")));
  const body = node("div", undefined, "details-content");
  body.append(node("p", t("数字表示 TA 当前情绪的强弱。点每行右侧的问号，可以看到这个数值为什么会升降。"), "hint"));
  body.append(explainerTable([t("指标"), t("什么情况下升高"), t("什么情况下回落"), t("回落速度"), t("说明")],
    DIMENSION_NOTES.map(([key, label, up, down, speed]) => ({
      cells: [label, up, down, speed], label, help: DIMENSION_HELP[key], key: `dim:${key}`,
    }))));
  body.append(node("p", t("当前档位「{0}」：单次变化最多 {1}，同一类刺激 5 分钟内累计最多 {2}；换档位等比放大，衰减速度不变。",
    [name, (0.15 * gain).toFixed(2), (0.30 * gain).toFixed(2)]), "hint"));
  body.append(explainerTable([t("信号"), t("识别方式"), t("愉悦"), t("唤醒"), t("压力"), t("社交需求"), t("说明")],
    RULE_NOTES.map(([key, label, source, ...weights]) => ({
      cells: [label, source, ...weights.map(value => signed(value, gain))],
      label, help: RULE_HELP[key], key: `signal:${key}`,
    }))));
  body.append(node("p", t("表中是「{0}」档的生效增量；没有新的互动时，这些数值会随着时间慢慢回落到平常水平。", [name]), "hint"));
  wrapper.append(body);
  return wrapper;
}
export function graphData(raw) {
  const data = object(raw);
  if (data.api_version !== 1 || !Array.isArray(data.nodes) || !Array.isArray(data.items) ||
      data.page_size !== 10 || !Number.isSafeInteger(data.total) || data.total < 0 || data.items.length > 10 ||
      data.items.some(item => !item || typeof item.id !== "string" || !item.platform || !item.account_id)) {
    throw Object.assign(new Error(t("关系响应不符合管理契约。")), { code: "invalid_response" });
  }
  const nodes = data.nodes.filter(item => item && typeof item.id === "string" && item.platform && item.account_id);
  const seen = new Set();
  const unique = nodes.filter(item => !seen.has(item.id) && seen.add(item.id));
  const visible = unique.slice(0, NODE_CAP), ids = new Set(visible.map(item => item.id)), pairs = new Set();
  const peer_edges = list(data.peer_edges).filter(edge => {
    if (!edge || !ids.has(edge.source) || !ids.has(edge.target) || edge.source === edge.target ||
        typeof edge.relation !== "string" || !Array.isArray(edge.evidence) ||
        !edge.evidence.some(ref => ref && typeof ref.excerpt === "string")) return false;
    const key = JSON.stringify([...[edge.source, edge.target].sort(), edge.relation]);
    if (pairs.has(key)) return false;
    pairs.add(key); return true;
  }).slice(0, NODE_CAP).map(edge => ({ ...edge,
    evidence: edge.evidence.filter(ref => ref && typeof ref.excerpt === "string").slice(0, 4) }));
  return { ...data, nodes: visible, peer_edges, items: data.items };
}
export function mountRelationships(root, {
  api, selection, persona, stageNames, canWrite, onError, uncertain = new Set(), editEnabled = false,
  queryState, onQuery,
}) {
  const stageLabel = item => relationshipStage(item, stageNames).name;
  let disposed = false, sequence = 0, simulation = null, timer = null, selected = null, writing = false, graph = null;
  // 筛选/翻页状态由宿主持久化：自动刷新或切页签会重新挂载本面板，不能回到第一页。
  const saved = object(queryState);
  let page = Number.isSafeInteger(saved.page) && saved.page > 0 ? saved.page : 1,
    query = text(saved.query, "").slice(0, 200),
    platform = selection.context_id ? selection.platform || "" : text(saved.platform, ""),
    paused = false, scale = 1;
  let version = null, conflict = false, edited = null, graphKey = "";
  const positionCache = new Map();
  const motionPreference = matchMedia("(prefers-reduced-motion: reduce)");
  const compactViewport = matchMedia("(max-width: 600px)");
  const view = { ...VIEW, yaw: DEFAULT_VIEW.yaw, pitch: DEFAULT_VIEW.pitch };
  const placed = new Map();
  const writeKey = item => `relationship:${selection.persona_id}/${item.platform}/${item.account_id}`;
  const form = node("form", undefined, "record-toolbar relationship-filters");
  const search = node("input"); search.type = "search"; search.id = "relationship-query"; search.maxLength = 200; search.placeholder = t("平台账号或昵称");
  const platforms = node("select"); platforms.id = "relationship-platform";
  platforms.append(node("option", t("全部平台"))); platforms.firstChild.value = "";
  for (const item of list(selection.platforms)) {
    const option = node("option", text(item.label ?? item)); option.value = text(item.value ?? item.id ?? item, "");
    if (selection.context_id && selection.platform && option.value !== selection.platform) option.disabled = true;
    platforms.append(option);
  }
  // 人格切换后旧平台可能已不在候选里：直接回落“全部平台”，避免永久空结果。
  if (platform && ![...platforms.options].some(option => option.value === platform)) platform = "";
  platforms.value = platform;
  search.value = query;
  const submit = node("button", t("查找关系")); submit.type = "submit";
  form.append(labelled(t("平台"), platforms), labelled(t("账号搜索 · 包含未绘制节点"), search), submit);
  const count = node("p", t("正在读取关系…"), "hint");
  const device = node("div", undefined, "graph-device");
  const svg = svgNode("svg", {
    viewBox: "0 0 720 420", class: "relationship-graph",
    "aria-label": t("人格中心三维关系图，可拖动旋转，选择人物查看详情"),
  });
  const world = svgNode("g"); svg.append(world);
  const fitViewport = () => svg.setAttribute("viewBox", compactViewport.matches ? "160 10 400 400" : "0 0 720 420");
  fitViewport(); compactViewport.addEventListener("change", fitViewport);
  const tableRoot = node("div");
  const editor = node("section", undefined, "relationship-row-editor");
  editor.hidden = true;
  const editorCard = node("div"); editor.append(editorCard);
  // 图例与操作条常驻；只读详情使用已有的侧边浮层。
  const zones = node("div", undefined, "graph-zones");
  const legend = node("div", undefined, "graph-legend");
  legend.setAttribute("aria-label", t("图例"));
  const hint = node("p", t("拖拽旋转 · 滚轮缩放 · 悬浮查看 · Shift+拖动移动节点"), "graph-hint");
  hint.setAttribute("aria-live", "polite");
  const detail = node("section", undefined, "graph-detail");
  detail.setAttribute("aria-label", t("选中账号详情"));
  const card = node("div", undefined, "float-card"); detail.append(card);
  detail.hidden = true;
  const actions = node("div", undefined, "graph-actions");
  const pause = button(t("暂停布局"), () => {
    paused = !paused; pause.textContent = paused ? t("继续布局") : t("暂停布局");
    pause.setAttribute("aria-pressed", String(paused));
    if (paused) stop(); else run();
  });
  pause.setAttribute("aria-pressed", "false");
  const transform = () => world.setAttribute("transform", `translate(360 210) scale(${scale}) translate(-360 -210)`);
  const zoom = factor => { scale = Math.max(.6, Math.min(2.5, scale * factor)); transform(); };
  const reset = () => {
    scale = 1; view.yaw = DEFAULT_VIEW.yaw; view.pitch = DEFAULT_VIEW.pitch;
    transform(); draw();
  };
  const zoomButton = (label, glyph, factor) => {
    const control = button(glyph, () => zoom(factor), "graph-zoom");
    control.setAttribute("aria-label", label); control.title = label;
    return control;
  };
  actions.append(pause, zoomButton(t("放大"), "＋", 1.2), zoomButton(t("缩小"), "－", 1 / 1.2),
    button(t("复位视图"), reset), button(t("拖拽旋转"), () => {
      view.yaw = DEFAULT_VIEW.yaw + .6; view.pitch = DEFAULT_VIEW.pitch - .28; draw();
    }));
  const hintRow = node("div", undefined, "graph-hint-row");
  hintRow.append(hint, actions);
  legend.append(
    legendItem("dot center", t("中心 · 当前人格")),
    legendItem("dot near", t("越靠近中心 · 好感越高")),
    legendItem("dot far", t("越远离中心 · 好感越低")),
    legendItem("line solid", t("与人格的连线 · 粗细表示好感")),
    legendItem("line dashed", t("人物之间 · 推测线索")));
  zones.append(legend, hintRow);
  // 详情浮层只盖住画布这一块（不压住下方图例与操作条）。
  const stage = node("div", undefined, "graph-stage");
  stage.append(svg, detail);
  device.append(stage, zones);
  // 筛选放在 3D 力图和列表之间；情绪说明已移到 TA 页底部，这里不再重复。
  root.append(count, device, form, tableRoot, editor);
  let draw = () => {};
  // 供画布级点击命中使用：当前这次布局的节点列表。
  let dataNodes = [];
  function stop() { cancelAnimationFrame(timer); timer = null; svg.dataset.layout = "stopped"; }
  function run() {
    stop();
    if (!simulation || paused || disposed || document.hidden) return;
    if (motionPreference.matches) { simulation.tick(180); draw(); return; }
    svg.dataset.layout = "running";
    let frames = 0; const started = performance.now();
    const frame = () => {
      if (paused || disposed || document.hidden) return stop();
      simulation.tick(); draw();
      if (++frames >= 120 || performance.now() - started >= 2000) return stop();
      timer = requestAnimationFrame(frame);
    };
    timer = requestAnimationFrame(frame);
  }
  // 同步选中位置与只读详情提示。
  function placeDetail(item) {
    const point = placed.get(item.id);
    hint.textContent = t("已选中 {0} · 详情在右侧", [text(item.label, item.account_id)]);
    if (point) {
      detail.dataset.anchor = `${point.x.toFixed(0)},${point.y.toFixed(0)}`;
    }
  }
  // 先显示再加 class，并强制一次重排，保证每次选中都能重新播放进入动画。
  function openDetail() {
    detail.hidden = false;
    detail.classList.remove("entering");
    void detail.offsetWidth;
    detail.classList.add("entering");
  }
  function show(item) {
    selected = item;
    card.replaceChildren(); openDetail(); placeDetail(item);
    card.append(node("h2", text(item.label, t("未记录昵称"))),
      node("p", `${text(item.platform)} / ${text(item.account_id)}`, "hint"));
    card.querySelector("h2").tabIndex = -1;
    const dl = node("dl", undefined, "key-values");
    for (const [label, value] of [
      [t("亲近阶段"), stageLabel(item)], [t("好感"), relationshipScore(item) === null ? t("未提供") : relationshipScore(item).toFixed(1)],
      [t("熟悉"), item.familiarity === null ? t("未建立") : percent(item.familiarity)],
      [t("信任"), item.trust === null ? t("未建立") : percent(item.trust)],
      [t("边界"), item.boundary === null ? t("未建立") : percent(item.boundary)],
      [t("备注"), text(item.note, "")], [t("自动好感变化"), item.frozen ? t("已冻结") : t("未冻结")],
      [t("来源完整性"), text(item.source_completeness, t("未提供"))], [t("版本"), text(item.version)],
    ]) dl.append(node("dt", label), node("dd", value));
    card.append(dl);
    const sources = node("details"); sources.append(node("summary", t("真实来源会话")));
    const sourceBody = node("div", undefined, "details-content");
    for (const source of list(item.sources)) sourceBody.append(node("p",
      `${text(source.platform)} / ${text(source.view_scope)} / ${text(source.scene_id)} · ${text(source.context_id)}`, "micro"));
    if (!sourceBody.childElementCount) sourceBody.append(node("p", t("未提供来源会话，不推测关系维度。"), "hint"));
    sources.append(sourceBody); card.append(sources);
    const peers = list(graph?.peer_edges).filter(edge => edge.source === item.id || edge.target === item.id);
    if (peers.length) {
      const section = node("section", undefined, "peer-relations");
      section.append(node("h3", t("与其他人的关系线索")), node("p", t("根据陈述推测，可展开核对依据。"), "hint"));
      for (const edge of peers) {
        const other = graph.nodes.find(n => n.id === (edge.source === item.id ? edge.target : edge.source));
        const record = node("details");
        record.append(node("summary", t("{0} · {1}（推测）", [text(other?.label), text(edge.relation)])));
        const body = node("div", undefined, "details-content");
        body.append(node("p", `${text(other?.platform)} / ${text(other?.account_id)}`, "micro"));
        for (const ref of edge.evidence.slice(0, 4)) {
          body.append(node("p", `${text(ref.basis)} · ${text(ref.kind)} · ${text(ref.platform)} / ${text(ref.scene_id)}`, "micro"),
            node("blockquote", text(ref.excerpt)), node("p",
              t("{0} · 来源 {1}", [Number.isFinite(ref.at) ? new Date(ref.at * 1000).toLocaleString(locale()) : t("时间未提供"), text(ref.source_id)]), "micro"));
        }
        record.append(body); section.append(record);
      }
      card.append(section);
    }
    card.append(button(t("收起详情"), hideDetail));
    world.querySelectorAll("[data-node-id]").forEach(element => element.classList.toggle("selected", element.dataset.nodeId === item.id));
    world.querySelectorAll("[data-edge-source]").forEach(element => element.classList.toggle("selected-edge",
      element.dataset.edgeSource === item.id || element.dataset.edgeTarget === item.id));
  }
  function openRowEditor(item, preserve = false) {
    if (writing) return;
    const retained = preserve ? { affinity: editor.querySelector("#relationship-affinity")?.value,
      note: editor.querySelector("#relationship-note")?.value,
      frozen: editor.querySelector("#relationship-frozen")?.checked } : null;
    edited = item; version = item.version; conflict = false;
    editor.hidden = false; editorCard.replaceChildren();
    editorCard.append(node("h2", t("编辑 {0} 的基础信息", [text(item.label, item.account_id)])),
      node("p", `${item.platform} / ${item.account_id} · ${t("昵称来自 QQ，不在这里改名。")}`, "hint"));
    if (!editEnabled) {
      editorCard.append(node("p", t("好感编辑已关闭：可在「设置 → 关系 → 允许在关系页修改好感」中打开。"), "hint"));
    } else {
      const edit = node("form", undefined, "relationship-edit");
      const score = node("input"); score.type = "number"; score.id = "relationship-affinity"; score.min = "0"; score.max = "100"; score.step = ".1";
      score.required = true; score.value = retained?.affinity ?? (relationshipScore(item) === null ? "" : String(relationshipScore(item)));
      const note = node("textarea"); note.id = "relationship-note"; note.maxLength = 1000; note.rows = 3; note.value = retained?.note ?? text(item.note, "");
      const frozen = node("input"); frozen.id = "relationship-frozen"; frozen.type = "checkbox"; frozen.checked = retained?.frozen ?? item.frozen === true;
      const error = node("p", undefined, "error-text"); error.setAttribute("role", "alert");
      const save = node("button", t("保存基础信息")); save.type = "submit"; save.className = "primary";
      const refresh = button(t("读取最新关系并复核"), async () => {
        await load(true);
      });
      refresh.hidden = true;
      const validVersion = () => Number.isSafeInteger(version) && version >= 0;
      save.disabled = !canWrite() || !validVersion() || uncertain.has(writeKey(item));
      edit.append(labelled(t("好感 · 0–100，步进 0.1"), score), labelled(t("冻结自动好感变化"), frozen),
        labelled(t("备注 · 留空清除"), note), error, node("p",
          t("只修改当前人格的这个平台账号。操作者由宿主认证注入，不修改其他平台的同号账号。"), "hint"));
      const row = node("div", undefined, "button-row"); row.append(save, refresh); edit.append(row); editorCard.append(edit);
      edit.addEventListener("submit", async event => {
        event.preventDefault();
        if (save.disabled || writing || !canWrite() || !validVersion() || conflict || !edit.reportValidity()) return;
        const affinity = Number(score.value);
        if (!Number.isFinite(affinity) || affinity < 0 || affinity > 100 || Math.abs(affinity * 10 - Math.round(affinity * 10)) > 1e-7) return;
        save.disabled = true; writing = true; error.textContent = "";
        try {
          await api.relationship({ persona_id: selection.persona_id,
            ...(selection.context_id ? { context_id: selection.context_id } : {}),
            platform: item.platform, account_id: item.account_id,
            score: affinity, frozen: frozen.checked, note: note.value, expected_version: version, reason: "控制台编辑关系" });
          if (disposed) return;
          writing = false;
          edited = null; editor.hidden = true;
          count.textContent = t("好感已保存，正在重新读取真实关系。");
          await load();
        } catch (errorValue) {
          if (disposed) return;
          const failure = pageError(errorValue);
          if (failure.code === "version_conflict") {
            conflict = true; refresh.hidden = false; error.textContent = t("关系版本已变化。草稿保留，请读取最新关系并人工复核；未自动重试。");
          } else {
            if (["timeout", "bridge_error", "invalid_response", "unavailable"].includes(failure.code)) {
              uncertain.add(writeKey(item)); refresh.hidden = false;
            }
            error.textContent = `${failure.message}。${uncertain.has(writeKey(item)) ? t("结果不明，已禁止重复提交。") : t("未保存。")} `;
            onError(errorValue);
          }
        } finally { writing = false; if (!disposed) save.disabled = conflict || uncertain.has(writeKey(item)) || !canWrite(); }
      });
    }
    editorCard.append(button(t("关闭编辑"), () => { if (!writing) { edited = null; editor.hidden = true; } }));
  }
  function hideDetail() {
    selected = null; detail.hidden = true; card.replaceChildren();
    hint.textContent = t("拖拽旋转 · 滚轮缩放 · 悬浮查看");
  }
  async function drawGraph(data, current) {
    stop(); world.replaceChildren(); placed.clear();
    if (disposed || current !== sequence) return;
    const nodes = spreadPeople(data.nodes);
    for (const item of nodes) {
      const cached = positionCache.get(item.id);
      if (cached) Object.assign(item, cached);
    }
    dataNodes = nodes;
    const edges = list(data.edges).filter(edge => nodes.some(item => item.id === edge.target))
      .map(edge => ({ source: "__persona__", target: edge.target }));
    // 每根连线一条渐变：中心端实、节点端虚，看起来像"亲密度在衰减"，
    // 也顺手实现了轻微发光（低透明度叠加 + 选中时 drop-shadow）。
    const defs = svgNode("defs"); world.append(defs);
    const graphId = `le-graph-${++graphSeq}`;
    const gradients = edges.map((edge, index) => {
      const gradient = svgNode("linearGradient", { id: `${graphId}-edge-${index}`, gradientUnits: "userSpaceOnUse" });
      gradient.append(
        svgNode("stop", { offset: "0%", "stop-opacity": .30 }),
        svgNode("stop", { offset: "100%", "stop-opacity": .07 }));
      defs.append(gradient); return gradient;
    });
    const lines = edges.map((edge, index) => {
      const item = nodes.find(n => n.id === edge.target), affinity = relationshipScore(item) ?? 0;
      const line = svgNode("line", { class: "graph-edge", "stroke-width": 0.7 + affinity / 110,
        stroke: `url(#${graphId}-edge-${index})`,
        "data-edge-source": "__persona__", "data-edge-target": edge.target }); world.append(line); return line;
    });
    const peerEdges = data.peer_edges.map(edge => ({ ...edge }));
    const peerLines = peerEdges.map(edge => {
      const line = svgNode("line", { class: "graph-peer-edge", "data-edge-source": edge.source, "data-edge-target": edge.target });
      line.append(svgNode("title", {}, t("{0}（推测，{1}条依据）", [edge.relation, edge.evidence.length])));
      world.append(line); return line;
    });
    // 常驻标签按「离中心多近」排序取前 20：亲密的先露名字，人多了也不糊。
    const labelRank = new Map([...nodes]
      .sort((a, b) => Math.hypot(a.x - 360, a.y - 210) - Math.hypot(b.x - 360, b.y - 210))
      .slice(0, LABEL_LIMIT).map((item, index) => [item.id, index]));
    const pinnedOrder = nodes.filter(item => labelRank.has(item.id))
      .sort((a, b) => labelRank.get(a.id) - labelRank.get(b.id));
    const labelOf = new Map();
    let hoverTimer = null;
    const circles = nodes.map(item => {
      const group = svgNode("g", { "data-depth": item.depth, "data-node-id": item.id });
      const hit = svgNode("circle", { r: 11, class: "graph-hit" });
      const circle = svgNode("circle", { r: PERSON_RADIUS, tabindex: 0, role: "button", class: "graph-person",
        "data-node-id": item.id, "aria-label": t("{0} {1}，好感 {2}", [item.platform, item.account_id, relationshipScore(item) ?? t("未提供")]) });
      circle.append(svgNode("title", {}, `${text(item.label, "")} ${item.platform}/${item.account_id}`));
      if (list(data.focus_ids).includes(item.id) && query) circle.classList.add("graph-focus");
      let moved = false, start = null;

      circle.addEventListener("keydown", event => { if (event.key === "Enter" || event.key === " ") { event.preventDefault(); show(item); } });
      let drag = false;
      group.addEventListener("pointerdown", event => {
        // 默认不拦截：整块画布都能拖动旋转。只有按住 Shift 才是拖节点。
        if (!event.shiftKey) return;
        event.stopPropagation(); drag = true; moved = false; start = [event.clientX, event.clientY];
        group.setPointerCapture(event.pointerId); item.fx = item.x; item.fy = item.y;
      });
      group.addEventListener("pointermove", event => {
        if (!drag) return;
        moved ||= Math.hypot(event.clientX - start[0], event.clientY - start[1]) > 4;
        // 屏幕位移逆相机旋转回三轴；保持当前相机深度，不把 z 压回平面。
        const step = projectPoint(item.x, item.y, item.depth, view);
        const matrix = svg.getScreenCTM();
        const screenScale = Math.hypot(matrix?.a || 1, matrix?.b || 0);
        const invScale = 1 / screenScale / Math.max(.35, step.scale) / .78 / scale;
        const rx = (event.clientX - start[0]) * invScale, ry = (event.clientY - start[1]) * invScale;
        const rotatedZ = -ry * Math.sin(view.pitch);
        item.x += rx * Math.cos(view.yaw) - rotatedZ * Math.sin(view.yaw);
        item.y += ry * Math.cos(view.pitch);
        item.depth += rx * Math.sin(view.yaw) + rotatedZ * Math.cos(view.yaw);
        start = [event.clientX, event.clientY];
        constrainPerson(item);
        item.fx = item.x; item.fy = item.y; draw();
      });
      const release = () => { drag = false; item.fx = null; item.fy = null; if (!paused) run(); };
      group.addEventListener("pointerup", release); group.addEventListener("pointercancel", release);
      const label = svgNode("text", { x: 9, y: -9, class: "person-label" }, text(item.label, item.account_id).slice(0, 12));
      // 常驻 / 悬浮两种标签状态，交给 CSS 决定显隐。
      label.dataset.label = labelRank.has(item.id) ? "pinned" : "hover";
      labelOf.set(item.id, label);
      group.append(hit, circle, label); world.append(group); return group;
    });
    // 中心节点：实心、视觉权重最高、默认不写字；悬浮停留 120ms 才浮出人格名，避免划过就闪。
    const centerGroup = svgNode("g", { class: "graph-center-group" });
    const centerHalo = svgNode("circle", { cx: 360, cy: 210, r: 8, class: "graph-center-halo" });
    const centerDot = svgNode("circle", { cx: 360, cy: 210, r: 5.8, class: "graph-center" });
    const centerLabel = svgNode("text", { x: 360, y: 214, "text-anchor": "middle", class: "center-label" },
      text(persona.name, t("人格")).slice(0, 8));
    centerGroup.append(centerHalo, centerDot, centerLabel);
    centerGroup.addEventListener("pointerenter", () => {
      clearTimeout(hoverTimer);
      hoverTimer = setTimeout(() => { if (!disposed) centerGroup.classList.add("reveal"); }, 120);
    });
    centerGroup.addEventListener("pointerleave", () => {
      clearTimeout(hoverTimer); centerGroup.classList.remove("reveal");
    });
    world.append(centerGroup);
    // 可信人物连线形成分团；Bot 中心吸引、排斥与碰撞同时作用于三个轴。
    simulation = createForce3D(nodes, peerEdges);
    const allEdges = [...edges, ...peerEdges], allLines = [...lines, ...peerLines];
    draw = () => {
      // 只在拖动时做间距推挤；静态布局已经满足最小间距，不需要每帧重排。
      if (nodes.some(item => item.fx != null)) separatePeople(nodes, 4);
      const points = new Map();
      for (const item of nodes) {
        const point = projectPoint(item.x, item.y, item.depth, view);
        points.set(item.id, point); placed.set(item.id, point);
      }
      nodes.forEach((item, i) => {
        const point = points.get(item.id), group = circles[i];
        group.setAttribute("transform", `translate(${point.x.toFixed(2)} ${point.y.toFixed(2)})`);
        group.setAttribute("data-depth", point.depth.toFixed(1));
        group.setAttribute("data-model-x", item.x.toFixed(2));
        group.setAttribute("data-model-y", item.y.toFixed(2));
        group.setAttribute("data-model-z", item.depth.toFixed(2));
        positionCache.set(item.id, { x: item.x, y: item.y, depth: item.depth });
        // 透视决定大小与明暗：越远越小越淡，形成真实的前后关系。
        const radius = PERSON_RADIUS * point.scale;
        group.querySelector(".graph-person").setAttribute("r", radius.toFixed(2));
        group.setAttribute("opacity", Math.min(1, .35 + .55 * point.scale).toFixed(2));
      });
      // 后景先绘制，前景后绘制；旋转后遮挡次序随真实深度变化。
      [...nodes.keys()].sort((a, b) => points.get(nodes[b].id).depth - points.get(nodes[a].id).depth)
        .forEach(i => world.append(circles[i]));
      world.append(centerGroup);
      // 常驻标签避让：按距离从近到远依次占位，四个方向找一个不压字的位置，
      // 四个方向都占满就让位给悬浮显示。只在屏幕空间算一次，20 个标签成本可忽略。
      const boxes = [];
      for (const item of pinnedOrder) {
        const point = points.get(item.id);
        if (!point) continue;
        const label = labelOf.get(item.id);
        const outward = Math.hypot(point.x - 360, point.y - 210) || 1;
        const ux = (point.x - 360) / outward, uy = (point.y - 210) / outward;
        // 字号 11（viewBox 单位）：中日韩字符接近全角，拉丁与数字约半角，
        // 按字宽估盒子，否则中文标签会算窄一半、避让失效。
        const name = text(item.label, item.account_id).slice(0, 12);
        const width = [...name].reduce((sum, ch) => sum + (/[\u3000-\u9fff\uff00-\uffef]/.test(ch) ? 11 : 6.2), 0) + 8;
        let accepted = null;
        for (const [ox, oy] of [[ux, uy], [-ux, -uy], [0, -1], [0, 1]]) {
          const anchorX = point.x + ox * 11, anchorY = point.y + oy * 11 + (oy > .3 ? 9 : oy < -.3 ? -5 : 3);
          const box = { x: ox >= 0 ? anchorX : anchorX - width, y: anchorY - 9, w: width, h: 12 };
          const clash = boxes.some(other => box.x < other.x + other.w && other.x < box.x + box.w &&
            box.y < other.y + other.h && other.y < box.y + box.h);
          if (!clash) { accepted = { box, anchorX, anchorY, anchor: ox >= 0 ? "start" : "end" }; break; }
        }
        if (!accepted) { delete label.dataset.show; continue; }
        boxes.push(accepted.box);
        // 标签在节点组内，坐标是相对节点的偏移（组的 transform 已经带了绝对位置）。
        label.setAttribute("x", (accepted.anchorX - point.x).toFixed(1));
        label.setAttribute("y", (accepted.anchorY - point.y).toFixed(1));
        label.setAttribute("text-anchor", accepted.anchor);
        label.dataset.show = "1";
      }
      const project = id => id === "__persona__" ? { x: 360, y: 210, scale: 1 } : points.get(id);
      allEdges.forEach((edge, i) => {
        const from = project(edge.source), to = project(edge.target);
        if (!from || !to) return;
        const line = allLines[i];
        const dx = to.x - from.x, dy = to.y - from.y, d = Math.hypot(dx, dy) || 1;
        const offset = edge.source === "__persona__" ? 33 : PERSON_RADIUS * from.scale;
        const coords = {
          x1: from.x + dx / d * offset, y1: from.y + dy / d * offset,
          x2: to.x - dx / d * (PERSON_RADIUS * to.scale), y2: to.y - dy / d * (PERSON_RADIUS * to.scale),
        };
        for (const [key, value] of Object.entries(coords)) line.setAttribute(key, value);
        // 渐变跟着连线走：中心端接近实心，节点端淡出。
        const gradient = gradients[i];
        if (gradient) for (const [key, value] of Object.entries(coords)) gradient.setAttribute(key, value);
        // CSS 类里的 opacity 会盖掉 SVG 属性，所以这里写 style，保证远近层次真的生效。
        line.style.opacity = (0.45 + 0.5 * ((from.scale + to.scale) / 2)).toFixed(2);
      });
      if (selected) placeDetail(selected);
    };
    simulation.tick(100); draw(); transform(); run();
  }
  function drawTable(data) {
    tableRoot.replaceChildren();
    const wrapper = node("div", undefined, "table-wrap"), table = node("table"), head = node("thead"), tr = node("tr");
    wrapper.tabIndex = 0; wrapper.setAttribute("role", "region"); wrapper.setAttribute("aria-label", t("关系表，可左右滚动；每页10条"));
    table.className = "relationship-table";
    for (const title of [t("人物"), t("好感"), t("亲近阶段"), t("详情")]) { const th = node("th", title); th.scope = "col"; tr.append(th); }
    head.append(tr); table.append(head);
    const body = node("tbody");
    const items = data.page_size === 10 ? list(data.items) : data.items.slice((page - 1) * 10, page * 10);
    for (const item of items.slice(0, 10)) {
      const row = node("tr"); row.dataset.relationshipId = item.id;
      // 昵称与平台/账号合并到一列：两列拆开会让每行多占一截高度，信息也更散。
      const person = node("td", undefined, "relationship-person");
      person.append(node("span", text(item.label, t("未记录")), "relationship-name"),
        node("span", `${text(item.platform)} / ${text(item.account_id)}`, "micro"));
      const action = node("td", undefined, "relationship-actions");
      action.append(button(t("查看"), () => {
        show(item); detail.querySelector("h2")?.focus();
      }));
      if (editEnabled) action.append(button(t("编辑"), () => {
        openRowEditor(item); editor.querySelector("input")?.focus({ preventScroll: true });
        editor.scrollIntoView({ block: "nearest", behavior: "instant" });
      }));
      row.append(person, node("td", relationshipScore(item) === null ? t("未提供") : relationshipScore(item).toFixed(1)),
        node("td", stageLabel(item)), action);
      body.append(row);
    }
    table.append(body); wrapper.append(table);
    if (!items.length) wrapper.append(node("p", t("没有符合条件的关系。清空搜索或切换平台再试。"), "empty relationship-empty"));
    const pager = node("div", undefined, "pager relationship-pager");
    const previous = button(t("上一页"), () => { page--; load(); }), next = button(t("下一页"), () => { page++; load(); });
    previous.disabled = page <= 1; next.disabled = page * 10 >= data.total;
    pager.append(previous, node("span", t("第 {0} 页 · 共 {1} 人", [page, data.total])), next);
    tableRoot.append(wrapper, pager);
  }
  async function load(preserve = false) {
    if (writing) return;
    const current = ++sequence; stop(); count.textContent = t("正在读取关系…"); root.setAttribute("aria-busy", "true");
    // 查询条件在请求前交给宿主持久化：自动刷新重新挂载本面板时不会丢筛选和页码。
    onQuery?.({ platform, query, page });
    try {
      const data = graphData(await api.relationships({ ...scopeParams(selection), platform, query, page, page_size: 10, limit: NODE_CAP, graph_scope: "neighbors" }));
      if (disposed || current !== sequence) return;
      // 人格或筛选变化后旧页码可能越界：回到最后一页，避免“有结果却显示空表”。
      if (data.total === 0 && page !== 1) page = 1;
      if (!data.items.length && data.total > 0 && page > 1) {
        page = Math.max(1, Math.ceil(data.total / 10));
        await load(preserve); return;
      }
      graph = data;
      count.textContent = t("图中 {0} 人 · 列表匹配 {1} 人 · {2} 条人物关系线索", [data.nodes.length, data.total, data.peer_edges.length]) +
        (data.truncated ? t(" · 节点已截断，最多 200 人") : "");
      const nextKey = JSON.stringify([query, data.focus_ids, data.nodes.map(item => [item.id, item.score, item.label]), data.peer_edges]);
      if (nextKey !== graphKey) { await drawGraph(data, current); graphKey = nextKey; }
      else {
        const latest = new Map(data.nodes.map(item => [item.id, item]));
        for (const item of dataNodes) {
          const fresh = latest.get(item.id);
          if (!fresh) continue;
          // 备注/冻结/版本变更只更新节点资料，保持现有三轴位置和相机。
          for (const key of ["note", "frozen", "version", "sources", "source_completeness",
            "trust", "familiarity", "boundary", "stage_key", "stage_index", "stage_name"]) item[key] = fresh[key];
        }
      }
      if (disposed || current !== sequence) return;
      drawTable(data);
      if (selected) {
        const updated = [...data.nodes, ...data.items].find(item => item.id === selected.id);
        if (updated) show(updated); else hideDetail();
      }
      if (edited) {
        const updated = [...data.nodes, ...data.items].find(item => item.id === edited.id);
        if (updated) openRowEditor(updated, preserve);
        else { edited = null; editor.hidden = true; }
      }
    } catch (error) {
      if (disposed || current !== sequence) return;
      count.textContent = t("关系读取失败，不表示关系为空。"); tableRoot.replaceChildren(button(t("重试读取关系"), () => load()));
      onError(error);
    } finally { if (!disposed && current === sequence) root.setAttribute("aria-busy", "false"); }
  }
  form.addEventListener("submit", event => { event.preventDefault(); query = search.value.trim(); platform = platforms.value; page = 1; load(); });
  svg.addEventListener("wheel", event => { event.preventDefault(); zoom(event.deltaY < 0 ? 1.1 : 1 / 1.1); }, { passive: false });
  // 背景拖动旋转相机；节点本身保留三维坐标。
  let rotateStart = null;
  // 拖拽是「转视角」，不是选文本：阻止浏览器把拖动变成选区或原生拖放。
  svg.addEventListener("selectstart", event => event.preventDefault());
  svg.addEventListener("dragstart", event => event.preventDefault());
  svg.addEventListener("pointerdown", event => {
    event.preventDefault();
    rotateStart = [event.clientX, event.clientY, view.yaw, view.pitch];
    svg.setPointerCapture(event.pointerId);
  });
  svg.addEventListener("pointermove", event => {
    if (!rotateStart) return;
    view.yaw = rotateStart[2] + (event.clientX - rotateStart[0]) * .006;
    view.pitch = Math.max(-1.1, Math.min(1.1, rotateStart[3] + (event.clientY - rotateStart[1]) * .005));
    draw();
  });
  svg.addEventListener("pointerup", event => {
    if (!rotateStart) return;
    const moved = Math.hypot(event.clientX - rotateStart[0], event.clientY - rotateStart[1]);
    rotateStart = null;
    if (moved >= 4) return;   // 拖动过就是转视角，不当作点击
    // 画布用了 pointer capture，click 不会再落到节点上：这里按坐标命中。
    const hit = document.elementFromPoint(event.clientX, event.clientY)?.closest?.("[data-node-id]");
    const target = hit && dataNodes.find(item => item.id === hit.dataset.nodeId);
    if (target) show(target);
    else hideDetail();        // 点空白收起详情，不再一直挂着
  });
  svg.addEventListener("pointercancel", () => { rotateStart = null; });
  const visibility = () => { if (document.hidden) stop(); else run(); };
  const motion = () => { if (motionPreference.matches) { stop(); draw(); } else run(); };
  motionPreference.addEventListener("change", motion);
  document.addEventListener("visibilitychange", visibility);
  load();
  return () => { disposed = true; sequence++; stop(); document.removeEventListener("visibilitychange", visibility);
    motionPreference.removeEventListener("change", motion); compactViewport.removeEventListener("change", fitViewport); };
}
