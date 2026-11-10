import { t, locale } from "../i18n.mjs";
import { DIMENSIONS, unit, percent } from "../model.mjs";
import { node } from "../dom.mjs";

/**
 * 3D 情绪球（canvas 实现，无第三方库）。
 *
 * 为什么不用 three.js：页面只需要一个可拖拽的四维小球，引入 WebGL 库会增加
 * 数 MB 下载与显存占用。这里用单一 canvas + 手写投影，常驻内存只有一个
 * 位图缓冲，旋转时才重绘，静止后停止 rAF。
 *
 * 交互：按住拖拽旋转（不选中文字），双击复位；键盘左右键也可旋转。
 * 无障碍：另附数值列表，读屏与对比不依赖图像。
 */
export function radar3d(current, baseline, { label = t("TA 情绪球"), dimensions = DIMENSIONS } = {}) {
  const figure = node("figure", undefined, "radar3d-figure");
  const stage = node("div", undefined, "radar3d-stage");
  const canvas = document.createElement("canvas");
  canvas.className = "radar3d-canvas";
  canvas.setAttribute("role", "img");
  canvas.setAttribute("aria-label", label);
  canvas.tabIndex = 0;
  stage.append(canvas);
  const hint = node("p", t("拖拽旋转 · 双击复位 · 中心是当前人格"), "radar3d-hint micro");
  stage.append(hint);
  figure.append(stage);

  const keys = Object.keys(dimensions);
  const values = keys.map(key => unit(current[key]));
  const bases = keys.map(key => unit(baseline?.[key]));
  // 机器可读的数据完整度：用来证明「基准缺失时不画虚构基准」。
  figure.dataset.chart = "radar3d";
  figure.dataset.currentComplete = String(values.every(value => value !== null));
  figure.dataset.baselineComplete = String(bases.every(value => value !== null));

  const points = keys.map((_, index) => {
    const angle = index * Math.PI * 2 / keys.length - Math.PI / 2;
    return [Math.cos(angle), 0, Math.sin(angle)];
  });
  let yaw = -0.5, pitch = 0.42, dragging = false, last = null, view = null;

  const palette = () => {
    const style = getComputedStyle(document.documentElement);
    const read = (name, fallback) => (style.getPropertyValue(name) || "").trim() || fallback;
    return {
      bg: read("--surface", "#eee5d9"), line: read("--line", "#c7beb1"),
      accent: read("--accent", "#435b48"), muted: read("--muted", "#62594f"),
      text: read("--text", "#342e29"), warning: read("--warning", "#805023"),
    };
  };

  function resize() {
    const ratio = Math.min(2, window.devicePixelRatio || 1);
    const width = Math.max(240, stage.clientWidth || 320);
    const height = Math.round(Math.min(340, Math.max(240, width * 0.82)));
    canvas.width = Math.round(width * ratio);
    canvas.height = Math.round(height * ratio);
    canvas.style.width = `${width}px`;
    canvas.style.height = `${height}px`;
    const context = canvas.getContext("2d");
    context.setTransform(ratio, 0, 0, ratio, 0, 0);
    return { context, width, height };
  }

  function project([x, y, z], { width, height }) {
    const cosY = Math.cos(yaw), sinY = Math.sin(yaw);
    const x1 = x * cosY - z * sinY, z1 = x * sinY + z * cosY;
    const cosP = Math.cos(pitch), sinP = Math.sin(pitch);
    const y1 = y * cosP - z1 * sinP, z2 = y * sinP + z1 * cosP;
    const scale = Math.min(width, height) * 0.30;
    const depth = 1 / (1.9 - z2 * 0.55);
    return {
      x: width / 2 + x1 * scale * depth * 1.6,
      y: height / 2 - y1 * scale * depth * 1.6,
      depth, z: z2,
    };
  }

  function ring(context, view, tilt, steps, color, alpha) {
    context.beginPath();
    for (let step = 0; step <= steps; step++) {
      const angle = step / steps * Math.PI * 2;
      const base = [Math.cos(angle), Math.sin(angle) * Math.sin(tilt), Math.sin(angle) * Math.cos(tilt)];
      const projected = project(base, view);
      if (step === 0) context.moveTo(projected.x, projected.y);
      else context.lineTo(projected.x, projected.y);
    }
    context.strokeStyle = color;
    context.globalAlpha = alpha;
    context.stroke();
    context.globalAlpha = 1;
  }

  function draw() {
    if (!view) view = resize();
    const { context, width, height } = view;
    const colors = palette();
    context.clearRect(0, 0, width, height);

    const glow = context.createRadialGradient(width / 2, height / 2, 4, width / 2, height / 2, Math.max(width, height) * 0.46);
    glow.addColorStop(0, `${colors.accent}22`);
    glow.addColorStop(1, "transparent");
    context.fillStyle = glow;
    context.fillRect(0, 0, width, height);

    context.lineWidth = 1;
    for (const tilt of [0, Math.PI / 6, -Math.PI / 6, Math.PI / 2]) {
      ring(context, view, tilt, 64, colors.line, 0.55);
    }
    for (let step = 0; step < 8; step++) {
      context.beginPath();
      const angle = step / 8 * Math.PI * 2;
      for (let inner = 0; inner <= 24; inner++) {
        const phi = inner / 24 * Math.PI * 2;
        const base = [Math.cos(phi) * Math.cos(angle), Math.sin(phi), Math.cos(phi) * Math.sin(angle)];
        const projected = project(base, view);
        if (inner === 0) context.moveTo(projected.x, projected.y);
        else context.lineTo(projected.x, projected.y);
      }
      context.strokeStyle = colors.line;
      context.globalAlpha = 0.35;
      context.stroke();
    }
    context.globalAlpha = 1;

    const centre = project([0, 0, 0], view);

    const drawShape = (list, { stroke, fill, dotted }) => {
      const ready = list.filter(value => value !== null);
      if (ready.length < keys.length) return;
      context.beginPath();
      ready.forEach((value, index) => {
        const direction = points[index];
        const radius = 0.22 + value * 0.9;
        const projected = project([direction[0] * radius, direction[1] * radius, direction[2] * radius], view);
        if (index === 0) context.moveTo(projected.x, projected.y);
        else context.lineTo(projected.x, projected.y);
      });
      context.closePath();
      context.fillStyle = fill;
      context.fill();
      context.strokeStyle = stroke;
      context.setLineDash(dotted ? [4, 5] : []);
      context.lineWidth = dotted ? 1 : 1.8;
      context.stroke();
      context.setLineDash([]);
    };

    drawShape(bases, { stroke: `${colors.muted}88`, fill: `${colors.muted}14`, dotted: true });
    drawShape(values, { stroke: colors.accent, fill: `${colors.accent}2e`, dotted: false });

    keys.forEach((key, index) => {
      const direction = points[index];
      const value = values[index];
      const radius = value === null ? 0.22 : 0.22 + value * 0.9;
      const tip = project([direction[0] * radius, direction[1] * radius, direction[2] * radius], view);
      const labelPoint = project([direction[0] * 1.32, direction[1] * 1.32, direction[2] * 1.32], view);
      context.beginPath();
      context.moveTo(centre.x, centre.y);
      context.lineTo(tip.x, tip.y);
      context.strokeStyle = `${colors.accent}55`;
      context.lineWidth = 1;
      context.stroke();
      const raised = value !== null && bases[index] !== null && value > bases[index];
      context.beginPath();
      context.arc(tip.x, tip.y, raised ? 4.4 : 3.2, 0, Math.PI * 2);
      context.fillStyle = raised ? colors.warning : colors.accent;
      context.fill();
      context.font = `600 ${locale() === "en" ? 11 : 12}px ui-sans-serif, system-ui, sans-serif`;
      context.fillStyle = colors.text;
      context.textAlign = "center";
      context.textBaseline = "middle";
      context.globalAlpha = 0.55 + Math.min(0.45, labelPoint.depth * 0.45);
      context.fillText(
        `${dimensions[key]} ${percent(value)}`,
        Math.max(46, Math.min(width - 46, labelPoint.x)),
        Math.max(14, Math.min(height - 14, labelPoint.y)),
      );
      context.globalAlpha = 1;
    });

    context.beginPath();
    context.arc(centre.x, centre.y, 5, 0, Math.PI * 2);
    context.fillStyle = colors.accent;
    context.fill();
    context.beginPath();
    context.arc(centre.x, centre.y, 10, 0, Math.PI * 2);
    context.strokeStyle = `${colors.accent}66`;
    context.lineWidth = 1;
    context.stroke();
  }

  function schedule() {
    // 只在尺寸或交互变化时重绘；静止时不占用 rAF。
    view = resize();
    draw();
  }

  const rotate = event => {
    if (!dragging || !last) return;
    yaw += (event.clientX - last.x) * 0.010;
    pitch = Math.max(-0.9, Math.min(0.9, pitch + (event.clientY - last.y) * 0.008));
    last = { x: event.clientX, y: event.clientY };
    draw();
  };
  canvas.addEventListener("pointerdown", event => {
    dragging = true; last = { x: event.clientX, y: event.clientY };
    canvas.setPointerCapture?.(event.pointerId);
    canvas.classList.add("dragging");
    event.preventDefault();
    canvas.focus({ preventScroll: true });
  });
  canvas.addEventListener("pointermove", rotate);
  const stop = event => {
    dragging = false; last = null;
    canvas.classList.remove("dragging");
    canvas.releasePointerCapture?.(event.pointerId);
  };
  canvas.addEventListener("pointerup", stop);
  canvas.addEventListener("pointercancel", stop);
  canvas.addEventListener("dblclick", event => { event.preventDefault(); yaw = -0.5; pitch = 0.42; draw(); });
  canvas.addEventListener("keydown", event => {
    if (!["ArrowLeft", "ArrowRight", "ArrowUp", "ArrowDown"].includes(event.key)) return;
    event.preventDefault();
    if (event.key === "ArrowLeft") yaw -= 0.18;
    if (event.key === "ArrowRight") yaw += 0.18;
    if (event.key === "ArrowUp") pitch = Math.max(-0.9, pitch - 0.12);
    if (event.key === "ArrowDown") pitch = Math.min(0.9, pitch + 0.12);
    draw();
  });
  window.addEventListener("resize", schedule, { passive: true });
  window.addEventListener("livingemotion:locale", schedule);

  // 首次绘制延后一帧，等布局给出真实宽度。
  requestAnimationFrame(() => draw());

  const valuesList = node("dl", undefined, "radar3d-values");
  keys.forEach((key, index) => {
    const high = values[index] !== null && bases[index] !== null && values[index] > bases[index];
    const row = node("div", undefined, high ? "above" : "");
    row.append(node("dt", dimensions[key]),
      node("dd", percent(values[index]) + (high ? " ↑" : "")),
      node("small", t("基准 {0}", [percent(bases[index])])));
    valuesList.append(row);
  });
  figure.append(node("figcaption", undefined, "radar3d-caption"),
    node("span", t("发光面 当前 · 虚线 真实基准 · 中心点 当前人格"), "micro"), valuesList);
  if (bases.some(value => value === null)) figure.append(node("p", t("领域基准未提供，不绘制虚构基准。"), "hint"));
  figure.append(node("p", t("↑ 表示高于基准，不代表改善；压力升高同样需要留意。"), "hint"));
  return figure;
}

// 兼容旧调用名：页面里仍有 radar(...) 的写法。
export const radar = radar3d;
