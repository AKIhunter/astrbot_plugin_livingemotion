/* Synthetic host only: no platform send or paid provider calls. */
import assert from "node:assert/strict";
import { createRequire } from "node:module";
import fs from "node:fs/promises";
import { startServer } from "./server.mjs";
const { chromium } = createRequire(import.meta.url)("playwright");
const DRAFT = "console/style-summary-draft", SAVE = "console/style-summary-save";
const PERSONA = "fixture-persona", OTHER = "fixture-persona-b";
const FILL = "用主模型自动填写", CONFIRM = "覆盖未保存的修改？再点一次";
const draftText = persona => `合成风格摘要草稿：${persona}。`;
const summaryText = persona => `合成风格摘要：${persona}。`;
const folder = process.env.LIVINGEMOTION_STYLE_OUTPUT || "/tmp/livingemotion-style-draft-20261126";
const { server, url } = await startServer();
const browser = await chromium.launch({ headless: true });
const report = { success: false, cases: [], errors: [], dialogs: [], layouts: [] };

// 设置页按分区导航：先跳到「原生人格」所在分区，风格摘要挂在它下面。
async function revealPersona(page) {
  const select = page.locator("#config-persona_id");
  if (!await select.isVisible()) {
    const group = await select.evaluate(el => el.closest("[data-task-group]").dataset.taskGroup);
    await page.locator(`[data-settings-jump="${group}"]`).click();
  }
  return select;
}
async function open(width) {
  const page = await browser.newPage({ viewport: { width, height: 1000 }, reducedMotion: "reduce" });
  page.setDefaultTimeout(8000);
  page.on("pageerror", error => report.errors.push(error.message));
  // 覆盖确认必须靠按钮文字完成：出现任何原生对话框都记为失败并关闭。
  page.on("dialog", async dialog => { report.dialogs.push(dialog.message()); await dialog.dismiss(); });
  await page.clock.install();
  await page.goto(`${url}?scenario=native-dto`);
  await page.locator("#content[aria-busy=false]").waitFor();
  await page.locator("[data-section=settings]").click();
  await (await revealPersona(page)).selectOption(PERSONA);
  await page.locator(".style-summary-editor textarea:enabled").waitFor();
  return page;
}
const block = page => page.locator(".style-summary-editor");
const area = page => page.locator(".style-summary-text");
const meta = page => page.locator(".style-summary-meta");
const named = (page, name) => block(page).getByRole("button", { name, exact: true });
const dirty = page => area(page).evaluate(el => el.dataset.dirty);
const callsTo = (page, path) => page.evaluate(path =>
  window.__fixture.calls.filter(call => call.path === path), path);
const metaHas = (page, text) => page.waitForFunction(text =>
  document.querySelector(".style-summary-meta").textContent.includes(text), text);
const areaIs = (page, text) => page.waitForFunction(text =>
  document.querySelector(".style-summary-text").value === text, text);
// 等第 count 个草稿请求真正发出再放行闸门，避免在点击尚未送达时提前 release。
const requested = (page, count = 1) => page.waitForFunction(([path, count]) =>
  window.__fixture.calls.filter(call => call.path === path).length >= count, [DRAFT, count]);
const settle = page => page.evaluate(() => new Promise(resolve => setTimeout(resolve, 50)));

async function caseRun(name, task) {
  const page = await open(1280);
  try { await task(page); report.cases.push({ name, passed: true }); console.log(`通过：${name}`); }
  catch (error) { report.cases.push({ name, passed: false, error: error.message }); console.error(`失败：${name}：${error.stack}`); }
  finally { await page.close(); }
}

try {
  await fs.mkdir(folder, { recursive: true });
  await caseRun("按钮与费用说明存在；生成只填草稿，点保存摘要才写入", async page => {
    const original = await area(page).inputValue();
    assert.equal(original, summaryText(PERSONA));
    assert.equal(await named(page, FILL).count(), 1);
    assert.equal(await named(page, FILL).isEnabled(), true);
    const text = await block(page).textContent();
    assert.ok(text.includes("会调用一次主模型，可能产生模型费用"));
    assert.ok(text.includes("点「保存摘要」后才生效"));
    await named(page, FILL).click();
    await areaIs(page, draftText(PERSONA));
    assert.deepEqual(await callsTo(page, DRAFT), [{ method: "POST", path: DRAFT, payload: { persona_id: PERSONA } }]);
    assert.equal(await dirty(page), "true");
    const shown = await meta(page).textContent();
    assert.ok(shown.includes(`${draftText(PERSONA).length} / 2000 字`), shown);
    assert.ok(shown.endsWith("已生成草稿，未保存"), shown);
    assert.equal(await named(page, "保存摘要").isEnabled(), true);
    assert.equal(await named(page, FILL).isEnabled(), true);
    assert.equal((await callsTo(page, SAVE)).length, 0);
    // 自动刷新不会替用户保存，草稿原样留在输入框里。
    await page.clock.runFor(60001);
    assert.equal(await area(page).inputValue(), draftText(PERSONA));
    assert.equal(await dirty(page), "true");
    assert.equal((await callsTo(page, SAVE)).length, 0);
    await named(page, "保存摘要").click();
    await metaHas(page, "已保存");
    assert.deepEqual((await callsTo(page, SAVE)).map(call => call.payload.text), [draftText(PERSONA)]);
    assert.equal((await callsTo(page, DRAFT)).length, 1);
    assert.equal(await dirty(page), "false");
  });

  await caseRun("生成中显示状态并禁用输入框和三个按钮", async page => {
    await page.evaluate(() => window.__fixture.holdDraft());
    await named(page, FILL).click();
    await requested(page);
    assert.equal(await meta(page).textContent(), "正在用主模型生成…");
    assert.equal(await area(page).isDisabled(), true);
    for (const name of [FILL, "保存摘要", "恢复默认"]) {
      assert.equal(await named(page, name).isDisabled(), true, name);
    }
    await page.clock.runFor(60001);
    assert.equal(await meta(page).textContent(), "正在用主模型生成…");
    assert.equal(await named(page, FILL).isDisabled(), true);
    await page.evaluate(() => window.__fixture.releaseDraft());
    await areaIs(page, draftText(PERSONA));
    assert.equal(await dirty(page), "true");
    assert.equal(await area(page).isDisabled(), false);
    assert.equal(await named(page, "保存摘要").isEnabled(), true);
    assert.equal((await callsTo(page, DRAFT)).length, 1);
    assert.equal((await callsTo(page, SAVE)).length, 0);
  });

  await caseRun("失败时在提示里显示错误，输入框保留原内容", async page => {
    await page.evaluate(() => window.__fixture.holdDraft());
    await named(page, FILL).click();
    await requested(page);
    await page.evaluate(() => window.__fixture.releaseDraft("unavailable"));
    await metaHas(page, "模型不可用或生成失败，没有生成草稿");
    assert.equal(await area(page).inputValue(), summaryText(PERSONA));
    assert.equal(await dirty(page), "false");
    assert.equal(await area(page).isDisabled(), false);
    assert.equal(await named(page, "保存摘要").isDisabled(), true);
    assert.equal((await callsTo(page, SAVE)).length, 0);
    // 手写内容未保存时失败：内容原样保留，仍可直接保存。
    await area(page).fill("手写的摘要");
    await page.evaluate(() => window.__fixture.holdDraft());
    await named(page, FILL).click();
    assert.equal(await named(page, CONFIRM).count(), 1);
    await named(page, CONFIRM).click();
    await requested(page, 2);
    await page.evaluate(() => window.__fixture.releaseDraft("generation_in_progress"));
    await metaHas(page, "上一份草稿还在生成");
    assert.equal(await area(page).inputValue(), "手写的摘要");
    assert.equal(await dirty(page), "true");
    assert.equal(await named(page, "保存摘要").isEnabled(), true);
    assert.equal(await named(page, FILL).textContent(), FILL);
    assert.equal((await callsTo(page, SAVE)).length, 0);
  });

  await caseRun("模型没有返回正文与等待超时分开提示，输入框保留原内容", async page => {
    await page.evaluate(() => window.__fixture.holdDraft());
    await named(page, FILL).click();
    await requested(page);
    await page.evaluate(() => window.__fixture.releaseDraft("empty_response"));
    await metaHas(page, "模型没有返回正文，没有生成草稿。可以调大「模型输出上限」，或换个模型再试。");
    assert.ok(!(await meta(page).textContent()).includes("超时"));
    assert.equal(await area(page).inputValue(), summaryText(PERSONA));
    assert.equal(await named(page, FILL).isEnabled(), true);
    await page.evaluate(() => window.__fixture.holdDraft());
    await named(page, FILL).click();
    await requested(page, 2);
    await page.evaluate(() => window.__fixture.releaseDraft("timeout"));
    await metaHas(page, "等待模型超时，没有生成草稿，可以重试。");
    assert.ok(!(await meta(page).textContent()).includes("没有返回正文"));
    assert.equal(await area(page).inputValue(), summaryText(PERSONA));
    assert.equal(await dirty(page), "false");
    assert.equal((await callsTo(page, SAVE)).length, 0);
  });

  await caseRun("有未保存修改时需再点一次确认才覆盖", async page => {
    await area(page).fill("手写的摘要");
    await named(page, FILL).click();
    assert.equal(await named(page, CONFIRM).count(), 1);
    assert.equal((await callsTo(page, DRAFT)).length, 0);
    assert.equal(await area(page).inputValue(), "手写的摘要");
    // 继续编辑会取消这次确认。
    await area(page).fill("手写的摘要，又改了");
    assert.equal(await named(page, FILL).count(), 1);
    await named(page, FILL).click();
    await named(page, CONFIRM).click();
    await areaIs(page, draftText(PERSONA));
    assert.equal((await callsTo(page, DRAFT)).length, 1);
    assert.equal(await named(page, FILL).textContent(), FILL);
    // 刚生成的草稿也算未保存修改：再点一次仍需确认，不会重复请求。
    await named(page, FILL).click();
    assert.equal(await named(page, CONFIRM).count(), 1);
    assert.equal((await callsTo(page, DRAFT)).length, 1);
    assert.equal((await callsTo(page, SAVE)).length, 0);
  });

  await caseRun("生成中切换人格丢弃结果", async page => {
    await page.evaluate(() => window.__fixture.holdDraft());
    await named(page, FILL).click();
    await requested(page);
    await page.locator("#config-persona_id").selectOption(OTHER);
    await areaIs(page, summaryText(OTHER));
    await page.evaluate(() => window.__fixture.releaseDraft());
    await settle(page);
    assert.equal(await area(page).inputValue(), summaryText(OTHER));
    assert.equal(await dirty(page), "false");
    assert.ok(!(await meta(page).textContent()).includes("已生成草稿"));
    assert.equal(await area(page).isDisabled(), false);
    assert.equal((await callsTo(page, DRAFT)).length, 1);
    // 切回原人格也不会补回旧草稿。
    await page.locator("#config-persona_id").selectOption(PERSONA);
    await areaIs(page, summaryText(PERSONA));
    await settle(page);
    assert.equal(await area(page).inputValue(), summaryText(PERSONA));
    assert.equal(await dirty(page), "false");
    assert.equal((await callsTo(page, SAVE)).length, 0);
  });

  await caseRun("切页签重建设置页后接回在途草稿，不重复请求", async page => {
    const backToSettings = async () => {
      await page.locator("[data-section=overview]").click();
      await page.locator("[data-section=settings]").click();
      assert.equal(await (await revealPersona(page)).inputValue(), PERSONA);
    };
    await page.evaluate(() => window.__fixture.holdDraft());
    await named(page, FILL).click();
    await requested(page);
    await backToSettings();
    await metaHas(page, "正在用主模型生成…");
    assert.equal(await named(page, FILL).isDisabled(), true);
    assert.equal(await named(page, "保存摘要").isDisabled(), true);
    assert.equal(await area(page).isDisabled(), true);
    await page.evaluate(() => window.__fixture.releaseDraft());
    await areaIs(page, draftText(PERSONA));
    assert.equal(await dirty(page), "true");
    assert.equal((await callsTo(page, DRAFT)).length, 1);
    // 未保存的草稿在再次重建后原样保留，仍然不会自动保存。
    await backToSettings();
    await areaIs(page, draftText(PERSONA));
    assert.equal(await dirty(page), "true");
    assert.equal(await named(page, "保存摘要").isEnabled(), true);
    assert.equal((await callsTo(page, DRAFT)).length, 1);
    assert.equal((await callsTo(page, SAVE)).length, 0);
  });

  for (const width of [390, 320]) {
    // 设置页保留 700px 最小画布：三个按钮排在同一行，不溢出摘要卡片。
    const page = await open(width);
    const metrics = await block(page).evaluate(editor => {
      const box = editor.getBoundingClientRect();
      const actions = editor.querySelector(".style-summary-actions");
      return {
        editor_width: Math.round(box.width),
        actions_scroll_overflow: actions.scrollWidth > actions.clientWidth + 1,
        same_row: new Set([...actions.querySelectorAll("button")].map(item => Math.round(item.getBoundingClientRect().top))).size === 1,
        buttons: [...actions.querySelectorAll("button")].map(item => {
          const rect = item.getBoundingClientRect();
          return { text: item.textContent, left: Math.round(rect.left - box.left), right: Math.round(rect.right - box.left) };
        }),
      };
    });
    report.layouts.push({ width, ...metrics });
    assert.equal(metrics.actions_scroll_overflow, false);
    assert.equal(metrics.same_row, true);
    assert.ok(metrics.buttons.every(item => item.right < metrics.editor_width), JSON.stringify(metrics));
    await block(page).screenshot({ path: `${folder}/style-summary-${width}.png` });
    await page.close();
  }
  assert.deepEqual(report.dialogs, []);
  assert.deepEqual(report.errors, []);
  report.success = report.cases.every(item => item.passed);
  if (!report.success) process.exitCode = 1;
} catch (error) { report.failure = error.stack; process.exitCode = 1; }
finally {
  await fs.writeFile(`${folder}/fixture-report.json`, JSON.stringify(report, null, 2));
  console.log(JSON.stringify(report)); await browser.close(); server.close();
}
