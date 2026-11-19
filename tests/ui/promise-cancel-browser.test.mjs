/* Synthetic bridge only; exercise actual UI clicks and automatic readback. */
import assert from "node:assert/strict";
import { createRequire } from "node:module";
import { mkdir, writeFile } from "node:fs/promises";
import os from "node:os";
import path from "node:path";
import { startServer } from "./server.mjs";
const require = createRequire(import.meta.url);
const { chromium } = require(process.env.PLAYWRIGHT_MODULE || "playwright");
const evidenceDir = process.env.UI_EVIDENCE_DIR || path.join(os.tmpdir(), "le-promise-cancel-ui");
await mkdir(evidenceDir, { recursive: true });
const { server, url } = await startServer();
const browser = await chromium.launch({ headless: true, executablePath: process.env.CHROME_EXECUTABLE });
const report = { success: false, cases: [], errors: [] };
try {
  for (const width of [1280, 390]) {
    const page = await browser.newPage({ viewport: { width, height: 1000 }, reducedMotion: "reduce" });
    page.on("pageerror", error => report.errors.push(error.message));
    await page.goto(`${url}?scenario=native-dto`);
    await page.locator("#content[aria-busy=false]").waitFor();
    const initialWidth = await page.evaluate(() => document.documentElement.scrollWidth);
    // Only the fixture's host data is changed; production DOM and event handlers are untouched.
    await page.evaluate(() => {
      const bridge = window.AstrBotPluginView, get = bridge.apiGet;
      const base = window.__fixture.state;
      const target = base.action_target.context_id;
      window.__promises = { cancelled: false, posts: [], reads: 0 };
      const make = () => ({ enabled: true, total: window.__promises.cancelled ? 1 : 2, items: [
        ...(!window.__promises.cancelled ? [{
          promise_id: "unknown-task", status: "unknown", description: "待核对的窗边猫",
          reason: "result_unknown", context_id: target, can_cancel: true,
          created_at: 1795000000, due_at: 1795000300, original_due_at: 1795000300,
          waiting_deadline: 1795086400, retry_count: 0, retry_limit: 3,
        }] : []),
        { promise_id: "running-task", status: "running", description: "正在生成的花园猫",
          context_id: target, can_cancel: false, created_at: 1795000000,
          due_at: 1795000300, original_due_at: 1795000300 },
      ] });
      window.__fixture.setPromises(make());
      bridge.apiGet = async (path, params) => {
        const result = await get(path, params);
        if (path === "console/state") {
          (result.data || result).behavior.promises = make();
          window.__promises.reads++;
        }
        if (path === "console/records") (result.data || result).promises = make();
        return result;
      };
      bridge.apiPost = async (path, payload) => {
        window.__promises.posts.push({ path, payload });
        if (path !== "console/action" || payload.action !== "promise.cancel") throw Error("Unexpected write");
        window.__promises.cancelled = true;
        return { api_version: 1, status: "cancelled", model_calls: 0, sends: 0 };
      };
    });
    await page.locator("[data-section=behavior]").click();
    const waiting = page.locator('[data-promise-id="unknown-task"].promise-card');
    await waiting.locator("summary").click();
    const cancel = waiting.getByRole("button", { name: "取消后续处理" });
    await cancel.waitFor();
    assert.equal(await cancel.isEnabled(), true);
    const running = page.locator('[data-promise-id="running-task"].promise-card');
    await running.locator("summary").click();
    assert.equal(await running.getByRole("button", { name: "取消后续处理" }).isEnabled(), false);
    await cancel.click();
    await waiting.waitFor({ state: "detached" });
    const evidence = await page.evaluate(() => window.__promises);
    assert.equal(evidence.posts.length, 1);
    assert.equal(evidence.posts[0].payload.promise_id, "unknown-task");
    assert.ok(evidence.reads >= 1);
    // The host page has a fixed minimum width; cancellation must not widen it.
    const finalWidth = await page.evaluate(() => document.documentElement.scrollWidth);
    assert.ok(finalWidth <= initialWidth + 1);
    report.cases.push({ width, initialWidth, finalWidth, unknown_cancelled: true,
      running_disabled: true, automatic_readback: true });
    await page.close();
  }
  assert.deepEqual(report.errors, []);
  report.success = true;
} catch (error) { report.failure = error.stack; process.exitCode = 1; }
finally {
  await writeFile(path.join(evidenceDir, "promise-cancel.json"), JSON.stringify(report, null, 2));
  console.log(JSON.stringify(report)); await browser.close(); await new Promise(resolve => server.close(resolve));
}
