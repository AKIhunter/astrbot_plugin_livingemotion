/* Synthetic host only: no platform send or paid provider calls. */
import assert from "node:assert/strict";
import { createRequire } from "node:module";
import fs from "node:fs/promises";
import { startServer } from "./server.mjs";
const { chromium } = createRequire(import.meta.url)("playwright");
const folder = process.env.LIVINGEMOTION_BEHAVIOR_OUTPUT || "/tmp/livingemotion-behavior-console-20261110";
const { server, url } = await startServer();
const browser = await chromium.launch({ headless: true });
const report = { success: false, cases: [], errors: [] };
try {
  for (const width of [1440, 390, 320]) {
    const page = await browser.newPage({ viewport: { width, height: 1100 }, reducedMotion: "reduce" });
    page.on("pageerror", error => report.errors.push(error.message));
    await page.clock.install();
    await page.goto(`${url}?scenario=native-dto`);
    await page.locator("#content[aria-busy=false]").waitFor();
    // TA 页底部：六维说明默认收起，点开后每行都有可展开的人话问号。
    const explainer = page.locator("details[data-emotion-explainer]");
    assert.equal(await explainer.count(), 1);
    assert.equal(await explainer.getAttribute("open"), null);
    await explainer.locator("summary").click();
    assert.equal(await explainer.getAttribute("open"), "");
    assert.equal(await explainer.locator("tbody tr").count(), 19);
    const help = explainer.locator(".help-button").first();
    await help.click();
    assert.equal(await help.getAttribute("aria-expanded"), "true");
    assert.equal(await explainer.locator(".help-text").first().isVisible(), true);
    // 自动刷新或切页签都会重建 TA 页 DOM：展开状态必须保留，不能被自动收起。
    await page.locator("[data-section=persona]").click();
    await page.locator("[data-section=overview]").click();
    const restored = page.locator("details[data-emotion-explainer]");
    assert.equal(await restored.getAttribute("open"), "");
    assert.equal(await restored.locator(".help-button").first().getAttribute("aria-expanded"), "true");
    assert.equal(await restored.locator(".help-text").first().isVisible(), true);
    await page.evaluate(() => {
      const bridge = window.AstrBotPluginView;
      const get = bridge.apiGet, post = bridge.apiPost;
      window.__behavior = { gets: [], posts: [], rows: [
        { id: "manual:unique-recoverable-id", send_id: "manual:unique-recoverable-id", target_label: "QQ号",
          target_id: "12345678", content: "真实发送的正文", replied: true, simulated: false, created_at: 1794315600,
          timestamp: 1794315603, emotion_snapshot: "happy,excited" },
        { id: "legacy-id", send_id: "legacy-id", target_label: "QQ号", target_id: "12345678",
          content: "旧日志的正文", replied: false, created_at: 1794315500 },
      ] };
      bridge.apiGet = async (path, params) => {
        if (path !== "console/records" || params.kind !== "behavior") return get(path, params);
        window.__behavior.gets.push({ ...params });
        const rows = window.__behavior.rows.filter(row => !params.query || JSON.stringify(row).includes(params.query));
        return { api_version: 1, items: rows.slice((params.page - 1) * 10, params.page * 10),
          total: rows.length, page: params.page, page_size: 10 };
      };
      bridge.apiPost = async (path, payload) => {
        window.__behavior.posts.push({ path, payload });
        if (path !== "console/behavior-simulate") return post(path, payload);
        const label = { joy: "喜悦", anger: "愤怒", current: "当前情绪" }[payload.emotion];
        window.__behavior.rows.unshift({ id: payload.request_id, send_id: payload.request_id,
          content: `这是${label}时说的话。`, replied: false, simulated: true, emotion_label: label,
          status: "completed", created_at: 1794315700 });
        return { api_version: 1, status: "completed", sends: 0, model_calls: 1 };
      };
    });
    await page.locator("[data-section=behavior]").click();
    await page.getByText("真实发送的正文", { exact: true }).waitFor();
    assert.equal(await page.locator("#behavior-panel .block").count(), 3);
    // 真实发送必须常驻在主动行为页最上方；是否可点由当前范围决定。
    assert.equal(await page.locator("#behavior-real-send").isVisible(), true);
    const realSend = page.locator("#behavior-real-send [data-operation='behavior.send']");
    assert.equal(await realSend.isVisible(), true);
    assert.equal(await page.locator("#records").isVisible(), false);
    assert.deepEqual(await page.locator(".behavior-log-table th").allTextContents(),
      ["时间", "发送 ID", "当时情绪", "目标 ID（QQ号）", "发送内容", "是否回应"]);
    const real = page.locator('[data-send-id="manual:unique-recoverable-id"]');
    assert.equal(await real.locator("time").textContent(), new Intl.DateTimeFormat("zh-CN", {
      year: "numeric", month: "2-digit", day: "2-digit", hour: "2-digit",
      minute: "2-digit", second: "2-digit", hour12: false, timeZone: "Asia/Shanghai",
    }).format(new Date(1794315603000)));
    assert.equal(await real.locator("td").nth(2).textContent(), "开心、兴奋");
    assert.equal(await real.locator("td").nth(3).textContent(), "QQ号 12345678");
    assert.equal(await page.locator('[data-send-id="legacy-id"] td').nth(2).textContent(), "未记录");
    assert.equal(await page.locator("#behavior-outcome").getByText("true", { exact: true }).count(), 1);
    assert.equal(await page.getByRole("button", { name: "刷新最近执行", exact: true }).count(), 0);
    // Query starts automatically and remains in the exact same input across refresh.
    await page.locator("#behavior-log-query").fill("12345678");
    await page.clock.runFor(251);
    await page.waitForFunction(() => window.__behavior.gets.at(-1).query === "12345678");
    await page.locator("#behavior-log-query").focus();
    await page.clock.runFor(5001);
    assert.equal(await page.locator("#behavior-log-query").inputValue(), "12345678");
    assert.equal(await page.evaluate(() => document.activeElement.id), "behavior-log-query");
    await page.locator("#behavior-log-query").fill("");
    await page.clock.runFor(251);
    await page.locator("[data-operation='behavior.simulate']").click();
    assert.equal(await page.locator("#simulation-emotion").inputValue(), "current");
    await page.locator("#simulation-emotion").selectOption("joy");
    await page.clock.runFor(60001);
    assert.equal(await page.locator("#simulation-emotion").inputValue(), "joy");
    await page.locator("#behavior-simulation-dialog").getByRole("button", { name: "生成", exact: true }).click();
    await page.getByText("这是喜悦时说的话。", { exact: true }).waitFor();
    await page.locator("[data-operation='behavior.simulate']").click();
    await page.locator("#simulation-emotion").selectOption("anger");
    await page.locator("#behavior-simulation-dialog").getByRole("button", { name: "生成", exact: true }).click();
    await page.getByText("这是愤怒时说的话。", { exact: true }).waitFor();
    const simulated = page.locator(".behavior-log-table tr").filter({ hasText: "这是愤怒时说的话。" });
    assert.equal(await simulated.locator("td").nth(2).textContent(), "愤怒");
    assert.equal(await simulated.locator("td").nth(3).textContent(), "模拟");
    assert.equal(await page.evaluate(() => window.__behavior.posts.length), 2);
    assert.equal(await page.evaluate(() => window.__behavior.posts.every(p => p.path === "console/behavior-simulate")), true);
    assert.equal(await page.evaluate(() => new Set(window.__behavior.posts.map(p => p.payload.request_id)).size), 2);
    // New rows appear automatically without a button, including while query input has focus.
    await page.evaluate(() => window.__behavior.rows.unshift({ id: "automatic-new-id", send_id: "automatic-new-id",
      target_label: "QQ群号", target_id: "87654321", content: "自动出现的新日志", replied: false, created_at: 1794315800 }));
    await page.clock.runFor(5001);
    await page.getByText("自动出现的新日志", { exact: true }).waitFor();
    assert.equal(await page.evaluate(() => document.documentElement.scrollWidth <= innerWidth + 1), true);
    await page.locator("body").screenshot({ path: `${folder}/fixture-${width}.png` });
    const reads = await page.evaluate(() => window.__behavior.gets.length);
    await page.evaluate(() => Object.defineProperty(document, "hidden", { configurable: true, value: true }));
    await page.clock.runFor(60001);
    assert.equal(await page.evaluate(() => window.__behavior.gets.length), reads);
    report.cases.push({ width, six_columns: true, timestamp_seconds_timezone: true, historical_emotion: true,
      missing_emotion_not_fabricated: true, target_qq: true, simulation_has_no_target: true,
      automatic_query: true, retained_query_focus: true,
      automatic_new_logs: true, selectable_emotion: true, zero_real_sends: true, no_overflow: true });
    await page.close();
  }
  assert.deepEqual(report.errors, []);
  report.success = true;
} catch (error) { report.failure = error.stack; process.exitCode = 1; }
finally {
  await fs.writeFile(`${folder}/fixture-report.json`, JSON.stringify(report, null, 2));
  console.log(JSON.stringify(report)); await browser.close(); server.close();
}
