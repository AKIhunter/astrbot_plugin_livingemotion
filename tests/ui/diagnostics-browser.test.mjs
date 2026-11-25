/* Real pages + native SDK/backend. Parent harness rejects unrelated reads. */
import assert from "node:assert/strict";
import { readFile, writeFile } from "node:fs/promises";
import { chromium } from "playwright";
const base = process.env.DIAGNOSTICS_BASE_URL;
if (!base) throw new Error("Set DIAGNOSTICS_BASE_URL to the loopback native fixture");
if (!["localhost", "127.0.0.1"].includes(new URL(base).hostname)) throw new Error("Loopback fixture required");
const browser = await chromium.launch({ headless: true });
const report = { layer: "real pages / native SDK and auth / parent harness",
  checks: [], external: [], model_calls: 0 };
try {
  for (const plugin of ["le", "lh"]) {
    for (const width of [1280, 390]) {
      const page = await browser.newPage({ viewport: { width, height: 900 }, acceptDownloads: true });
      await page.route("**/*", route => {
        if (new URL(route.request().url()).origin === new URL(base).origin) return route.continue();
        report.external.push(new URL(route.request().url()).origin);
        return route.abort();
      });
      await page.goto(`${base}/diagnostics/${plugin}/index.html`);
      const button = page.locator("#diagnosticsExport");
      const status = page.locator("#diagnosticsStatus");
      const downloading = page.waitForEvent("download");
      await button.click();
      const download = await downloading;
      const bytes = await readFile(await download.path());
      assert.equal(bytes.subarray(0, 4).toString("hex"), "504b0304");
      assert.match(download.suggestedFilename(), /\.zip$/);
      await status.filter({ hasText: "已发起诊断包下载" }).waitFor();
      assert.equal(await button.isDisabled(), false);
      const box = await button.boundingBox();
      assert.ok(box && box.x >= 0 && box.x + box.width <= width + 1);
      report.checks.push(`${plugin}_${width}_native_zip_and_recovery`);
      await page.goto(`${base}/diagnostics/${plugin}/index.html?mode=expired`);
      await button.click();
      await status.filter({ hasText: "登录已失效或无权限" }).waitFor();
      assert.equal(await button.isDisabled(), false);
      report.checks.push(`${plugin}_${width}_expired_auth_visible`);
      await page.close();
    }
  }
  assert.deepEqual(report.external, []);
  if (process.env.DIAGNOSTICS_REPORT) {
    await writeFile(process.env.DIAGNOSTICS_REPORT, JSON.stringify(report, null, 2));
  }
  console.log(`Native diagnostics browser: ${report.checks.length}/${report.checks.length}, external 0, models 0`);
} finally {
  await browser.close();
}
