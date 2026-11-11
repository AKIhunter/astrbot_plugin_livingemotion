/* 所有保存均为合成宿主；验证计时、旧响应、并发冲突和五行编辑。 */
import assert from "node:assert/strict";
import { createRequire } from "node:module";
import { writeFile } from "node:fs/promises";
import { startServer } from "./server.mjs";
const { chromium } = createRequire(import.meta.url)("playwright");
const { server, url } = await startServer();
const browser = await chromium.launch({ headless: true });
const folder = "/tmp/livingemotion-refresh-relations-20261110";
const report = { cases: [], errors: [] };
const writes = page => page.evaluate(() => window.__fixture.calls.filter(c => c.method === "POST" && c.path === "console/config"));
const reads = page => page.evaluate(() => window.__fixture.calls.filter(c => c.path === "console/state").length);
async function open(scenario = "save-fast", width = 1280, theme = "light", clock = false) {
  const page = await browser.newPage({ viewport: { width, height: 1000 }, colorScheme: theme, reducedMotion: "reduce" });
  page.on("pageerror", error => report.errors.push(error.message));
  if (clock) await page.clock.install();
  await page.goto(`${url}?scenario=${scenario}`);
  await page.locator("#content[aria-busy=false]").waitFor();
  await page.locator('[data-section="settings"]').click();
  return page;
}
try {
  for (const width of [1280, 390, 320]) for (const theme of ["light", "dark"]) {
    const page = await open("save-fast", width, theme);
    await page.locator('[data-settings-jump="relationship"]').click();
    assert.equal(await page.locator(".relationship-editor-row").count(), 5);
    assert.equal(await page.locator(".relationship-editor-row textarea").count(), 5);
    assert.equal(await page.locator("#stage-description-0").inputValue(), "反感：保持距离，可以冷淡或表达不满，不羞辱、威胁或攻击对方；正经任务仍可靠。");
    const boxes = await page.locator(".relationship-editor-row").first().evaluate(row => {
      const [a, b] = [...row.children].map(child => child.getBoundingClientRect());
      return { side: b.x >= a.right, stack: b.y >= a.bottom };
    });
    assert.ok(width === 1280 ? boxes.side : boxes.stack);
    assert.equal(await page.locator(".stage-name-editor").evaluate(editor =>
      editor.getBoundingClientRect().width > editor.closest(".field").getBoundingClientRect().width * .9), true);
    await page.locator("#stage-name-4").fill("主人");
    await page.locator("#stage-description-2").fill("珍惜善意，轻松交流。");
    await page.locator("#config-relationship_special_description").fill("温柔陪伴，保留傲娇。");
    await page.screenshot({ path: `${folder}/relationships-${width}-${theme}.png`, fullPage: true });
    await page.locator("#save").click(); await page.locator("#editor").waitFor({ state: "hidden" });
    const [post] = await writes(page);
    assert.equal(post.payload.receipt, "config");
    assert.equal(JSON.parse(post.payload.patch.relationship_stage_names)[4], "主人");
    assert.equal(JSON.parse(post.payload.patch.relationship_stage_descriptions)[2], "珍惜善意，轻松交流。");
    assert.equal(post.payload.patch.relationship_special_description, "温柔陪伴，保留傲娇。");
    assert.equal(await page.evaluate(() => document.documentElement.scrollWidth <= innerWidth + 1), true);
    report.cases.push({ width, theme, five_rows: true, descriptions_saved: true, no_overflow: true });
    await page.close();
  }
  let page = await open("save-fast", 1280, "light", true);
  await page.locator("#config-home_city").fill("未保存的城市");
  await page.locator("#config-home_city").focus();
  await page.evaluate(() => { window.__originalInput = document.activeElement; document.activeElement.setSelectionRange(2, 4); });
  const firstReads = await reads(page);
  await page.clock.runFor(30000);
  await page.locator("#refresh").click();
  await page.locator("#content[aria-busy=false]").waitFor();
  assert.equal(await reads(page), firstReads + 1);
  await page.locator("#config-home_city").focus();
  await page.evaluate(() => document.activeElement.setSelectionRange(2, 4));
  await page.clock.runFor(30001);
  await page.waitForFunction(n => window.__fixture.calls.filter(c => c.path === "console/state").length === n, firstReads + 2);
  assert.equal(await page.locator("#config-home_city").inputValue(), "未保存的城市");
  assert.equal(await page.evaluate(() => document.activeElement === window.__originalInput &&
    document.activeElement.selectionStart === 2 && document.activeElement.selectionEnd === 4), true);
  assert.equal(await page.locator("#save").isDisabled(), false);
  const visibleReads = await reads(page);
  await page.evaluate(() => Object.defineProperty(document, "hidden", { configurable: true, value: true }));
  await page.clock.runFor(120000);
  assert.equal(await reads(page), visibleReads);
  await page.evaluate(() => Object.defineProperty(document, "hidden", { configurable: true, value: false }));
  report.cases.push({ independent_timer: true, draft_dom_focus_selection_preserved: true, hidden_skips: true });
  await page.close();

  // 暂停状态响应，配置预读和保存仍能完成；旧响应释放后不能覆盖回执。
  page = await open("save-fast");
  await page.evaluate(() => {
    const original = window.AstrBotPluginView.apiGet;
    window.AstrBotPluginView.apiGet = async (...args) => {
      const result = await original(...args);
      if (args[0] === "console/state") {
        await new Promise(resolve => { window.__releaseRead = resolve; });
      }
      return result;
    };
  });
  await page.locator("#config-home_city").fill("成都");
  await page.locator("#save").click();
  await page.locator("#editor").waitFor({ state: "hidden" });
  assert.equal((await writes(page)).length, 1);
  assert.equal(await page.locator("#config-home_city").inputValue(), "成都");
  await page.waitForFunction(() => !!window.__releaseRead);
  await page.locator("#refresh").click();
  assert.equal((await writes(page)).length, 1);
  await page.evaluate(() => window.__releaseRead());
  report.cases.push({ compact_ack_does_not_wait_for_state: true }); await page.close();

  page = await open("save-fast", 1280, "light", true);
  await page.evaluate(() => {
    const original = window.AstrBotPluginView.apiGet;
    let blocked = false;
    window.AstrBotPluginView.apiGet = async (...args) => {
      const result = await original(...args);
      if (args[0] === "console/state" && !blocked) {
        blocked = true; await new Promise(resolve => { window.__releaseRead = resolve; });
      }
      return result;
    };
  });
  await page.locator("#config-home_city").fill("成都");
  await page.clock.runFor(60001);
  await page.waitForFunction(() => !!window.__releaseRead);
  const pendingReads = await reads(page);
  await page.locator("#refresh").click();
  assert.equal(await reads(page), pendingReads, "手动与自动共用正在进行的读取");
  await page.locator("#save").click(); await page.locator("#editor").waitFor({ state: "hidden" });
  await page.evaluate(() => window.__releaseRead());
  await page.waitForFunction(() => document.querySelector("#config-home_city").value === "成都" &&
    window.__fixture.calls.filter(c => c.path === "console/state").length >= 3);
  assert.equal((await writes(page)).length, 1);
  report.cases.push({ overlapping_reads_deduplicated: true, old_auto_response_invalidated_by_save: true }); await page.close();

  page = await open("save-fast");
  await page.locator("#config-home_city").fill("成都");
  await page.evaluate(() => window.__fixture.changeConfig({ home_city: "北京", diary_enabled: true }, "other-2"));
  await page.locator("#save").click(); await page.locator("#draft-review").waitFor();
  assert.equal((await writes(page)).length, 0);
  await page.locator("#rebase").click(); await page.locator("#save").click();
  await page.locator("#editor").waitFor({ state: "hidden" });
  assert.equal((await writes(page))[0].payload.expected_revision, "other-2");
  assert.equal(await page.evaluate(() => window.__fixture.state.config.values.diary_enabled), true);
  report.cases.push({ compact_conflict_review_preserved: true }); await page.close();
  for (const scenario of ["save-fast-race", "save-fast-read-error", "save-fast-timeout"]) {
    page = await open(scenario);
    await page.locator("#config-home_city").fill("成都");
    await page.locator("#save").click();
    const feedback = scenario === "save-fast-race" ? /上海/ : scenario === "save-fast-read-error" ? /预读超时/ : /回执超时/;
    await page.locator("#draft-feedback,#draft-conflicts").filter({ hasText: feedback }).first().waitFor();
    assert.equal((await writes(page)).length, scenario === "save-fast-read-error" ? 0 : 1);
    assert.equal(await page.locator("#config-home_city").inputValue(), "成都");
    report.cases.push({ scenario, no_automatic_write_retry: true }); await page.close();
  }
  page = await browser.newPage();
  await page.goto(`${url}?scenario=unauthorized`);
  await page.getByText("私人内容已清空。请在 AstrBot 宿主重新登录并确认管理权限。", { exact: true }).waitFor();
  assert.equal(await page.locator("#refresh").isDisabled(), false, "权限失效后仍允许重新读取确认宿主登录");
  report.cases.push({ authorization_failure_releases_loading: true }); await page.close();
  assert.deepEqual(report.errors, []);
  report.success = true;
} catch (error) { report.success = false; report.failure = error.stack; process.exitCode = 1; }
finally {
  await writeFile(`${folder}/ui-report.json`, JSON.stringify(report, null, 2));
  console.log(JSON.stringify(report)); await browser.close(); server.close();
}
