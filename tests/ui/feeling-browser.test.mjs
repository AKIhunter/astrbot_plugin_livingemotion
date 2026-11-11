import assert from "node:assert/strict";
import { createRequire } from "node:module";
import { writeFile } from "node:fs/promises";
import { startServer } from "./server.mjs";
const { chromium } = createRequire(import.meta.url)("playwright");
const { server, url } = await startServer();
const browser = await chromium.launch({ headless: true });
const report = { cases: [], errors: [] };
try {
  for (const width of [1440, 1280, 390]) for (const theme of ["light", "dark"]) {
    const page = await browser.newPage({ viewport: { width, height: 1000 }, colorScheme: theme, reducedMotion: "reduce" });
    page.on("pageerror", e => report.errors.push(e.message));
    await page.goto(`${url}?scenario=native-dto`);
    await page.locator("#content[aria-busy=false]").waitFor();
    await page.getByLabel("此刻心绪", { exact: true }).waitFor();
    assert.ok((await page.locator(".hero-feeling").textContent()).includes("每 12 小时"));
    await page.evaluate(() => {
      window.__fixture.setFeeling({ text: "想起你说的话，心里悄悄暖了一点。", generated_at: 1794229200, status: "succeeded" });
    });
    await page.locator("#refresh").click();
    await page.getByText("想起你说的话，心里悄悄暖了一点。", { exact: true }).waitFor();
    const { hero, radar } = await page.evaluate(async () => {
      await new Promise(resolve => requestAnimationFrame(() => requestAnimationFrame(resolve)));
      const box = selector => {
        const { x, y, width, height } = document.querySelector(selector).getBoundingClientRect();
        return { x, y, width, height };
      };
      return { hero: box(".ta-layout > .hero"), radar: box(".ta-layout > :nth-child(2)") };
    });
    if (width >= 1280) {
      assert.ok(Math.abs(hero.y - radar.y) < 1);
      assert.ok(Math.abs(hero.y + hero.height - radar.y - radar.height) < 1,
        `两卡片底边必须相齐 ${JSON.stringify({ hero, radar })}`);
    } else {
      assert.ok(radar.y >= hero.y + hero.height);
    }
    assert.equal(await page.evaluate(() => document.documentElement.scrollWidth <= innerWidth + 1), true);
    assert.equal(await page.evaluate(() => window.__fixture.calls.filter(c => c.method === "POST").length), 0);
    await page.screenshot({ path: `/tmp/livingemotion-feeling-20261109/feeling-${width}-${theme}.png`, fullPage: true });
    report.cases.push({ width, theme, aligned: true, text: true, no_writes: true });
    await page.close();
  }
  assert.deepEqual(report.errors, []);
  report.success = true;
} catch (error) { report.success = false; report.failure = error.stack; process.exitCode = 1; }
finally {
  await writeFile("/tmp/livingemotion-feeling-20261109/ui-report.json", JSON.stringify(report, null, 2));
  console.log(JSON.stringify(report)); await browser.close(); server.close();
}
