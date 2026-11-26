import { node, button, svgNode } from "../dom.mjs?v=eff0d6f932b0";
import { t } from "../i18n.mjs?v=eff0d6f932b0";
import { emotionAnalysis, affectLabel, object, unit } from "../model.mjs?v=eff0d6f932b0";

const emotions = [
  ["joy", "喜悦"], ["anger", "愤怒"], ["sadness", "悲伤"],
  ["fear", "恐惧"], ["surprise", "惊讶"], ["affection", "关爱"],
  ["wronged", "委屈"], ["hurt", "受伤"], ["shyness", "害羞"],
];
const score = value => value === null ? t("未采集") : (value * 100).toFixed(1);

export function emotionSpectrum(data) {
  // 只读 TA 投影，不以对方情绪、天气诊断或缺省零值补齐缺失项。
  const raw = object(emotionAnalysis(data).bot.emotions);
  const contextual = object(data.context_emotions);
  const scoped = contextual.version === 1 && contextual.enabled === true &&
    contextual.scope_kind === "account" && contextual.context_id === data.context_id && contextual.target;
  const local = scoped ? object(contextual.emotions) : {};
  const values = emotions.map(([key, name], index) => ({
    key, name: t(name), value: unit(index < 6 ? raw[key] : local[key]),
  }));
  const ranked = values.filter(item => item.value !== null).sort((a, b) => b.value - a.value);
  const strongest = ranked[0];
  const root = node("section", undefined, "ta-emotions");
  root.dataset.emotionSpectrum = "";
  root.dataset.updatedAt = String(data.updated_at ?? "");
  root.setAttribute("aria-label", t("TA 当前情绪分布"));
  const grid = node("div", undefined, "ta-emotion-grid");
  const summary = node("div", undefined, "ta-emotion-summary");
  const glyph = svgNode("svg", { viewBox: "0 0 9 9", class: "ta-pixel-glyph",
    "aria-hidden": "true", "shape-rendering": "crispEdges" });
  // 抽象情绪符号不额外推断某种情绪；状态名称始终使用运行时标签。
  glyph.append(svgNode("path", { fill: "currentColor",
    d: "M2 2h1v2H2zM6 2h1v2H6zM2 6h1v1H2zM3 7h3v1H3zM6 6h1v1H6z" }));
  summary.append(node("p", t("此刻状态"), "ta-emotion-eyebrow"), glyph,
    node("h2", affectLabel(object(data.bot_state).label, t("未采集")), "ta-emotion-word"));
  const strength = node("div", undefined, "ta-emotion-strength");
  strength.append(node("span", strongest ? `${t("最强")} · ${strongest.name}` : t("最强分量")),
    node("strong", strongest ? score(strongest.value) : t("未采集")));
  if (strongest) strength.append(node("span", "/ 100", "ta-emotion-unit"));
  summary.append(strength);
  const companions = node("div", undefined, "ta-emotion-companions");
  if (ranked.length > 1) companions.append(node("span", t("其他分量"), "ta-emotion-eyebrow"));
  for (const item of ranked.slice(1, 3)) {
    const row = node("div");
    row.append(node("span", item.name), node("span", score(item.value), "ta-emotion-number"));
    companions.append(row);
  }
  summary.append(companions);
  const distribution = node("div", undefined, "ta-emotion-distribution");
  const heading = node("div", undefined, "ta-emotion-heading");
  heading.append(node("strong", t("情绪分布")), node("span", t("独立强度 · 0–100")));
  const paper = node("div", undefined, "ta-emotion-paper");
  for (const value of [100, 50, 0]) {
    const line = node("div", undefined, "ta-emotion-scale");
    line.style.top = `${(100 - value) * 2}px`;
    line.append(node("span", value));
    paper.append(line);
  }
  const stems = node("div", undefined, "ta-emotion-stems");
  const pixel = node("div", undefined, "ta-emotion-pixel");
  const inspection = node("p", t("实线为已采集 · 虚线为未采集"), "ta-emotion-inspection");
  inspection.setAttribute("aria-live", "polite");
  for (const item of values) {
    const text = item.value === null ? `${item.name} · ${t("未采集")}`
      : `${item.name} · ${score(item.value)} / 100`;
    const bind = row => {
      row.dataset.emotion = item.key;
      row.dataset.value = item.value === null ? "uncollected" : String(item.value);
      row.classList.toggle("missing", item.value === null);
      // 仅强调最大分量，保持运行时状态标签，不在前端添加主导阈值。
      row.classList.toggle("strongest", item.value !== null && item.value > 0 && item.value === strongest?.value);
      row.setAttribute("aria-label", text);
      const show = () => { inspection.textContent = text; };
      const clear = () => { inspection.textContent = t("实线为已采集 · 虚线为未采集"); };
      row.addEventListener("pointerenter", show);
      row.addEventListener("pointerleave", clear);
      row.addEventListener("focus", show);
      row.addEventListener("blur", clear);
    };
    const stemButton = button(item.name, () => { inspection.textContent = text; }, "ta-emotion-stem-button");
    stemButton.replaceChildren();
    const stem = node("span", undefined, "ta-emotion-stem");
    const fill = node("span", undefined, "ta-emotion-fill");
    fill.style.setProperty("--strength", item.value ?? 0);
    const number = node("span", score(item.value), "ta-emotion-stem-number");
    number.style.bottom = `${(item.value ?? 0) * 200 + 9}px`;
    stem.append(fill, number);
    stemButton.append(stem, node("span", item.name, "ta-emotion-stem-label"));
    bind(stemButton); stems.append(stemButton);
    const pixelRow = button(item.name, () => { inspection.textContent = text; }, "ta-emotion-pixel-row");
    const cells = node("span", undefined, "ta-emotion-cells");
    cells.setAttribute("aria-hidden", "true");
    for (let i = 0; i < 20; i++) {
      const cell = node("span", undefined, "ta-emotion-cell");
      const filled = node("b");
      filled.style.setProperty("--filled", item.value === null ? 0 : Math.max(0, Math.min(1, item.value * 20 - i)));
      cell.append(filled); cells.append(cell);
    }
    pixelRow.replaceChildren(node("span", item.name), cells, node("span", score(item.value), "ta-emotion-pixel-number"));
    bind(pixelRow); pixel.append(pixelRow);
  }
  paper.append(stems);
  distribution.append(heading, paper, pixel, inspection);
  grid.append(summary, distribution);
  root.append(grid);
  const scopeNote = node("p", contextual.enabled === true
    ? scoped ? (contextual.dimension === "user"
        ? t("委屈、受伤与害羞：对 {0}，各群与私聊通用", [contextual.target])
        : t("委屈、受伤与害羞：当前会话对象 {0}", [contextual.target]))
      : t("委屈、受伤与害羞按对象采集；选择具体会话后查看。")
    : t("在设置 → 情绪开启「委屈、受伤与害羞」并保存后采集。"), "hint");
  scopeNote.dataset.contextEmotionScope = "";
  root.append(scopeNote);
  if (contextual.enabled === true && data.mode === "observe_only") {
    root.append(node("p", t("仅观察模式不新增这三项采集；在设置 → 快速开始将运行模式改为参与中后生效。"), "hint"));
  }
  return root;
}
