import { t, locale, controlled, resource } from "../i18n.mjs";
import { node, button, labelled, svgNode } from "../dom.mjs";
import { object, list, text, date, scopeParams, energyValue, NIGHT_STATES } from "../model.mjs";
export const ENERGY_KINDS = resource({
  reply: t("回复消耗"), fatigue: t("疲劳消耗"), recovery: t("恢复"), sleep: t("入睡"), wake: t("唤醒"), manual: t("手动"), config: t("配置"),
});
const seconds = value => typeof value === "number" ? value : Date.parse(value) / 1000;
export function energyPoints(raw) {
  const data = object(raw);
  if (data.api_version !== 1 || !Array.isArray(data.points) || !Array.isArray(data.items) ||
      data.page_size !== 10 || !Number.isSafeInteger(data.total) || data.total < 0 || data.items.length > 10) {
    throw Object.assign(new Error(t("精力日志响应不符合管理契约。")), { code: "invalid_response" });
  }
  try { new Intl.DateTimeFormat(locale(), { timeZone: data.timezone || "UTC" }); }
  catch (_) { throw Object.assign(new Error(t("精力日志时区无效，未推测事件时间。")), { code: "invalid_response" }); }
  return { ...data, from: data.window_start, to: data.window_end, points: data.points.filter(point => Number.isFinite(seconds(point.at ?? point.created_at)) &&
    energyValue(point.energy ?? point.after_energy) !== null).slice(0, 1440) };
}
export function energyChart(data, options = {}) {
  // 清醒线：精力到这条线就算睡够，正常自主参与。画成横向虚线，和 25/50/75 网格区分开。
  const comfort = Number.isFinite(Number(options.comfort)) ? Math.max(0, Math.min(100, Number(options.comfort))) : null;
  const figure = node("figure", undefined, "energy-figure");
  const svg = svgNode("svg", { viewBox: "0 0 720 240", class: "energy-chart", role: "img", "aria-label": t("最近24小时真实精力时间线，精力上限100，逐事件数值见下表") });
  const start = seconds(data.from), end = seconds(data.to);
  const validWindow = Number.isFinite(start) && Number.isFinite(end) && end > start;
  for (const value of [0, 25, 50, 75, 100]) {
    const y = 204 - value * 1.8;
    svg.append(svgNode("line", { x1: 36, y1: y, x2: 708, y2: y, class: "grid" }),
      svgNode("text", { x: 30, y: y + 4, "text-anchor": "end" }, value));
  }
  if (comfort !== null) {
    const y = 204 - comfort * 1.8;
    svg.append(svgNode("line", { x1: 36, y1: y, x2: 708, y2: y, class: "energy-threshold" }),
      svgNode("text", { x: 712, y: y + 4, "text-anchor": "start", class: "energy-threshold-label" },
        t("清醒线 {0}", [comfort])));
  }
  if (validWindow) {
    for (let i = 0; i <= 4; i++) {
      const at = start + (end - start) * i / 4;
      svg.append(svgNode("text", { x: 36 + 672 * i / 4, y: 228, "text-anchor": i === 0 ? "start" : i === 4 ? "end" : "middle" },
        new Intl.DateTimeFormat(locale(), { hour: "2-digit", minute: "2-digit", hour12: false, timeZone: data.timezone || "UTC" }).format(new Date(at * 1000))));
    }
    const series = new Map();
    for (const point of data.points.slice().sort((a, b) => seconds(a.at ?? a.created_at) - seconds(b.at ?? b.created_at))) {
      const at = seconds(point.at ?? point.created_at), value = point.energy ?? point.after_energy;
      if (at < start || at > end) continue;
      const x = 36 + (at - start) / (end - start) * 672, y = 204 - value * 1.8;
      const key = point.owner_key ?? "";
      const path = series.get(key) || "";
      series.set(key, `${path}${path ? "L" : "M"}${x},${y} `);
      if (energyValue(point.min) !== null && energyValue(point.max) !== null) {
        svg.append(svgNode("line", { x1: x, x2: x, y1: 204 - point.max * 1.8, y2: 204 - point.min * 1.8, class: "energy-range" }));
      }
      svg.append(svgNode("circle", { cx: x, cy: y, r: 2 }));
    }
    for (const [key, path] of series) svg.append(svgNode("path", { d: path, class: "energy-line", "data-series": key }));
  }
  figure.append(svg, node("figcaption", data.points.length && validWindow ?
    t("真实时点 · {0} 至 {1} · 时区 {2} · 上限 100{3} · 竖线保留显示桶极值", [date(data.from, data.timezone || "UTC"), date(data.to, data.timezone || "UTC"), text(data.timezone, "UTC"), data.series_total > 1 ? t(" · 各状态所有者分别连线，不合并精力") : ""]) :
    t("最近24小时未采集精力历史，不补造连续曲线。"), "hint"));
  // 只有算得出清醒线时才补这句解释；append(null) 会插入字面量 "null"。
  if (comfort !== null) {
    figure.append(node("p",
      t("虚线是清醒线 {0}：在线以上算睡够，可正常自主参与；掉到线以下又在夜里被叫醒，才需要唤醒窗口。", [comfort]), "hint"));
  }
  return figure;
}
export function mountEnergy(root, { api, selection, onError, comfort }) {
  let disposed = false, sequence = 0, page = 1;
  const form = node("form", undefined, "record-toolbar");
  const kind = node("select"); kind.id = "energy-kind"; const all = node("option", t("全部事件")); all.value = ""; kind.append(all);
  for (const [value, title] of Object.entries(ENERGY_KINDS)) { const option = node("option", title); option.value = value; kind.append(option); }
  const submit = node("button", t("筛选日志")); submit.type = "submit";
  form.append(labelled(t("事件类型"), kind), submit);
  const body = node("div"); body.id = "energy-body"; body.setAttribute("aria-live", "polite");
  root.append(node("h2", t("最近 24 小时")), node("p", t("曲线和逐事件表来自同一持久日志；没有采集的历史保持空白。"), "hint"), form, body);
  async function load() {
    const current = ++sequence; body.setAttribute("aria-busy", "true"); body.replaceChildren(node("p", t("正在读取精力日志…"), "empty"));
    try {
      const data = energyPoints(await api.energy({ ...scopeParams(selection), ...(kind.value ? { event_type: kind.value } : {}), page, page_size: 10 }));
      if (disposed || current !== sequence) return;
      body.replaceChildren(energyChart(data, { comfort }));
      const wrapper = node("div", undefined, "table-wrap"), table = node("table"), head = node("thead"), tr = node("tr");
      wrapper.tabIndex = 0; wrapper.setAttribute("role", "region"); wrapper.setAttribute("aria-label", t("精力事件表，可左右滚动；每页10条"));
      for (const title of [t("时点"), t("事件 / 状态"), t("前 → 后"), t("变化"), t("原因")]) { const th = node("th", title); th.scope = "col"; tr.append(th); }
      head.append(tr); table.append(head); const tbody = node("tbody");
      for (const item of list(data.items).slice(0, 10)) {
        const row = node("tr"); row.dataset.energyId = text(item.id, "");
        const before = energyValue(item.before_energy), after = energyValue(item.after_energy);
        row.append(node("td", date(item.at ?? item.created_at, data.timezone || "UTC")),
          node("td", `${ENERGY_KINDS[item.kind] || text(item.kind)} / ${NIGHT_STATES[item.after_state ?? item.after_display_state] || text(item.after_state ?? item.after_display_state)}`),
          node("td", `${before === null ? t("未提供") : before.toFixed(1)} → ${after === null ? t("未提供") : after.toFixed(1)}`),
          node("td", typeof item.delta === "number" && Number.isFinite(item.delta) ? `${item.delta > 0 ? "+" : ""}${item.delta.toFixed(1)}` : t("未提供")),
          node("td", text(item.reason ?? item.reason_code)));
        tbody.append(row);
      }
      table.append(tbody); wrapper.append(table); body.append(wrapper);
      if (!data.items.length) body.append(node("p", t("当前筛选暂无精力事件。旧历史未采集，不代表精力为零。"), "empty"));
      const pager = node("div", undefined, "pager");
      const previous = button(t("上一页"), () => { page--; load(); }), next = button(t("下一页"), () => { page++; load(); });
      previous.disabled = page <= 1; next.disabled = page * 10 >= data.total;
      pager.append(previous, node("span", t("第 {0} 页 · 共 {1} 条 · 每页 10 条", [page, data.total])), next); body.append(pager);
    } catch (error) {
      if (disposed || current !== sequence) return;
      body.replaceChildren(node("p", t("精力日志读取失败，不表示没有历史。"), "error-text"), button(t("重试读取日志"), load)); onError(error);
    } finally { if (!disposed && current === sequence) body.setAttribute("aria-busy", "false"); }
  }
  form.addEventListener("submit", event => { event.preventDefault(); page = 1; load(); }); load();
  return () => { disposed = true; sequence++; };
}
