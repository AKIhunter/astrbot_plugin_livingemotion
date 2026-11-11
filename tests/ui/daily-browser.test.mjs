/* Stateful synthetic UI checks. Model/storage claims require native acceptance. */
import assert from "node:assert/strict";
import { createRequire } from "node:module";
import { writeFile } from "node:fs/promises";
import { startServer } from "./server.mjs";
const require = createRequire(import.meta.url);
const { chromium } = require(process.env.PLAYWRIGHT_MODULE || "playwright");
const { server, url } = await startServer();
const browser = await chromium.launch({ headless: true, executablePath: process.env.CHROME_PATH });
const report = { scope: "stateful synthetic bridge; no paid model", cases: [], errors: [], external: [] };
try {
  for (const width of [1280, 390]) for (const colorScheme of ["light", "dark"]) {
    const context = await browser.newContext({ viewport: { width, height: 900 }, colorScheme });
    const page = await context.newPage();
    page.on("pageerror", e => report.errors.push(e.message));
    await page.route("**/*", route => {
      if (new URL(route.request().url()).origin === new URL(url).origin) return route.continue();
      report.external.push(route.request().url()); return route.abort();
    });
    await page.goto(`${url}?scenario=daily`);
    await page.locator("#content[aria-busy=false]").waitFor();
    await page.locator('[data-section="experience"]').click();
    await page.locator("#record-body[aria-busy=false]").waitFor();
    assert.deepEqual(await page.getByRole("tab").allTextContents(), ["设置", "日记", "梦境"]);
    await page.getByRole("tab", { name: "日记", exact: true }).focus();
    await page.keyboard.press("Home");
    assert.equal(await page.getByRole("tab", { selected: true }).textContent(), "设置");
    assert.equal(await page.locator("#settings").isVisible(), true);
    assert.equal(await page.locator("[data-operation$='.generate']:visible").count(), 0);
    await page.locator("#config-diary_enabled").check();
    await page.getByRole("tab", { name: "梦境", exact: true }).click();
    assert.equal(await page.locator("[data-operation$='.generate']:visible").count(), 1);
    const motion = await page.evaluate(() => document.getAnimations().filter(a =>
      a.effect?.target?.id !== "radar-canvas").map(a => a.effect.getTiming().duration));
    assert.ok(motion.includes(140));
    assert.equal(await page.locator(".experience-tab-indicator").evaluate(el => getComputedStyle(el).transitionDuration), ".28s".replace(/^\./, "0."));
    assert.equal(await page.locator(".experience-tabs").evaluate(el => getComputedStyle(el).display), "grid");
    await page.locator("#record-body[aria-busy=false]").waitFor();
    const baseline = await page.locator("#experience-panel").boundingBox();
    const reads = await page.evaluate(() => window.__fixture.calls.filter(c => c.path === "console/records").length);
    for (let index = 0; index < 20; index++) {
      await page.getByRole("tab", { name: ["设置", "日记", "梦境"][index % 3], exact: true }).click();
      await page.locator("#experience-panel").evaluate(book => book.getBoundingClientRect().height);
      const box = await page.locator("#experience-panel").boundingBox();
      for (const dimension of ["x", "y", "width", "height"]) assert.ok(Math.abs(box[dimension] - baseline[dimension]) < 1);
    }
    assert.equal(await page.evaluate(() => window.__fixture.calls.filter(c => c.path === "console/records").length), reads);
    await page.waitForFunction(() => {
      const tab = document.querySelector('.experience-tabs [aria-selected="true"]').getBoundingClientRect();
      const indicator = document.querySelector(".experience-tab-indicator").getBoundingClientRect();
      return Math.abs(tab.x - indicator.x) < 1 && Math.abs(tab.width - indicator.width) < 1;
    });
    await page.getByRole("tab", { name: "设置", exact: true }).click();
    assert.equal(await page.locator("#config-diary_enabled").isChecked(), true);
    await page.locator("#discard").click();
    assert.equal(await page.locator("#config-diary_enabled").isChecked(), false);
    await page.getByRole("tab", { name: "日记", exact: true }).click();
    const heading = page.locator("#record-body article").first().locator("details").first();
    await heading.locator("summary").click();
    const reading = page.locator("#experience-panel-diary");
    await reading.evaluate(panel => panel.scrollTop = 100);
    const scroll = await reading.evaluate(panel => panel.scrollTop);
    await page.getByRole("tab", { name: "梦境", exact: true }).click();
    await page.getByRole("tab", { name: "日记", exact: true }).click();
    assert.equal(await heading.getAttribute("open"), "");
    assert.equal(await reading.evaluate(panel => panel.scrollTop), scroll);
    await page.locator("#refresh").click();
    assert.equal(await page.getByRole("tab", { selected: true }).textContent(), "日记");
    assert.equal(await page.locator('[data-operation="diary.generate"]').isEnabled(), true);
    await page.locator('[data-operation="diary.generate"]').click();
    await page.locator("#refresh").click();
    const generationBox = await page.locator("#experience-panel").boundingBox();
    const generationScroll = await page.evaluate(() => ({ x: scrollX, y: scrollY, busy: document.querySelector("#content").getAttribute("aria-busy") }));
    await page.waitForFunction(() => document.querySelector('[data-record-id="daily-diary"] details[open]'));
    const generatedBox = await page.locator("#experience-panel").boundingBox();
    for (const dimension of ["x", "y", "width", "height"]) assert.ok(Math.abs(generatedBox[dimension] - generationBox[dimension]) < 1,
      JSON.stringify({ dimension, generationBox, generatedBox, generationScroll,
        after: await page.evaluate(() => ({ x: scrollX, y: scrollY, busy: document.querySelector("#content").getAttribute("aria-busy") })) }));
    assert.equal(await page.evaluate(() => window.__fixture.calls.filter(c =>
      c.path === "console/experience-generate").length), 1);
    await page.locator('[data-operation="diary.generate"]:not([disabled])').waitFor();
    assert.equal(await page.evaluate(() => document.documentElement.scrollWidth <= innerWidth + 1), true);
    await page.screenshot({ path: `/tmp/livingemotion-daily-20261109/daily-${width}-${colorScheme}.png`, fullPage: true });
    await page.emulateMedia({ reducedMotion: "reduce" });
    await page.getByRole("tab", { name: "梦境", exact: true }).click();
    assert.equal(await page.evaluate(() => document.getAnimations().length), 0);
    report.cases.push({ name: `tabs/refresh/generate/motion/layout ${width} ${colorScheme}`, passed: true });
    await context.close();
  }
  for (const scenario of ["daily-timeout", "daily-not-found", "daily-unknown"]) {
    const context = await browser.newContext({ reducedMotion: "reduce" });
    const page = await context.newPage();
    page.on("pageerror", e => report.errors.push(e.message));
    await page.goto(`${url}?scenario=${scenario}`);
    await page.locator("#content[aria-busy=false]").waitFor();
    await page.locator('[data-section="experience"]').click();
    await page.locator('[data-operation="diary.generate"]').click();
    await page.reload();
    await page.locator("#content[aria-busy=false]").waitFor();
    if (scenario === "daily-timeout") {
      await page.waitForFunction(() => document.querySelector('[data-record-id="daily-diary"] details[open]'));
    } else {
      await page.locator('[data-operation="diary.generate"]:not([disabled])').waitFor();
      if (scenario === "daily-unknown") assert.match(await page.locator("#experience-panel").textContent(), /可能再次计费/);
    }
    assert.equal(await page.evaluate(() => window.__fixture.calls.filter(c => c.method === "POST").length), 0);
    report.cases.push({ name: `reload reconciliation ${scenario}`, passed: true });
    await context.close();
  }
  assert.deepEqual(report.errors, []);
  assert.deepEqual(report.external, []);
  report.success = true;
} catch (error) { report.success = false; report.failure = error.stack; process.exitCode = 1; }
finally {
  await writeFile("/tmp/livingemotion-daily-20261109/daily-ui-report.json", JSON.stringify(report, null, 2));
  console.log(JSON.stringify(report));
  await browser.close(); server.close();
}
