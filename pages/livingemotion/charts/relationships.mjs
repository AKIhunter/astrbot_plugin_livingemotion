import { node, button, svgNode, labelled } from "../dom.mjs";
import { object, list, text, percent, scopeParams } from "../model.mjs";
import { pageError } from "../api.mjs";
export const NODE_CAP = 200;
export function relationshipScore(item) {
  const value = item.score;
  return typeof value === "number" && Number.isFinite(value) && value >= 0 && value <= 100 ? value : null;
}
export function graphData(raw) {
  const data = object(raw);
  if (data.api_version !== 1 || !Array.isArray(data.nodes) || !Array.isArray(data.items) ||
      data.page_size !== 10 || !Number.isSafeInteger(data.total) || data.total < 0 || data.items.length > 10 ||
      data.items.some(item => !item || typeof item.id !== "string" || !item.platform || !item.account_id)) {
    throw Object.assign(new Error("关系响应不符合管理契约。"), { code: "invalid_response" });
  }
  const nodes = data.nodes.filter(item => item && typeof item.id === "string" && item.platform && item.account_id);
  const seen = new Set();
  const unique = nodes.filter(item => !seen.has(item.id) && seen.add(item.id));
  return { ...data, nodes: unique.slice(0, NODE_CAP), items: Array.isArray(data.items) ? data.items : unique };
}
export function mountRelationships(root, { api, selection, persona, canWrite, onError, uncertain = new Set() }) {
  let disposed = false, sequence = 0, simulation = null, timer = null, selected = null, writing = false;
  let page = 1, query = "", platform = selection.context_id ? selection.platform || "" : "", paused = false, scale = 1, pan = [0, 0], version = null, conflict = false;
  const writeKey = item => `relationship:${selection.persona_id}/${item.platform}/${item.account_id}`;
  const form = node("form", undefined, "record-toolbar");
  const search = node("input"); search.type = "search"; search.id = "relationship-query"; search.maxLength = 200; search.placeholder = "平台账号或昵称";
  const platforms = node("select"); platforms.id = "relationship-platform";
  platforms.append(node("option", "全部平台")); platforms.firstChild.value = "";
  for (const item of list(selection.platforms)) {
    const option = node("option", text(item.label ?? item)); option.value = text(item.value ?? item.id ?? item, "");
    if (selection.context_id && selection.platform && option.value !== selection.platform) option.disabled = true;
    platforms.append(option);
  }
  platforms.value = platform;
  const submit = node("button", "查找关系"); submit.type = "submit";
  form.append(labelled("平台", platforms), labelled("账号搜索 · 包含未绘制节点", search), submit);
  const count = node("p", "正在读取关系…", "hint");
  const device = node("div", undefined, "graph-device");
  const svg = svgNode("svg", { viewBox: "0 0 720 420", class: "relationship-graph", "aria-label": "人格中心二维关系图，可使用表格选择账号" });
  const world = svgNode("g"); svg.append(world);
  const actions = node("div", undefined, "graph-actions");
  const pause = button("暂停布局", () => {
    paused = !paused; pause.textContent = paused ? "继续布局" : "暂停布局";
    pause.setAttribute("aria-pressed", String(paused));
    if (paused) simulation?.stop(); else run();
  });
  pause.setAttribute("aria-pressed", "false");
  const transform = () => world.setAttribute("transform", `translate(${pan[0]} ${pan[1]}) translate(360 210) scale(${scale}) translate(-360 -210)`);
  const zoom = factor => { scale = Math.max(.6, Math.min(2.5, scale * factor)); transform(); };
  actions.append(pause, button("放大", () => zoom(1.2)), button("缩小", () => zoom(1 / 1.2)),
    button("复位视图", () => { scale = 1; pan = [0, 0]; transform(); }));
  const tableRoot = node("div"), detail = node("section", undefined, "graph-detail"); detail.hidden = true;
  detail.setAttribute("aria-label", "选中账号详情");
  device.append(svg, actions); root.append(form, count, device, tableRoot, detail);
  let draw = () => {};
  function stop() { simulation?.stop(); clearTimeout(timer); svg.dataset.layout = "stopped"; }
  function run() {
    stop();
    if (!simulation || paused || disposed || document.hidden) return;
    if (matchMedia("(prefers-reduced-motion: reduce)").matches) { simulation.tick(180); draw(); return; }
    simulation.alpha(.45).restart();
    svg.dataset.layout = "running";
    timer = setTimeout(stop, 2000);
  }
  function show(item, preserve = false) {
    const retained = preserve ? { affinity: detail.querySelector("#relationship-affinity")?.value,
      reason: detail.querySelector("#relationship-reason")?.value, frozen: detail.querySelector("#relationship-frozen")?.checked } : null;
    if (writing) return;
    selected = item; version = item.version; conflict = false;
    detail.replaceChildren(); detail.hidden = false;
    detail.append(node("h2", `${text(item.platform)} / ${text(item.account_id)}`), node("p", text(item.label, "未记录昵称"), "hint"));
    detail.querySelector("h2").tabIndex = -1;
    const dl = node("dl", undefined, "key-values");
    for (const [label, value] of [
      ["亲近阶段", text(item.stage, "未建立")], ["好感", relationshipScore(item) === null ? "未提供" : relationshipScore(item).toFixed(1)],
      ["熟悉", item.familiarity === null ? "未建立" : percent(item.familiarity)],
      ["信任", item.trust === null ? "未建立" : percent(item.trust)],
      ["边界", item.boundary === null ? "未建立" : percent(item.boundary)],
      ["来源完整性", text(item.source_completeness, "未提供")], ["版本", text(item.version)],
    ]) dl.append(node("dt", label), node("dd", value));
    detail.append(dl);
    const sources = node("details"); sources.append(node("summary", "真实来源会话"));
    const sourceBody = node("div", undefined, "details-content");
    for (const source of list(item.sources)) sourceBody.append(node("p",
      `${text(source.platform)} / ${text(source.view_scope)} / ${text(source.scene_id)} · ${text(source.context_id)}`, "micro"));
    if (!sourceBody.childElementCount) sourceBody.append(node("p", "未提供来源会话，不推测关系维度。", "hint"));
    sources.append(sourceBody); detail.append(sources);
    const edit = node("form", undefined, "relationship-edit");
    const score = node("input"); score.type = "number"; score.id = "relationship-affinity"; score.min = "0"; score.max = "100"; score.step = ".1";
    score.required = true; score.value = retained?.affinity ?? (relationshipScore(item) === null ? "" : String(relationshipScore(item)));
    const reason = node("input"); reason.id = "relationship-reason"; reason.required = true; reason.maxLength = 300; reason.value = retained?.reason || "";
    const frozen = node("input"); frozen.id = "relationship-frozen"; frozen.type = "checkbox"; frozen.checked = retained?.frozen ?? item.frozen === true;
    const error = node("p", undefined, "error-text"); error.setAttribute("role", "alert");
    const save = node("button", "保存此账号好感"); save.type = "submit"; save.className = "primary";
    const refresh = button("读取最新关系并复核", async () => {
      const draft = { affinity: score.value, reason: reason.value, frozen: frozen.checked };
      await load(true);
      const newScore = detail.querySelector("#relationship-affinity"), newReason = detail.querySelector("#relationship-reason");
      if (newScore) newScore.value = draft.affinity;
      if (newReason) newReason.value = draft.reason;
      const newFrozen = detail.querySelector("#relationship-frozen");
      if (newFrozen) newFrozen.checked = draft.frozen;
    });
    refresh.hidden = true;
    const validVersion = () => Number.isSafeInteger(version) && version >= 0;
    save.disabled = !canWrite() || !validVersion() || uncertain.has(writeKey(item));
    edit.append(labelled("好感 · 0–100，步进 0.1", score), labelled("冻结自动好感变化", frozen), labelled("修改原因（必填）", reason), error, node("p",
      "只修改当前人格的这个平台账号。操作者由宿主认证注入，不修改其他平台的同号账号。", "hint"));
    const row = node("div", undefined, "button-row"); row.append(save, refresh); edit.append(row); detail.append(edit);
    edit.addEventListener("submit", async event => {
      event.preventDefault();
      if (save.disabled || writing || !canWrite() || !validVersion() || conflict || !edit.reportValidity()) return;
      const affinity = Number(score.value);
      if (!Number.isFinite(affinity) || affinity < 0 || affinity > 100 || Math.abs(affinity * 10 - Math.round(affinity * 10)) > 1e-7 || !reason.value.trim()) return;
      save.disabled = true; writing = true; error.textContent = "";
      try {
        await api.relationship({ persona_id: selection.persona_id,
          ...(selection.context_id ? { context_id: selection.context_id } : {}),
          platform: item.platform, account_id: item.account_id,
          score: affinity, frozen: frozen.checked, expected_version: version, reason: reason.value.trim() });
        if (disposed) return;
        writing = false;
        count.textContent = "好感已保存，正在重新读取真实关系。";
        await load();
      } catch (errorValue) {
        if (disposed) return;
        const failure = pageError(errorValue);
        if (failure.code === "version_conflict") {
          conflict = true; refresh.hidden = false; error.textContent = "关系版本已变化。草稿保留，请读取最新关系并人工复核；未自动重试。";
        } else {
          if (["timeout", "bridge_error", "invalid_response", "unavailable"].includes(failure.code)) uncertain.add(writeKey(item));
          error.textContent = `${failure.message}。${uncertain.has(writeKey(item)) ? "结果不明，已禁止重复提交。" : "未保存。"} `;
          onError(errorValue);
        }
      } finally { writing = false; if (!disposed) save.disabled = conflict || uncertain.has(writeKey(item)) || !canWrite(); }
    });
    world.querySelectorAll("[data-node-id]").forEach(element => element.classList.toggle("selected", element.dataset.nodeId === item.id));
  }
  async function drawGraph(data, current) {
    stop(); world.replaceChildren();
    const { forceSimulation, forceManyBody, forceLink, forceCollide, forceRadial } = await import("../vendor/d3-force.mjs");
    if (disposed || current !== sequence) return;
    let seed = 42;
    const random = () => ((seed = Math.imul(1664525, seed) + 1013904223 >>> 0) / 4294967296);
    const center = { id: "__persona__", x: 360, y: 210, fx: 360, fy: 210 };
    const nodes = data.nodes.map((item, i) => {
      const angle = i * 2.399963;
      return { ...item, x: 360 + Math.cos(angle) * (60 + i * .4), y: 210 + Math.sin(angle) * (60 + i * .4) };
    });
    const edges = list(data.edges).filter(edge => nodes.some(item => item.id === edge.target))
      .map(edge => ({ source: "__persona__", target: edge.target }));
    const lines = edges.map(edge => {
      const item = nodes.find(n => n.id === edge.target), affinity = relationshipScore(item) ?? 0;
      const line = svgNode("line", { class: "graph-edge", "stroke-width": 1 + affinity / 30 }); world.append(line); return line;
    });
    const circles = nodes.map(item => {
      const group = svgNode("g");
      const circle = svgNode("circle", { r: 9, tabindex: 0, role: "button", class: "graph-person",
        "data-node-id": item.id, "aria-label": `${item.platform} ${item.account_id}，好感 ${relationshipScore(item) ?? "未提供"}` });
      circle.append(svgNode("title", {}, `${text(item.label, "")} ${item.platform}/${item.account_id}`));
      circle.addEventListener("click", () => show(item));
      circle.addEventListener("keydown", event => { if (event.key === "Enter" || event.key === " ") { event.preventDefault(); show(item); } });
      let drag = false;
      circle.addEventListener("pointerdown", event => {
        event.stopPropagation(); drag = true; circle.setPointerCapture(event.pointerId); item.fx = item.x; item.fy = item.y;
      });
      circle.addEventListener("pointermove", event => {
        if (!drag) return;
        const point = svg.createSVGPoint(); point.x = event.clientX; point.y = event.clientY;
        const local = point.matrixTransform(world.getScreenCTM().inverse());
        item.fx = item.x = local.x; item.fy = item.y = local.y; draw();
      });
      const release = () => { drag = false; item.fx = null; item.fy = null; if (!paused) run(); };
      circle.addEventListener("pointerup", release); circle.addEventListener("pointercancel", release);
      group.append(circle); world.append(group); return group;
    });
    const centerGroup = svgNode("g");
    centerGroup.append(svgNode("circle", { cx: 360, cy: 210, r: 29, class: "graph-center" }),
      svgNode("text", { x: 360, y: 214, "text-anchor": "middle", class: "center-label" }, text(persona.name, "人格").slice(0, 6)));
    world.append(centerGroup);
    simulation = forceSimulation([center, ...nodes]).randomSource(random).stop()
      .force("charge", forceManyBody().strength(-18)).force("collision", forceCollide(13))
      .force("relation", forceLink(edges).id(item => item.id).distance(edge => 48 + (100 - (relationshipScore(edge.target) ?? 0)) * 1.2).strength(.4))
      .force("radius", forceRadial(item => item === center ? 0 : 48 + (100 - (relationshipScore(item) ?? 0)) * 1.2, 360, 210).strength(.25));
    draw = () => {
      nodes.forEach((item, i) => {
        item.x = Math.max(20, Math.min(700, item.x)); item.y = Math.max(20, Math.min(400, item.y));
        circles[i].setAttribute("transform", `translate(${item.x} ${item.y})`);
      });
      edges.forEach((edge, i) => {
        for (const [key, value] of Object.entries({ x1: edge.source.x, y1: edge.source.y, x2: edge.target.x, y2: edge.target.y })) lines[i].setAttribute(key, value);
      });
    };
    simulation.on("tick", draw); simulation.tick(100); draw(); transform(); run();
  }
  function drawTable(data) {
    tableRoot.replaceChildren();
    const wrapper = node("div", undefined, "table-wrap"), table = node("table"), head = node("thead"), tr = node("tr");
    wrapper.tabIndex = 0; wrapper.setAttribute("role", "region"); wrapper.setAttribute("aria-label", "关系表，可左右滚动；每页10条");
    table.className = "relationship-table";
    for (const title of ["平台 / 账号", "昵称", "好感", "亲近阶段", "详情"]) { const th = node("th", title); th.scope = "col"; tr.append(th); }
    head.append(tr); table.append(head);
    const body = node("tbody");
    const items = data.page_size === 10 ? list(data.items) : data.items.slice((page - 1) * 10, page * 10);
    for (const item of items.slice(0, 10)) {
      const row = node("tr"); row.dataset.relationshipId = item.id;
      const action = node("td"); action.append(button("查看 / 修改", () => {
        show(item); detail.querySelector("h2")?.focus();
      }));
      row.append(node("td", `${text(item.platform)} / ${text(item.account_id)}`), node("td", text(item.label, "未记录")),
        node("td", relationshipScore(item) === null ? "未提供" : relationshipScore(item).toFixed(1)), node("td", text(item.stage, "未建立")), action);
      body.append(row);
    }
    table.append(body); wrapper.append(table);
    if (!items.length) wrapper.append(node("p", "当前范围暂无符合条件的关系。可以清空搜索或切换平台。", "empty"));
    const pager = node("div", undefined, "pager");
    const previous = button("上一页", () => { page--; load(); }), next = button("下一页", () => { page++; load(); });
    previous.disabled = page <= 1; next.disabled = page * 10 >= data.total;
    pager.append(previous, node("span", `第 ${page} 页 · 共 ${data.total} 人 · 每页 10 条`), next);
    tableRoot.append(wrapper, pager);
  }
  async function load(preserve = false) {
    if (writing) return;
    const current = ++sequence; stop(); count.textContent = "正在读取关系…"; root.setAttribute("aria-busy", "true");
    try {
      const data = graphData(await api.relationships({ ...scopeParams(selection), platform, query, page, page_size: 10, limit: NODE_CAP }));
      if (disposed || current !== sequence) return;
      count.textContent = `已展示 ${data.nodes.length} / ${data.total} 人 · 仅记录人格→账号的真实关系 · 距离与线宽表达好感`;
      await drawGraph(data, current);
      if (disposed || current !== sequence) return;
      drawTable(data);
      if (selected) {
        const updated = [...data.nodes, ...data.items].find(item => item.id === selected.id);
        if (updated) show(updated, preserve); else { selected = null; detail.hidden = true; detail.replaceChildren(); }
      }
    } catch (error) {
      if (disposed || current !== sequence) return;
      count.textContent = "关系读取失败，不表示关系为空。"; tableRoot.replaceChildren(button("重试读取关系", () => load()));
      onError(error);
    } finally { if (!disposed && current === sequence) root.setAttribute("aria-busy", "false"); }
  }
  form.addEventListener("submit", event => { event.preventDefault(); query = search.value.trim(); platform = platforms.value; page = 1; load(); });
  svg.addEventListener("wheel", event => { event.preventDefault(); zoom(event.deltaY < 0 ? 1.1 : 1 / 1.1); }, { passive: false });
  let panStart = null;
  svg.addEventListener("pointerdown", event => {
    panStart = [event.clientX, event.clientY, ...pan]; svg.setPointerCapture(event.pointerId);
  });
  svg.addEventListener("pointermove", event => {
    if (!panStart) return;
    const rect = svg.getBoundingClientRect();
    pan = [panStart[2] + (event.clientX - panStart[0]) * 720 / rect.width, panStart[3] + (event.clientY - panStart[1]) * 420 / rect.height]; transform();
  });
  svg.addEventListener("pointerup", () => { panStart = null; }); svg.addEventListener("pointercancel", () => { panStart = null; });
  const visibility = () => { if (document.hidden) stop(); else run(); };
  document.addEventListener("visibilitychange", visibility);
  load();
  return () => { disposed = true; sequence++; stop(); document.removeEventListener("visibilitychange", visibility); };
}
