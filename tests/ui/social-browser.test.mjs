/* Real console fixture; only synthetic config writes, never a bot send. */
import assert from "node:assert/strict";
import { createRequire } from "node:module";
import { writeFile } from "node:fs/promises";
import { startServer } from "./server.mjs";
import { relationshipStage, stageNames } from "../../pages/livingemotion/model.mjs";
const { chromium } = createRequire(import.meta.url)("playwright");
const { server, url } = await startServer();
const browser = await chromium.launch({ headless: true });
const report = { checks: [], errors: [] };
try {
  assert.deepEqual(stageNames(["反感","冷淡","陌生","相识","熟悉","友好","亲近","信赖","知己","挚友","主人"]),
    ["反感", "陌生", "友好", "亲近", "主人"]);
  for (const [score, index] of [[0,0],[10.9,0],[11,1],[24.9,1],[25,2],[44.9,2],[45,3],[99,3],[100,4]])
    assert.equal(relationshipStage({ score }, []).index, index);
  for (const width of [1280, 390]) {
    const page = await browser.newPage({ viewport: { width, height: 1000 } });
    page.on("pageerror", error => report.errors.push(error.message));
    await page.goto(`${url}?scenario=native-dto`);
    await page.locator("#content[aria-busy=false]").waitFor();
    await page.locator('[data-section="settings"]').click();
    await page.locator('[data-settings-jump="relationship"]').click();
    const entries = page.locator(".stage-name-editor input");
    assert.equal(await entries.count(), 5);
    assert.deepEqual(await page.locator(".stage-name-editor label").allTextContents(),
      ["0–10 分", "11–24 分", "25–44 分", "45–99 分", "100 · 独特（管理员设置）"]);
    await entries.nth(4).fill("主人");
    const special = page.locator("#config-relationship_special_description");
    assert.equal(await special.evaluate(el => el.tagName), "TEXTAREA");
    await special.fill("主人，温柔陪伴，关心加倍");
    await page.locator("#save").click();
    await page.locator("#editor").waitFor({ state: "hidden" });
    const call = await page.evaluate(() => window.__fixture.calls.find(c => c.path === "console/config"));
    assert.equal(JSON.parse(call.payload.patch.relationship_stage_names)[4], "主人");
    assert.equal(call.payload.patch.relationship_special_description, "主人，温柔陪伴，关心加倍");
    assert.equal(await page.evaluate(() => document.documentElement.scrollWidth <= innerWidth + 1), true);
    report.checks.push({ width, five_bands: true, special_saved: true });
    await page.close();
  }
  assert.deepEqual(report.errors, []);
  report.success = true;
} catch (error) { report.success = false; report.failure = error.stack; process.exitCode = 1; }
finally {
  await writeFile("/tmp/livingemotion-social-20261109/social-ui-report.json", JSON.stringify(report, null, 2));
  console.log(JSON.stringify(report)); await browser.close(); server.close();
}
