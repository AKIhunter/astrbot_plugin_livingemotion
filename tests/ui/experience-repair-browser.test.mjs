/* Isolated synthetic host bridge, blocked external traffic, real production UI. */
import assert from "node:assert/strict";
import { createRequire } from "node:module";
import { mkdir, writeFile } from "node:fs/promises";
import { startServer } from "./server.mjs";
const { chromium } = createRequire(import.meta.url)("playwright");
const { server, url } = await startServer();
const output = "/tmp/livingemotion-experience-repair-20261113";
await mkdir(output, { recursive: true });
const browser = await chromium.launch({ headless: true });
const report = { cases: [], errors: [], external: [] };
let currentPage;
try {
  for (const width of [1280, 390]) for (const colorScheme of ["light", "dark"]) {
    const context = await browser.newContext({ viewport: { width, height: 900 }, colorScheme });
    const page = await context.newPage();
    currentPage = page;
    page.on("pageerror", e => report.errors.push(e.message));
    await page.route("**/*", route => {
      if (new URL(route.request().url()).origin === new URL(url).origin) return route.continue();
      report.external.push(route.request().url()); return route.abort();
    });
    await page.addInitScript(() => {
      const interval = window.setInterval;
      window.setInterval = (fn, delay, ...args) =>
        interval(fn, delay === 60000 ? 2000 : delay, ...args);
      let wrapped;
      window.__repairState = { failed: true };
      Object.defineProperty(window, "AstrBotPluginView", {
        configurable: true,
        get: () => wrapped,
        set: bridge => {
          const get = bridge.apiGet.bind(bridge);
          wrapped = { ...bridge, async apiGet(path, params) {
            const result = await get(path, params);
            if (path === "console/state") {
              result.data.experience.automatic = {
                diary: { status: window.__repairState.failed ? "failed" : "created",
                  reason_code: window.__repairState.failed ? "model_preflight_http_error" : "",
                  http_status: window.__repairState.failed ? 503 : 200, day: "2026-11-13" },
                dream: { status: "idle" },
              };
            }
            if (path === "console/records" && ["diary", "dream"].includes(params.kind)) {
              result.data.items = [
                { id: "repair-new", date: "2026-11-13", created_at: 1794528000,
                  title: params.kind === "diary" ? "把这一点温柔留到夜里" : "",
                  emotion_snapshot: { at: 1794528000, label: "关爱", emotions: { affection: .8 } },
                  body: "日期：2026-11-13\n天气：晴\n\n" + "我在一盏小灯旁留住了今天的心情。".repeat(10) },
                { id: "repair-old", date: "2026-11-12", created_at: 1794441600,
                  body: "旧记录保留原正文，不补造标题或情绪。" },
              ];
              result.data.total = 2;
            }
            return result;
          } };
        },
      });
    });
    await page.goto(`${url}?scenario=normal`);
    await page.locator("#content[aria-busy=false]").waitFor();
    await page.locator('[data-section="experience"]').click();
    await page.getByRole("tab", { name: "日记", exact: true }).click();
    const diary = page.locator('[data-experience-records="diary"]');
    await diary.locator(".paper-sheet").first().waitFor();
    assert.equal(await diary.locator("h3").first().textContent(), "2026-11-13");
    assert.equal(await diary.locator(".paper-meta time").first().textContent(), "星期五");
    assert.equal(await diary.locator(".paper-title").textContent(), "把这一点温柔留到夜里");
    assert.equal(await diary.locator(".paper-meta span").first().textContent(), "晴");
    assert.match(await page.locator('[data-automatic-task="diary"]').textContent(), /503/);
    await diary.locator("summary").first().click();
    await page.screenshot({ path: `${output}/diary-${width}-${colorScheme}.png`, fullPage: true });
    await page.getByRole("tab", { name: "梦境", exact: true }).click();
    const dream = page.locator('[data-experience-records="dream"]');
    await dream.locator(".paper-sheet").first().waitFor();
    assert.equal(await dream.locator("h3").first().textContent(), "2026-11-13");
    assert.equal(await dream.locator(".paper-meta time").first().textContent(), "星期五");
    assert.equal(await dream.locator(".paper-emotion").textContent(), "关爱");
    assert.equal(await dream.locator('[data-record-id="repair-old"] .paper-emotion').count(), 0);
    await dream.locator("summary").first().click();
    await page.screenshot({ path: `${output}/dream-${width}-${colorScheme}.png`, fullPage: true });
    assert.equal(await page.evaluate(() => document.documentElement.scrollWidth <= innerWidth + 1), true);
    await page.evaluate(() => { window.__repairState.failed = false; document.activeElement.blur(); });
    await page.waitForFunction(() => document.querySelector('[data-automatic-task="diary"]')?.textContent.includes("200"));
    assert.equal(await dream.locator(".paper-emotion").textContent(), "关爱");
    assert.equal(await page.evaluate(() => window.__fixture.calls.filter(c =>
      c.path === "console/experience-generate").length), 0);
    await page.emulateMedia({ reducedMotion: "reduce" });
    await page.getByRole("tab", { name: "日记", exact: true }).click();
    assert.equal(await page.evaluate(() => document.getAnimations().length), 0);
    report.cases.push({ width, colorScheme, header: "date / weekday / title / saved emotion",
      oldEntries: "no invented fields", autoRefresh: "updated without click", passed: true });
    await context.close();
  }
  assert.deepEqual(report.errors, []);
  assert.deepEqual(report.external, []);
  report.success = true;
} catch (error) {
  report.success = false; report.failure = error.stack; process.exitCode = 1;
  if (currentPage && !currentPage.isClosed()) {
    report.visible = await currentPage.locator("#notice, #record-body, #diary-record-body").allTextContents();
    report.calls = await currentPage.evaluate(() => window.__fixture?.calls.slice(-12).map(c => c.path));
    await currentPage.screenshot({ path: `${output}/failure.png`, fullPage: true });
  }
} finally {
  await writeFile(`${output}/report.json`, JSON.stringify(report, null, 2));
  console.log(JSON.stringify(report));
  await browser.close(); server.close();
}
