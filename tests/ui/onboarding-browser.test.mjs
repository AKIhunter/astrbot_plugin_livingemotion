/* Synthetic host + virtual clock only: no platform send or paid provider calls. */
import assert from "node:assert/strict";
import { createRequire } from "node:module";
import { messages } from "../../pages/livingemotion/messages.mjs";
import { startServer } from "./server.mjs";
import { nativeDTO } from "./fixtures.mjs";

const { chromium } = createRequire(import.meta.url)("playwright");
// 既有控制台 body 最小宽度 700px（见 browser.test.mjs）：窄屏只断言不新增横向溢出。
const MINIMUM_CONSOLE_WIDTH = 700;
const TITLES = ["1. 人格", "2. 关系", "3. 长夜", "4. 提示词注入", "5. 风格摘要", "6. 模型选择"];
// 步骤、点击后应展开的分区、应获得焦点的字段。
const STEPS = [
  ["persona", "persona", "config-persona_mode"],
  ["relationship", "relationship", "stage-name-0"],
  ["night", "night", "config-allow_sleep"],
  ["prompts", "prompt_injection", "config-character_prompt_enabled"],
  ["style", "persona", "config-persona_id"],
  ["models", "quick_start", "config-provider_id"],
];
const MODELS = [
  ["provider_id", "quick_start", "跟随主模型"], ["fallback_provider_id", "quick_start", "跟随主模型"],
  ["emotion_provider_id", "emotion", "跟随主模型"], ["behavior_provider_id", "behavior", "跟随主模型"],
  ["catchup_provider_id", "night", "跟随主模型"], ["closing_provider_id", "night", "跟随主模型"],
  ["diary_provider_id", "experience", "跟随主模型"], ["dream_provider_id", "experience", "跟随主模型"],
  ["embedding_provider_id", "memory", "未配置"],
];
const optionLabel = (key, value) => nativeDTO.config.fields.find(field => field.key === key)
  .options.find(option => option.value === value).label;
const { server, url } = await startServer();
const browser = await chromium.launch({ headless: true,
  ...(process.env.CHROME_PATH ? { executablePath: process.env.CHROME_PATH } : {}) });
const report = { layer: "isolated_browser", checks: [], errors: [], real_model_calls: 0, writes: 0 };
const check = (name, condition) => { assert.ok(condition, name); report.checks.push(name); };

function panelMetrics() {
  const panel = document.querySelector("[data-onboarding]");
  const box = panel.getBoundingClientRect();
  const outside = [...panel.querySelectorAll("*"), panel].filter(element => {
    const rect = element.getBoundingClientRect();
    return rect.width && (rect.right > box.right + 1 || rect.left < box.left - 1);
  }).map(element => String(element.className));
  const small = [...panel.querySelectorAll("button"), document.querySelector("#onboarding-toggle")]
    .filter(element => element.getBoundingClientRect().height < 23).length;
  const unnamed = [...panel.querySelectorAll("button")].filter(element => !element.textContent.trim() && !element.getAttribute("aria-label")).length;
  return { scrollWidth: document.documentElement.scrollWidth, innerWidth, outside, small, unnamed };
}
function panelContrast() {
  const rgb = string => {
    const nums = string.match(/[\d.]+/g)?.map(Number) || [0, 0, 0];
    return nums.length < 4 || nums[3] > 0 ? nums.slice(0, 3) : null;
  };
  const luminance = color => color.map(channel => channel / 255)
    .map(channel => channel <= .04045 ? channel / 12.92 : ((channel + .055) / 1.055) ** 2.4)
    .reduce((sum, channel, index) => sum + channel * [.2126, .7152, .0722][index], 0);
  const ratio = (a, b) => { const [high, low] = [luminance(a), luminance(b)].sort((x, y) => y - x); return (high + .05) / (low + .05); };
  const background = element => {
    while (element) { const color = rgb(getComputedStyle(element).backgroundColor); if (color) return color; element = element.parentElement; }
    return [255, 255, 255];
  };
  let textMin = Infinity, controlMin = Infinity;
  for (const root of document.querySelectorAll("#onboarding-toggle, [data-onboarding]")) {
    for (const element of root.querySelectorAll("*")) {
      const style = getComputedStyle(element), back = background(element);
      if ([...element.childNodes].some(node => node.nodeType === Node.TEXT_NODE && node.textContent.trim())) {
        textMin = Math.min(textMin, ratio(rgb(style.color), back));
      }
      if (element.matches("button")) for (const side of ["Top", "Bottom", "Left", "Right"]) {
        if (parseFloat(style[`border${side}Width`]) && style[`border${side}Style`] !== "none") {
          controlMin = Math.min(controlMin, ratio(rgb(style[`border${side}Color`]), background(element.parentElement)));
        }
      }
    }
  }
  return { textMin, controlMin };
}
function landed() {
  const open = [...document.querySelectorAll("[data-task-group]")].filter(section => !section.hidden);
  const rect = document.activeElement.getBoundingClientRect();
  return { groups: open.map(section => section.dataset.taskGroup), active: document.activeElement.id,
    jump: document.querySelector(`[data-settings-jump="${open[0]?.dataset.taskGroup}"]`)?.getAttribute("aria-expanded"),
    focusedTop: rect.top, focusedBottom: rect.bottom, innerHeight,
    panelOpen: !document.querySelector("#onboarding-panel").hidden,
    failures: document.querySelectorAll("[data-settings-error]").length };
}
function leafTexts() {
  const out = [];
  for (const root of document.querySelectorAll("#onboarding-toggle, [data-onboarding]")) {
    for (const walker = document.createTreeWalker(root, NodeFilter.SHOW_TEXT); walker.nextNode();) {
      const value = walker.currentNode.textContent.trim();
      if (value) out.push(value);
    }
  }
  return out;
}
async function open(width, theme) {
  const page = await browser.newPage({ viewport: { width, height: 900 }, reducedMotion: "reduce" });
  page.setDefaultTimeout(8000);
  page.on("pageerror", error => report.errors.push(error.message));
  page.on("console", message => { if (message.type() === "error") report.errors.push(message.text()); });
  page.on("dialog", dialog => dialog.type() === "beforeunload" ? dialog.accept() : dialog.dismiss());
  await page.route("**/*", route => new URL(route.request().url()).origin === new URL(url).origin ? route.continue() : route.abort());
  await page.clock.install();
  await page.goto(`${url}?scenario=native-dto`);
  await page.locator("#content[aria-busy=false]").waitFor();
  await page.locator(`[data-theme-choice="${theme}"]`).click();
  // 入口在顶栏：不先进设置页，确认在默认页签上就能打开。
  return page;
}
const stateReads = page => page.evaluate(() => window.__fixture.calls.filter(call => call.path === "console/state").length);
const badges = page => page.locator("[data-onboarding-step] > .status").allTextContents();
const rowStates = page => page.locator("[data-onboarding-key]").evaluateAll(rows =>
  rows.map(row => `${row.dataset.onboardingKey}=${row.querySelector(".onboarding-model-state").textContent}`));
async function settled(page, before) {
  await page.waitForFunction(count => window.__fixture.calls.filter(call => call.path === "console/state").length > count, before);
  await page.locator("#content[aria-busy=false]").waitFor();
  await page.clock.runFor(1);
}
// 模拟另一位管理员改了配置，再由页面重新读取；清单状态应原地更新。
async function changedTo(page, patch, revision, expected, name) {
  const before = await stateReads(page);
  await page.evaluate(([patch, revision]) => window.__fixture.changeConfig(patch, revision), [patch, revision]);
  await page.locator("#refresh").click();
  await settled(page, before);
  assert.deepEqual(await badges(page), expected, name);
  check(name, await page.locator("#onboarding-panel").evaluate(panel => panel.dataset.probe) === "kept");
}

try {
  for (const width of [1280, 390]) for (const theme of ["light", "dark"]) {
    const page = await open(width, theme);
    const tag = `${width}-${theme}`;
    const toggle = page.locator("#onboarding-toggle");
    const closed = await page.evaluate(() => document.documentElement.scrollWidth);
    check(`${tag} entry reachable without opening settings`, await toggle.isVisible() && !await page.locator("#settings").isVisible());
    check(`${tag} entry`, await toggle.count() === 1 && (await toggle.textContent()) === "新手引导" &&
      await toggle.getAttribute("aria-expanded") === "false" && !await page.locator("#onboarding-panel").isVisible());
    // 开关与「导出诊断日志」同一排、紧挨在它左边；面板占标题栏下方整行，不再挂在设置页里。
    check(`${tag} entry sits in the masthead row, left of diagnostics export`, await page.evaluate(() => {
      const toggle = document.querySelector("#onboarding-toggle"), panel = document.querySelector("#onboarding-panel");
      const row = document.querySelector(".header-controls"), masthead = document.querySelector(".masthead");
      const centers = [toggle, document.querySelector("#diagnosticsExport")]
        .map(element => { const rect = element.getBoundingClientRect(); return rect.top + rect.height / 2; });
      return toggle.parentElement === row && toggle.nextElementSibling?.id === "diagnosticsExport" &&
        Math.abs(centers[0] - centers[1]) < 4 && panel.previousElementSibling === masthead &&
        !row.contains(panel) && !document.querySelector("#settings").contains(panel);
    }));
    await toggle.click();
    check(`${tag} panel opens`, await toggle.getAttribute("aria-expanded") === "true" && await page.locator("#onboarding-panel").isVisible() &&
      await page.locator("[data-onboarding-step]").count() === 6);
    assert.deepEqual(await page.locator(".onboarding-text h3").allTextContents(), TITLES);
    assert.deepEqual(await badges(page), ["默认", "默认", "已配置", "默认", "默认", "默认"]);
    await toggle.click();
    check(`${tag} panel closes`, await toggle.getAttribute("aria-expanded") === "false" && !await page.locator("#onboarding-panel").isVisible());
    await toggle.click();
    await page.evaluate(() => { document.querySelector("#onboarding-panel").dataset.probe = "kept"; });

    // 九个模型键；留空的聊天模型跟随主模型，向量模型是未配置。
    const rows = page.locator("[data-onboarding-key]");
    check(`${tag} nine model rows`, await rows.count() === 9);
    assert.deepEqual(await rowStates(page), MODELS.map(([key, , state]) => `${key}=${state}`));
    for (const [key, group] of MODELS) {
      await page.locator(`[data-onboarding-key="${key}"]`).click();
      const result = await page.evaluate(landed);
      check(`${tag} row ${key} opens ${group}`, result.groups.join() === group && result.active === `config-${key}` &&
        result.jump === "true" && result.panelOpen && result.failures === 0);
    }
    // 每一步的「去设置」展开正确分区，并把焦点放到这一步的第一个相关字段。
    for (const [id, group, focus] of STEPS) {
      await page.locator(`[data-onboarding-step="${id}"] .onboarding-go`).click();
      const result = await page.evaluate(landed);
      check(`${tag} step ${id} opens ${group}`, result.groups.join() === group && result.active === focus &&
        result.jump === "true" && result.panelOpen && result.failures === 0 &&
        result.focusedTop >= -1 && result.focusedBottom <= result.innerHeight + 1);
    }
    const metrics = await page.evaluate(panelMetrics);
    check(`${tag} no new horizontal overflow`, metrics.scrollWidth <= Math.max(width, MINIMUM_CONSOLE_WIDTH) + 1 &&
      metrics.scrollWidth <= closed);
    check(`${tag} panel fits its box`, metrics.outside.length === 0);
    if (width === 390) {
      // 既有 body 最小宽度是 700px；临时去掉它，确认清单自身在真实的 390px 下也不溢出。
      const narrow = await page.evaluate(() => {
        document.body.style.minWidth = "0";
        const panel = document.querySelector("[data-onboarding]");
        const box = panel.getBoundingClientRect();
        const outside = [panel, ...panel.querySelectorAll("*")].filter(element => {
          const rect = element.getBoundingClientRect();
          return rect.width && (rect.right > box.right + 1 || rect.left < box.left - 1);
        }).length;
        const result = { right: box.right, inner: panel.scrollWidth <= panel.clientWidth + 1, outside };
        document.body.style.minWidth = "";
        return result;
      });
      check(`${tag} panel fits a true 390px page`, narrow.right <= width + 1 && narrow.inner && narrow.outside === 0);
    }
    check(`${tag} named controls at least 24px`, metrics.small === 0 && metrics.unnamed === 0);
    const contrast = await page.evaluate(panelContrast);
    check(`${tag} contrast`, contrast.textMin >= 4.5 && contrast.controlMin >= 3);

    // 自动刷新（60 秒）与切换页签重建 DOM 之后，清单仍保持展开。
    await page.locator('[data-settings-jump="persona"]').click();
    await settled(page, await stateReads(page) - 1);
    await page.clock.runFor(60001);
    await page.clock.runFor(1);
    await page.waitForFunction(() => window.__fixture.calls.filter(call => call.path === "console/state").length >= 2);
    check(`${tag} stays open after automatic refresh`, await toggle.getAttribute("aria-expanded") === "true" &&
      await page.locator("#onboarding-panel").isVisible() && await page.locator("[data-onboarding-step]").count() === 6);
    await page.locator('[data-section="overview"]').click();
    check(`${tag} stays open outside settings`, !await page.locator("#settings").isVisible() &&
      await page.locator("#onboarding-panel").isVisible());
    await page.locator('[data-section="experience"]').click();
    // 入口是全局的：日记页顶栏仍有且只有一个开关，设置区里不再重复出现清单。
    check(`${tag} single entry on diary settings`, await page.locator("#onboarding-toggle").count() === 1 &&
      await page.locator("#settings [data-onboarding], #settings #onboarding-toggle").count() === 0);
    await page.locator('[data-section="settings"]').click();
    check(`${tag} stays open after tab switch`, await toggle.getAttribute("aria-expanded") === "true" &&
      await page.locator("#onboarding-panel").isVisible() && await page.locator("[data-onboarding-step]").count() === 6);
    // 清单里的每句话都必须是对应 key 的登记译文，不能残留中文。
    await page.locator("#onboarding-toggle").scrollIntoViewIfNeeded();
    const chinese = await page.evaluate(leafTexts);
    const goLabels = await page.locator(".onboarding-go").evaluateAll(buttons => buttons.map(button => button.getAttribute("aria-label")));
    assert.deepEqual(goLabels, TITLES.map(title => `去设置：${title.slice(3)}`));
    for (const [language, index] of [["en", 0], ["ja", 1]]) {
      await page.locator("#language").selectOption(language);
      const translated = await page.evaluate(leafTexts);
      assert.equal(translated.length, chinese.length, `${tag} ${language} text count`);
      chinese.forEach((source, position) => {
        const numbered = source.match(/^(\d+\. )?(.*)$/), prefix = numbered[1] || "";
        assert.deepEqual(messages[numbered[2]]?.[index], translated[position].slice(prefix.length), `${tag} ${language} ${source}`);
        assert.ok(translated[position].startsWith(prefix), `${tag} ${language} numbering`);
      });
      if (language === "en") check(`${tag} en has no Chinese left`, !translated.concat(await page.locator(".onboarding-go")
        .evaluateAll(buttons => buttons.map(button => button.getAttribute("aria-label")))).some(value => /[\u4e00-\u9fff]/.test(value)));
      check(`${tag} ${language} stays open`, await toggle.getAttribute("aria-expanded") === "true" &&
        await page.locator("#onboarding-panel").isVisible() && await page.locator("[data-onboarding-step]").count() === 6);
    }
    await page.locator("#language").selectOption("zh-CN");
    // 线上模型名是「显示名 · 模型 ID」，与线上等长：标题和用途仍各占一行，模型名只在状态列内折行。
    await page.evaluate(() => {
      window.__fixture.renameOption("fixture-chat", "合成配置01名字1017 · deepseek-v4.1-flash");
      window.__fixture.changeConfig({ fallback_provider_id: "fixture-chat", behavior_provider_id: "fixture-chat" }, "onboarding-long");
    });
    const before = await stateReads(page);
    await page.locator("#refresh").click();
    await settled(page, before);
    // 英文的用途说明本来就按单词折行，只要求标题不折行。
    const tidy = singleLineUse => page.locator("[data-onboarding-key]").evaluateAll((rows, singleLineUse) => rows.map(row => {
      const oneLine = selector => { const element = row.querySelector(selector); return element.getBoundingClientRect().height <= parseFloat(getComputedStyle(element).lineHeight) + 1; };
      return oneLine(".onboarding-model-name") && (!singleLineUse || oneLine(".onboarding-model-use")) &&
        row.querySelector(".onboarding-model-state").getBoundingClientRect().right <= row.getBoundingClientRect().right + 1;
    }), singleLineUse);
    for (const [language, singleLineUse] of [["zh-CN", true], ["en", false]]) {
      if (language === "en") await page.locator("#language").selectOption(language);
      const layout = await tidy(singleLineUse);
      check(`${tag} long model names keep titles on one line (${language})`, layout.length === 9 && layout.every(Boolean));
    }
    await page.close();
  }

  // 状态标记：依据已保存的配置值原地更新，不重建清单。
  const page = await open(1280, "light");
  await page.locator("#onboarding-toggle").click();
  await page.evaluate(() => { document.querySelector("#onboarding-panel").dataset.probe = "kept"; });
  const fresh = ["默认", "默认", "已配置", "默认", "默认", "默认"];
  await changedTo(page, { timezone: "" }, "onboarding-1", ["默认", "默认", "默认", "默认", "默认", "默认"], "blank timezone is default");
  await changedTo(page, { allow_sleep: false }, "onboarding-2", ["默认", "默认", "已配置", "默认", "默认", "默认"], "sleep switched off is set up");
  await changedTo(page, { allow_sleep: true, relationship_edit_enabled: true }, "onboarding-3", ["默认", "已配置", "默认", "默认", "默认", "默认"], "affinity editing is set up");
  await changedTo(page, { relationship_edit_enabled: false, relationship_image_refusal_close: 20 }, "onboarding-4", ["默认", "已配置", "默认", "默认", "默认", "默认"], "refusal chance changed is set up");
  await changedTo(page, { relationship_image_refusal_close: 10, relationship_special_description: "主人" }, "onboarding-5", ["默认", "已配置", "默认", "默认", "默认", "默认"], "special relationship note is set up");
  await changedTo(page, { relationship_special_description: "", persona_mode: "explicit", persona_id: "fixture-persona" }, "onboarding-6", ["已配置", "默认", "默认", "默认", "默认", "默认"], "explicit persona is set up");
  await changedTo(page, { persona_mode: "follow", persona_id: "", tone_prompt_enabled: true }, "onboarding-7", ["默认", "默认", "默认", "已配置", "默认", "默认"], "plain prompt on is set up");
  await changedTo(page, { tone_prompt_enabled: false, prompt_core_enabled: false }, "onboarding-8", ["默认", "默认", "默认", "已配置", "默认", "默认"], "shared notes off is set up");
  await changedTo(page, { prompt_core_enabled: true, provider_id: "fixture-chat" }, "onboarding-9", ["默认", "默认", "默认", "默认", "默认", "已配置"], "main model chosen is set up");
  assert.deepEqual(await rowStates(page), MODELS.map(([key, , state]) =>
    `${key}=${key === "provider_id" ? optionLabel("provider_id", "fixture-chat") : state}`));
  await changedTo(page, { provider_id: "", embedding_provider_id: "fixture-embedding" }, "onboarding-10",
    ["默认", "默认", "默认", "默认", "默认", "已配置"], "embedding chosen is set up");
  assert.equal((await rowStates(page)).at(-1), `embedding_provider_id=${optionLabel("embedding_provider_id", "fixture-embedding")}`);
  await changedTo(page, { embedding_provider_id: "", timezone: "Asia/Shanghai" }, "onboarding-11", fresh, "defaults restored");

  // 本页保存后立即更新：通用说明开启、人物性格开启都算第 4 步已配置。
  await page.locator('[data-onboarding-step="prompts"] .onboarding-go').click();
  await page.locator("#config-character_prompt_enabled").check();
  await page.locator("#save").click();
  await page.getByText("已保存到原生配置。", { exact: true }).waitFor();
  await page.locator("#editor").waitFor({ state: "hidden" });
  assert.deepEqual(await badges(page), ["默认", "默认", "已配置", "已配置", "默认", "默认"]);
  check("save refreshes status in place", await page.locator("#onboarding-panel").evaluate(panel => panel.dataset.probe) === "kept");
  report.writes += 1;

  // 风格摘要不在配置值里：跟着编辑器自己的保存与恢复走。
  // 既有行为：自动或手动刷新后这个输入框会被禁用，重建设置页后才恢复可编辑。
  const rebuildSettings = async () => {
    await page.locator('[data-section="overview"]').click();
    await page.locator('[data-section="settings"]').click();
    await page.waitForFunction(() => document.querySelector(".style-summary-text")?.disabled === false);
  };
  await rebuildSettings();
  await page.locator('[data-onboarding-step="style"] .onboarding-go').click();
  await page.locator(".style-summary-text").fill("合成自定义风格");
  await page.getByRole("button", { name: "保存摘要", exact: true }).click();
  await page.clock.runFor(1);
  await page.waitForFunction(() => document.querySelector(".style-summary-text")?.dataset.custom === "true");
  assert.deepEqual(await badges(page), ["默认", "默认", "已配置", "已配置", "已配置", "默认"]);
  report.writes += 1;
  // 重建后编辑器重新读取：已保存的自定义摘要仍让第 5 步显示已配置。
  await rebuildSettings();
  assert.deepEqual(await badges(page), ["默认", "默认", "已配置", "已配置", "已配置", "默认"]);
  await page.getByRole("button", { name: "恢复默认", exact: true }).click();
  await page.clock.runFor(1);
  await page.waitForFunction(() => document.querySelector(".style-summary-text")?.dataset.custom === "false");
  assert.deepEqual(await badges(page), ["默认", "默认", "已配置", "已配置", "默认", "默认"]);
  report.writes += 1;
  await page.close();
  check("no page errors", report.errors.length === 0);
  report.success = true;
} catch (error) {
  report.success = false; report.failure = error.stack; process.exitCode = 1;
} finally {
  console.log(JSON.stringify(report));
  await browser.close();
  await new Promise(resolve => server.close(resolve));
}
