/* Synthetic UI + virtual clock only; reject every external request. */
import assert from "node:assert/strict";
import { createRequire } from "node:module";
import { writeFile } from "node:fs/promises";
import { startServer } from "./server.mjs";
const { chromium } = createRequire(import.meta.url)(process.env.PW_MODULE || "playwright");
const { server, url } = await startServer();
const browser = await chromium.launch({ headless: true,
  ...(process.env.CHROME_PATH ? { executablePath: process.env.CHROME_PATH } : {}),
  args: ["--disable-background-networking", "--disable-sync", "--no-first-run",
    "--proxy-server=http://127.0.0.1:9", "--proxy-bypass-list=127.0.0.1;localhost"] });
const report = { layer: "isolated_browser", checks: [], errors: [], real_model_calls: 0, writes: 0 };
const check = (name, condition) => { assert.ok(condition, name); report.checks.push(name); };
try {
  for (const width of [1440, 390]) {
    const page = await browser.newPage({ viewport: { width, height: 1000 }, reducedMotion: "reduce" });
    page.on("pageerror", error => report.errors.push(error.message));
    await page.route("**/*", route => new URL(route.request().url()).origin === new URL(url).origin
      ? route.continue() : route.abort());
    await page.clock.install();
    await page.goto(`${url}?scenario=ta-relationships`);
    await page.locator("#content[aria-busy=false]").waitFor();
    check(`${width}_suggestions_ten`, await page.locator("#context-emotion-picker option").count() === 11);
    await page.locator("#context-emotion-query").fill("80029");
    await page.locator("#context-emotion-query").press("Enter");
    await page.waitForFunction(() => document.querySelector("#context-emotion-picker")?.value === "ta-extra-29" &&
      document.querySelector('[data-context-emotion-scope]')?.textContent.includes("80029"));
    for (const kind of ["wronged", "hurt", "shyness"]) {
      check(`${width}_${kind}_measured_zero`, await page.locator(`[data-emotion="${kind}"]`).first().getAttribute("data-value") === "0");
    }
    await page.locator('[data-section="relationships"]').click();
    await page.locator(".relationship-table tbody tr").first().waitFor();
    const call = await page.evaluate(() => window.__fixture.calls.filter(c => c.path === "console/relationships").at(-1));
    check(`${width}_ta_does_not_limit_relationships`, call.payload.view_scope === "global" &&
      !call.payload.context_id && !call.payload.platform);
    await page.locator("#relationship-platform").selectOption("bilibili");
    await page.locator("#relationship-query").fill("10010");
    await page.locator(".relationship-filters button[type=submit]").click();
    await page.waitForFunction(() => document.querySelector(".relationship-table tbody tr")?.textContent.includes("10010"));
    await page.locator(".relationship-table tbody button").first().click();
    const fields = await page.locator(".graph-detail dt").allTextContents();
    check(`${width}_no_trust_boundary`, !fields.includes("信任") && !fields.includes("边界"));
    await page.locator('[data-section="overview"]').click();
    check(`${width}_relationship_does_not_change_ta`, await page.locator("#context-emotion-picker").inputValue() === "ta-extra-29");
    await page.clock.fastForward(60001);
    await page.waitForFunction(() => document.querySelector("#content")?.getAttribute("aria-busy") === "false");
    check(`${width}_ta_auto_refresh_keeps_selection`, await page.locator("#context-emotion-picker").inputValue() === "ta-extra-29");
    await page.reload();
    await page.locator("#content[aria-busy=false]").waitFor();
    check(`${width}_ta_reload_keeps_selection`, await page.locator("#context-emotion-picker").inputValue() === "ta-extra-29");
    await page.locator('[data-section="relationships"]').click();
    await page.locator(".relationship-table tbody tr").first().waitFor();
    check(`${width}_relationship_filters_persist`, await page.locator("#relationship-platform").inputValue() === "bilibili" &&
      await page.locator("#relationship-query").inputValue() === "10010");
    await page.locator('[data-section="overview"]').click();
    await page.locator("#context-emotion-query").fill("missing-id");
    check(`${width}_missing_no_candidates`, await page.locator("#context-emotion-picker option").count() === 1);
    await page.locator("#context-emotion-query").fill("");
    await page.locator("#context-emotion-picker").selectOption("");
    await page.waitForFunction(() => document.querySelector('[data-emotion="wronged"]')?.dataset.value === "uncollected");
    check(`${width}_global_not_fake_zero`, await page.locator('[data-emotion="hurt"]').first().getAttribute("data-value") === "uncollected");
    const layout = await page.evaluate(() => ({ width: innerWidth, scrollWidth: document.documentElement.scrollWidth,
      overflow: [...document.querySelectorAll("#content *")].map(el => ({
        tag: el.tagName, id: el.id, className: el.className,
        right: el.getBoundingClientRect().right, width: el.getBoundingClientRect().width,
      })).filter(el => el.right > innerWidth + 1).slice(0, 8) }));
    report.layouts ||= []; report.layouts.push(layout);
    // Existing console is desktop-sized: exact untouched baseline at 390px is 700px.
    check(`${width}_no_new_horizontal_overflow`, layout.scrollWidth <= (width === 390 ? 700 : width) + 1);
    check(`${width}_read_only`, await page.evaluate(() => window.__fixture.calls.every(c => c.method === "GET")));
    await page.close();
  }
  assert.deepEqual(report.errors, []);
} finally {
  if (process.env.REPORT_PATH) await writeFile(process.env.REPORT_PATH, JSON.stringify(report, null, 2));
  await browser.close(); await new Promise(resolve => server.close(resolve));
}
console.log(JSON.stringify(report));
