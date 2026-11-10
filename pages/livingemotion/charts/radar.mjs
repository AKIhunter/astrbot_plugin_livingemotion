import { t, locale, controlled } from "../i18n.mjs";
import { DIMENSIONS, unit, percent } from "../model.mjs";
import { node, svgNode } from "../dom.mjs";
export function radar(current, baseline) {
  const figure = node("figure", undefined, "radar-figure");
  const keys = Object.keys(DIMENSIONS), c = keys.map(key => unit(current[key])), b = keys.map(key => unit(baseline[key]));
  const svg = svgNode("svg", { viewBox: "0 0 360 300", role: "img", "aria-label": t("TA 四维情绪雷达，实线为当前，虚线为领域基准；数值见下方") });
  const point = (i, value) => [180 + Math.sin(i * Math.PI / 2) * 98 * value, 150 - Math.cos(i * Math.PI / 2) * 98 * value];
  for (const level of [.25, .5, .75, 1]) svg.append(svgNode("polygon", {
    points: keys.map((_, i) => point(i, level).join(",")).join(" "), class: "radar-grid",
  }));
  keys.forEach((key, i) => {
    const [x, y] = point(i, 1), [lx, ly] = point(i, 1.35);
    svg.append(svgNode("line", { x1: 180, y1: 150, x2: x, y2: y, class: "radar-grid" }),
      svgNode("text", { x: lx, y: ly + 5, "text-anchor": "middle", class: "radar-label" }, DIMENSIONS[key]));
  });
  if (b.every(value => value !== null)) svg.append(svgNode("polygon", {
    points: b.map((value, i) => point(i, value).join(",")).join(" "), class: "radar-baseline",
  }));
  if (c.every(value => value !== null)) {
    svg.append(svgNode("polygon", { points: c.map((value, i) => point(i, value).join(",")).join(" "), class: "radar-current" }));
    c.forEach((value, i) => {
      const [cx, cy] = point(i, value), high = b[i] !== null && value > b[i];
      svg.append(svgNode("circle", { cx, cy, r: high ? 5 : 3,
        class: `radar-point${high ? " above" : ""}${high && keys[i] === "stress" ? " pressure-high" : ""}` }));
    });
  } else svg.append(svgNode("text", { x: 180, y: 154, "text-anchor": "middle", class: "radar-label" }, t("当前维度未完整采集")));
  const caption = node("figcaption");
  caption.append(node("span", t("实线 当前 · 虚线 真实基准"), "micro"));
  const values = node("dl", undefined, "radar-values");
  keys.forEach((key, i) => {
    const high = c[i] !== null && b[i] !== null && c[i] > b[i];
    const row = node("div", undefined, high ? `above${key === "stress" ? " pressure-high" : ""}` : "");
    row.append(node("dt", DIMENSIONS[key]), node("dd", `${percent(c[i])}${c[i] !== null && b[i] !== null && c[i] > b[i] ? " ↑" : ""}`),
      node("small", t("基准 {0}", [percent(b[i])])));
    values.append(row);
  });
  caption.append(values);
  if (!b.every(value => value !== null)) caption.append(node("p", t("领域基准未提供，不绘制虚构基准。"), "hint"));
  caption.append(node("p", t("↑ 表示高于基准，不代表改善；压力升高同样需要留意。"), "hint"));
  figure.append(svg, caption); return figure;
}
