import { node, svgNode } from "../dom.mjs";
import { t, locale } from "../i18n.mjs";
import { EMOTIONS, object, list, unit } from "../model.mjs";

const colors = ["#bc7b18", "#c14c58", "#6482bb", "#8c63af", "#268d92", "#bc668c"];
export function emotionChart(raw) {
  const data = object(raw), points = list(data.points).slice(0, 288);
  const figure = node("figure", undefined, "emotion-figure");
  figure.dataset.emotionCurve = "";
  const heading = node("h2", t("近 24 小时情绪"));
  const tooltip = node("div", undefined, "emotion-tooltip");
  tooltip.setAttribute("role", "status"); tooltip.setAttribute("aria-live", "polite");
  const svg = svgNode("svg", { viewBox: "0 0 800 250", class: "emotion-chart",
    role: "img", tabindex: 0, "aria-label": t("六维情绪折线图；左右方向键查看每5分钟的数据") });
  const keys = Object.keys(EMOTIONS);
  const time = at => new Intl.DateTimeFormat(locale(), { timeZone: data.timezone || "UTC",
    month: "2-digit", day: "2-digit", hour: "2-digit", minute: "2-digit", hour12: false }).format(new Date(at * 1000));
  for (const value of [0, 25, 50, 75, 100]) {
    const y = 214 - value * 1.9;
    svg.append(svgNode("line", { x1: 42, x2: 785, y1: y, y2: y, class: "grid" }),
      svgNode("text", { x: 35, y: y + 4, "text-anchor": "end" }, `${value}%`));
  }
  const xAt = index => 42 + index / Math.max(1, points.length - 1) * 743;
  for (const [index, key] of keys.entries()) {
    let path = "", connected = false;
    points.forEach((point, i) => {
      const value = unit(object(point.emotions)[key]);
      if (value === null) { connected = false; return; }
      path += `${connected ? "L" : "M"}${xAt(i).toFixed(2)},${(214 - value * 190).toFixed(2)} `;
      connected = true;
    });
    svg.append(svgNode("path", { d: path, fill: "none", stroke: colors[index],
      "stroke-width": 2, "data-emotion-line": key }));
  }
  if (points.length) {
    for (const index of [0, 72, 144, 216, points.length - 1].filter(i => i < points.length)) {
      svg.append(svgNode("text", { x: xAt(index), y: 242,
        "text-anchor": index === 0 ? "start" : index === points.length - 1 ? "end" : "middle" },
        time(points[index].at).split(" ").at(-1)));
    }
  }
  const cursor = svgNode("line", { y1: 20, y2: 214, class: "emotion-cursor", visibility: "hidden" });
  svg.append(cursor);
  const legend = node("div", undefined, "emotion-legend");
  keys.forEach((key, i) => {
    const label = node("span", EMOTIONS[key]); label.style.setProperty("--line-color", colors[i]); legend.append(label);
  });
  let selected = Math.max(0, points.length - 1);
  const show = index => {
    if (!points.length) return;
    selected = Math.max(0, Math.min(points.length - 1, index));
    const point = points[selected], x = xAt(selected);
    cursor.setAttribute("x1", x); cursor.setAttribute("x2", x); cursor.setAttribute("visibility", "visible");
    tooltip.replaceChildren(node("span", time(point.at), "micro"));
    keys.forEach((key, i) => {
      const value = unit(object(point.emotions)[key]);
      const row = node("span", `${EMOTIONS[key]} ${value === null ? t("未采集") : `${Math.round(value * 100)}%`}`);
      row.style.setProperty("--line-color", colors[i]); tooltip.append(row);
    });
  };
  svg.addEventListener("pointermove", event => {
    const rect = svg.getBoundingClientRect();
    show(Math.round(((event.clientX - rect.left) / rect.width * 800 - 42) / 743 * (points.length - 1)));
  });
  svg.addEventListener("focus", () => show(selected));
  svg.addEventListener("keydown", event => {
    if (!["ArrowLeft", "ArrowRight", "Home", "End"].includes(event.key)) return;
    event.preventDefault();
    show(event.key === "Home" ? 0 : event.key === "End" ? points.length - 1 : selected + (event.key === "ArrowRight" ? 1 : -1));
  });
  figure.append(heading, legend, svg, tooltip, node("figcaption",
    t("每 5 分钟 · 根据真实状态与自然回落计算，含当日天气加成；未采集时段留空。"), "hint"));
  return figure;
}
