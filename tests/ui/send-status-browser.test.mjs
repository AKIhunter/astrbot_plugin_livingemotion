/* Real production UI, virtual browser time, synthetic bridge and no external traffic. */
import assert from "node:assert/strict";
import { createRequire } from "node:module";
import { mkdir, writeFile } from "node:fs/promises";
import { startServer } from "./server.mjs";
const { chromium } = createRequire(import.meta.url)("playwright");
const output = "/tmp/le-send-status-ui-20261114";
await mkdir(output, { recursive: true });
const { server, url } = await startServer();
const browser = await chromium.launch({ headless: true });
const report = { cases: [], errors: [], external: [] };
try {
  for (const width of [1440, 390, 320]) {
    const page = await browser.newPage({ viewport: { width, height: 1100 }, reducedMotion: "reduce" });
    page.on("pageerror", error => report.errors.push(error.message));
    await page.route("**/*", route => {
      if (new URL(route.request().url()).origin === new URL(url).origin) return route.continue();
      report.external.push(route.request().url()); return route.abort();
    });
    await page.clock.install();
    await page.addInitScript(() => {
      let wrapped;
      window.__sendStatus = { confirmed: 2, rows: [
        { id: "confirmed", status: "succeeded", target_label: "QQ号", target_id: "12345678",
          created_at: 1794315600, timestamp: 1794315603, emotion_snapshot: "happy,excited",
          content: "已经确认的正文", replied: true },
        { id: "unknown", status: "unknown", target_label: "QQ号", target_id: "12345678",
          created_at: 1794315500, emotion_snapshot: "calm", content: "未知结果仍保留正文", replied: false },
        { id: "legacy", status: "cancelled", created_at: 1794315400, target_id: "12345678" },
      ] };
      Object.defineProperty(window, "AstrBotPluginView", {
        configurable: true, get: () => wrapped,
        set: bridge => {
          const get = bridge.apiGet.bind(bridge);
          wrapped = { ...bridge, async apiGet(path, params) {
            if (path === "console/records" && params.kind === "behavior") {
              const rows = window.__sendStatus.rows.filter(row =>
                !params.query || JSON.stringify(row).includes(params.query));
              return { api_version: 1, items: rows, total: rows.length, page: 1, page_size: 10,
                send_daily_limit: 6, send_statistics: { global: {
                  consumed: 6, confirmed: window.__sendStatus.confirmed, unknown: 1,
                  cancelled: 1, failed: 1, in_progress: 1,
                } } };
            }
            const result = await get(path, params);
            if (path === "console/state") {
              (result.data || result).behavior.send_statistics = { global: {
                consumed: 6, confirmed: window.__sendStatus.confirmed, unknown: 1,
                cancelled: 1, failed: 1, in_progress: 1,
              } };
              (result.data || result).emotion_curve = { timezone: "Asia/Shanghai", points: [
                { at: 1794315600, emotions: { joy: .2 }, basis: "legacy_baseline_unknown" },
              ] };
            }
            return result;
          } };
        },
      });
    });
    await page.goto(`${url}?scenario=native-dto`);
    await page.locator("#content[aria-busy=false]").waitFor();
    await page.getByText("旧样本未记录情绪基准，部分历史曲线按默认基准推算。", { exact: true }).waitFor();
    await page.locator("[data-section=behavior]").click();
    await page.getByText("已经确认的正文", { exact: true }).waitFor();
    assert.deepEqual(await page.locator(".behavior-log-table th").allTextContents(),
      ["时间", "发送 ID", "当时情绪", "目标 ID（QQ号）", "发送内容", "是否回应"]);
    assert.equal(await page.locator('[data-send-id="confirmed"]').getByText("平台已确认", { exact: true }).count(), 1);
    assert.equal(await page.locator('[data-send-id="unknown"]').getByText("结果未知", { exact: true }).count(), 1);
    assert.equal(await page.locator('[data-send-id="legacy"] td').nth(2).textContent(), "未记录");
    await page.getByText("今日额度占用 6/6 · 平台确认 2 · 未知 1 · 取消 1 · 失败 1 · 处理中 1", { exact: true }).waitFor();
    assert.match(await page.locator('[data-send-id="confirmed"] time').textContent(), /:03$/);
    await page.locator("#behavior-log-query").fill("12345678");
    await page.clock.runFor(251);
    await page.locator("#behavior-log-query").focus();
    await page.evaluate(() => {
      window.__sendStatus.confirmed = 3;
      window.__sendStatus.rows.unshift({ id: "new", status: "unknown", content: "自动刷新的正文",
        target_id: "12345678", created_at: 1794315700, emotion_snapshot: "happy" });
    });
    await page.clock.runFor(60001);
    await page.getByText("自动刷新的正文", { exact: true }).waitFor();
    await page.getByText("今日额度占用 6/6 · 平台确认 3 · 未知 1 · 取消 1 · 失败 1 · 处理中 1", { exact: true }).waitFor();
    assert.equal(await page.locator("#behavior-log-query").inputValue(), "12345678");
    assert.equal(await page.evaluate(() => document.activeElement.id), "behavior-log-query");
    assert.equal(await page.evaluate(() => document.documentElement.scrollWidth <= innerWidth + 1), true);
    assert.equal(await page.evaluate(() => window.__fixture.calls.filter(c =>
      c.path === "console/action" || c.path === "console/behavior-simulate").length), 0);
    await page.screenshot({ path: `${output}/${width}.png`, fullPage: true });
    report.cases.push({ width, sixColumns: true, quotaAndConfirmationSeparate: true,
      unknownRetainsBody: true, noInventedHistoricalEmotion: true,
      historicalBaselineGapVisible: true,
      automaticRefresh: true, retainedQueryFocus: true, noOverflow: true, zeroRealSends: true });
    await page.close();
  }
  assert.deepEqual(report.errors, []);
  assert.deepEqual(report.external, []);
  report.success = true;
} catch (error) {
  report.success = false; report.failure = error.stack; process.exitCode = 1;
} finally {
  await writeFile(`${output}/report.json`, JSON.stringify(report, null, 2));
  console.log(JSON.stringify(report));
  await browser.close(); server.close();
}
