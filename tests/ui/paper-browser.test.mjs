/* Real Console DTO with synthetic numeric storage; no model or external sends. */
import assert from "node:assert/strict";
import { createRequire } from "node:module";
import { writeFile } from "node:fs/promises";
import { startServer } from "./server.mjs";
import { nativeDTO } from "./native-dto.mjs";
const { chromium } = createRequire(import.meta.url)("playwright");
const { server, url } = await startServer();
const browser = await chromium.launch({ headless: true });
const report = { scope: "real Console DTO / temporary synthetic states", cases: [], errors: [] };
try {
  assert.equal(nativeDTO.state.emotion_curve.points.length, 288);
  assert.ok(nativeDTO.state.emotion_curve.points.every(p => p.emotions !== null));
  for (const width of [1280, 390]) for (const colorScheme of ["light", "dark"]) {
    const context = await browser.newContext({ viewport: { width, height: 1000 }, colorScheme });
    const page = await context.newPage();
    page.on("pageerror", e => report.errors.push(e.message));
    await page.goto(`${url}?scenario=native-dto`);
    await page.locator("#content[aria-busy=false]").waitFor();
    assert.equal(await page.locator('[data-section="emotion"]').count(), 0);
    assert.equal(await page.locator("#scope, #context, #change-reason").count(), 0);
    const chart = page.locator(".emotion-chart");
    assert.equal(await chart.locator("[data-emotion-line]").count(), 6);
    for (const d of await chart.locator("[data-emotion-line]").evaluateAll(els => els.map(el => el.getAttribute("d"))))
      assert.ok(d.includes("L") && !d.includes("NaN"));
    await chart.hover({ position: { x: 100, y: 60 } });
    assert.equal(await page.locator(".emotion-tooltip span").count(), 7);
    assert.equal(await page.locator(".emotion-tooltip").textContent().then(s => s.includes("未采集")), false);
    await chart.focus();
    await page.keyboard.press("End");
    const end = await page.locator(".emotion-tooltip").textContent();
    await page.keyboard.press("ArrowLeft");
    assert.notEqual(await page.locator(".emotion-tooltip").textContent(), end);
    await page.keyboard.press("Home");
    await page.screenshot({ path: `/tmp/livingemotion-paper-20261109/ta-${width}-${colorScheme}.png`, fullPage: true });
    await page.locator('[data-section="experience"]').click();
    await page.locator("#record-body[aria-busy=false]").waitFor();
    await page.getByRole("tab", { name: "设置", exact: true }).click();
    const pool = page.locator("#config-dream_theme_pool");
    assert.equal(await pool.evaluate(el => el.tagName), "TEXTAREA");
    await pool.fill("赛博朋克\n绿野仙踪\n生活日常");
    await page.locator("#save").click();
    assert.equal(await page.locator("#editor").isVisible(), false);
    const save = await page.evaluate(() => window.__fixture.calls.find(c => c.path === "console/config"));
    assert.ok(save.payload.expected_revision);
    assert.equal(save.payload.reason, "控制台保存配置");
    await page.getByRole("tab", { name: "日记", exact: true }).click();
    const paper = page.locator(".paper-sheet").first();
    await paper.locator("summary").click();
    assert.equal(await paper.getAttribute("open"), "");
    assert.ok((await paper.locator(".paper-body").textContent()).length > 10);
    assert.equal(await page.locator("#record-body [data-pin-entry], #record-body article button").count(), 0);
    assert.ok(!/素材来源|上下文来源|置顶/.test(await page.locator("#record-body").textContent()));
    await page.screenshot({ path: `/tmp/livingemotion-paper-20261109/paper-${width}-${colorScheme}.png`, fullPage: true });
    await page.getByRole("tab", { name: "梦境", exact: true }).click();
    assert.equal(await page.locator(".paper-meta span").count(), 0);
    assert.equal(await page.evaluate(() => document.documentElement.scrollWidth <= innerWidth + 1), true);
    report.cases.push({ width, colorScheme, curve: "6 lines / 288 slots / hover + keyboard",
      editing: "save without reason; CAS retained", paper: "readable; no pins or sources", passed: true });
    await context.close();
  }
  assert.deepEqual(report.errors, []);
  report.success = true;
} catch (error) { report.success = false; report.failure = error.stack; process.exitCode = 1; }
finally {
  await writeFile("/tmp/livingemotion-paper-20261109/paper-ui-report.json", JSON.stringify(report, null, 2));
  console.log(JSON.stringify(report));
  await browser.close(); server.close();
}
