import assert from "node:assert/strict";
import { createRequire } from "node:module";
import { readFile, writeFile } from "node:fs/promises";
import { startServer } from "./server.mjs";
const { chromium } = createRequire(import.meta.url)("playwright");
const folder = "/tmp/livingemotion-persona-refresh-20261110";
const { server, url } = await startServer();
const browser = await chromium.launch({ headless: true });
const report = { success: false, cases: [], errors: [] };
const fixture = await readFile(new URL("./fixture-bridge.mjs", import.meta.url), "utf8");
const catalog = `
window.__personas = ["fixture-persona", "removed-persona"];
const originalGet = window.AstrBotPluginView.apiGet;
window.AstrBotPluginView.apiGet = async (path, params) => {
  const result = await originalGet(path, params);
  if (path === "console/scopes") result.data.personas =
    window.__personas.map(id => ({ id, name: id }));
  return result;
};`;
try {
  for (const width of [1280, 390]) for (const automatic of [false, true]) {
    for (const selectedDeleted of [false, true]) {
      const page = await browser.newPage({ viewport: { width, height: 1000 }, reducedMotion: "reduce" });
      page.on("pageerror", error => report.errors.push(error.message));
      await page.clock.install();
      await page.route("**/fixture-bridge.mjs", route => route.fulfill({
        contentType: "text/javascript", body: fixture + catalog,
      }));
      await page.goto(url);
      await page.locator("#content[aria-busy=false]").waitFor();
      await page.locator("[data-section=persona]").click();
      const picker = page.locator("select#persona-picker");
      assert.deepEqual(await picker.locator("option").allTextContents(), ["fixture-persona", "removed-persona"]);
      if (selectedDeleted) {
        await picker.selectOption("removed-persona");
        await page.getByRole("button", { name: "应用", exact: true }).click();
        await page.locator("#content[aria-busy=false]").waitFor();
        assert.equal(await picker.inputValue(), "removed-persona");
      }
      await page.evaluate(() => { window.__personas = ["fixture-persona", "new-persona"]; });
      if (automatic) {
        await page.locator("[data-section=persona]").focus();
        await page.clock.runFor(60001);
      } else await page.locator("#refresh").click();
      await page.waitForFunction(() =>
        [...document.querySelectorAll("select#persona-picker option")].map(option => option.value).join(",") ===
          "fixture-persona,new-persona");
      assert.equal(await picker.inputValue(), "fixture-persona");
      assert.equal(await page.evaluate(() => window.__fixture.calls.filter(call => call.path === "console/state").at(-1).payload.persona_id),
        "fixture-persona");
      assert.equal(await page.evaluate(() => window.__fixture.calls.filter(call => call.method === "POST").length), 0);
      assert.equal(await page.evaluate(() => document.documentElement.scrollWidth <= innerWidth + 1), true);
      await page.locator("body").screenshot({ path: `${folder}/fixture-${width}-${automatic ? "auto" : "manual"}-${selectedDeleted}.png` });
      report.cases.push({ width, automatic, selectedDeleted, removed: true, added: true, recovered: true, writes: 0 });
      await page.close();
    }
  }
  assert.deepEqual(report.errors, []);
  report.success = true;
} catch (error) { report.failure = error.message; process.exitCode = 1; }
finally {
  await writeFile(`${folder}/fixture-report.json`, JSON.stringify(report, null, 2));
  console.log(JSON.stringify(report)); await browser.close(); server.close();
}
