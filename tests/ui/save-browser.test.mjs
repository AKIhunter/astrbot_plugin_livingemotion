/* Native Console DTO; all configuration writes and concurrent edits are synthetic. */
import assert from "node:assert/strict";
import { createRequire } from "node:module";
import { writeFile } from "node:fs/promises";
import { startServer } from "./server.mjs";
const { chromium } = createRequire(import.meta.url)("playwright");
const { server, url } = await startServer();
const browser = await chromium.launch({ headless: true });
const report = { cases: [], errors: [] };
async function open(scenario = "native-dto", options = {}) {
  const page = await browser.newPage({ viewport: { width: 1280, height: 800 }, ...options });
  page.on("pageerror", e => report.errors.push(e.message));
  await page.goto(`${url}?scenario=${scenario}`);
  await page.locator("#content[aria-busy=false]").waitFor();
  await page.locator('[data-section="settings"]').click();
  return page;
}
const writes = page => page.evaluate(() => window.__fixture.calls.filter(c => c.path === "console/config" && c.method === "POST"));
const change = (page, patch, revision) => page.evaluate(({ patch, revision }) =>
  window.__fixture.changeConfig(patch, revision), { patch, revision });
async function clickVisibleSave(page) {
  const box = await page.locator("#save").boundingBox();
  assert.ok(box.y >= 0 && box.y + box.height <= page.viewportSize().height);
  // 坐标点击不会像 locator.click 一样自动把底部控件滚入视口。
  await page.mouse.click(box.x + box.width / 2, box.y + box.height / 2);
}
try {
  for (const width of [1280, 390]) for (const colorScheme of ["light", "dark"]) {
    const page = await open("native-dto", { viewport: { width, height: 800 }, colorScheme, reducedMotion: "reduce" });
    assert.equal(await page.locator("#editor").isVisible(), false);
    await page.locator("#config-home_city").fill("深圳");
    await page.locator('[data-settings-jump="night"]').click();
    const beforeWheel = await page.evaluate(() => scrollY);
    await page.mouse.move(width - 30, 300); await page.mouse.wheel(0, 400);
    await page.waitForFunction(y => scrollY >= y + 390, beforeWheel);
    const bar = await page.locator("#editor").boundingBox();
    assert.ok(bar.x >= 0 && bar.x + bar.width <= width && bar.y + bar.height <= 800);
    assert.equal(await page.locator("#editor").evaluate(e => getComputedStyle(e).position), "fixed");
    assert.ok(!/基准版本|原生配置|[a-f0-9]{64}/.test(await page.locator("#editor").textContent()));
    const at = await page.evaluate(() => ({ y: scrollY, bottom: document.documentElement.scrollHeight - innerHeight }));
    assert.ok(at.bottom - at.y > 100, "保存时仍未到页面最底部");
    await page.screenshot({ path: `/tmp/livingemotion-save-20261109/bar-${width}-${colorScheme}.png` });
    await clickVisibleSave(page);
    await page.locator("#editor").waitFor({ state: "hidden" });
    assert.deepEqual((await writes(page))[0].payload.patch, { home_city: "深圳" });
    assert.equal(await page.evaluate(() => window.__fixture.state.config.values.home_city), "深圳");
    const afterY = await page.evaluate(() => scrollY);
    assert.ok(Math.abs(afterY - at.y) < 50, `保存前后滚动位置 ${at.y} → ${afterY}`);
    assert.equal(await page.evaluate(() => document.documentElement.scrollWidth <= innerWidth + 1), true);
    await page.locator('[data-section="experience"]').click();
    await page.getByRole("tab", { name: "设置", exact: true }).click();
    const pool = page.locator("#config-dream_theme_pool");
    await pool.fill("赛博朋克\n绿野仙踪\n生活日常");
    await clickVisibleSave(page); await page.locator("#editor").waitFor({ state: "hidden" });
    assert.equal((await writes(page)).length, 2);
    await page.locator('[data-section="settings"]').click();
    await page.locator('[data-settings-jump="quick_start"]').click();
    await page.locator("#config-home_city").fill("未保存");
    await page.locator("#discard").focus(); await page.keyboard.press("Enter");
    assert.equal(await page.locator("#editor").isVisible(), false);
    assert.equal(await page.locator("#config-home_city").inputValue(), "深圳");
    report.cases.push({ width, colorScheme, long_page_save: true, paper_save: true, discard_keyboard: true });
    await page.close();
  }
  let page = await open("save-overlap");
  await page.locator("#config-home_city").fill("深圳");
  await change(page, { home_city: "上海", diary_enabled: true }, "other-2");
  await clickVisibleSave(page); await page.locator("#draft-review").waitFor();
  assert.equal((await writes(page)).length, 0);
  assert.equal(await page.locator("#save").isDisabled(), true);
  assert.ok((await page.locator("#draft-conflicts").textContent()).includes("上海"));
  assert.ok((await page.locator("#draft-conflicts").textContent()).includes("深圳"));
  assert.ok(!/Revision changed|version_conflict/.test(await page.locator("#draft-feedback").textContent()));
  await page.locator("#rebase").click();
  await change(page, { home_city: "杭州" }, "other-3");
  await clickVisibleSave(page); await page.getByText("杭州", { exact: true }).waitFor();
  assert.equal((await writes(page)).length, 0, "复核后有新冲突仍不能覆盖");
  await page.locator("#rebase").click(); await clickVisibleSave(page);
  await page.locator("#editor").waitFor({ state: "hidden" });
  assert.equal((await writes(page))[0].payload.expected_revision, "other-3");
  assert.equal(await page.evaluate(() => window.__fixture.state.config.values.diary_enabled), true);
  report.cases.push({ overlap: "shown; explicit review; new conflict rechecked; other edits preserved" });
  await page.close();
  page = await open("save-unrelated");
  await page.locator("#config-home_city").fill("深圳");
  await change(page, { diary_enabled: true }, "unrelated-2");
  await clickVisibleSave(page); await page.locator("#editor").waitFor({ state: "hidden" });
  assert.equal((await writes(page))[0].payload.expected_revision, "unrelated-2");
  assert.equal(await page.evaluate(() => window.__fixture.state.config.values.diary_enabled), true);
  report.cases.push({ unrelated: "merged in one click" }); await page.close();
  page = await open("save-equal");
  await page.locator("#config-home_city").fill("深圳");
  await change(page, { home_city: "深圳" }, "equal-2");
  await clickVisibleSave(page); await page.locator("#editor").waitFor({ state: "hidden" });
  assert.equal((await writes(page)).length, 0);
  report.cases.push({ equal: "already saved; no redundant POST" }); await page.close();
  page = await open("save-race");
  await page.locator("#config-home_city").fill("深圳");
  await clickVisibleSave(page); await page.locator("#draft-review").waitFor();
  assert.equal((await writes(page)).length, 1, "CAS失败不会自动重试");
  assert.equal(await page.locator("#config-home_city").inputValue(), "深圳");
  await page.locator("#rebase").click(); await clickVisibleSave(page);
  await page.locator("#editor").waitFor({ state: "hidden" });
  assert.equal((await writes(page)).length, 2);
  report.cases.push({ race: "409 reloads; draft kept; manual retry" }); await page.close();
  page = await open("save-read-error");
  await page.locator("#config-home_city").fill("深圳"); await clickVisibleSave(page);
  await page.locator("#draft-feedback").getByText(/合成预读超时/).waitFor();
  assert.equal((await writes(page)).length, 0);
  assert.equal(await page.locator("#config-home_city").inputValue(), "深圳");
  report.cases.push({ read_failure: "no POST; draft kept" }); await page.close();
  page = await open("save-timeout");
  await page.locator("#config-home_city").fill("深圳"); await clickVisibleSave(page);
  await page.locator("#draft-feedback").getByText(/回执超时/).waitFor();
  assert.equal(await page.locator("#save").isDisabled(), true);
  assert.equal((await writes(page)).length, 1);
  report.cases.push({ timeout: "no automatic retry; write disabled" }); await page.close();
  assert.deepEqual(report.errors, []);
  report.success = true;
} catch (error) { report.success = false; report.failure = error.stack; process.exitCode = 1; }
finally {
  await writeFile("/tmp/livingemotion-save-20261109/ui-report.json", JSON.stringify(report, null, 2));
  console.log(JSON.stringify(report)); await browser.close(); server.close();
}
