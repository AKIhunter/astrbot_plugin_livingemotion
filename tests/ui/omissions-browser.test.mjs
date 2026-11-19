/* Offline bridge replay: no providers, transport or production data writes. */
import assert from "node:assert/strict";
import { createRequire } from "node:module";
import { writeFile } from "node:fs/promises";
import { startServer } from "./server.mjs";

const { chromium } = createRequire(import.meta.url)(process.env.PW_MODULE || "playwright");
const { server, url } = await startServer();
const browser = await chromium.launch({
  headless: true, ...(process.env.CHROME_PATH ? { executablePath: process.env.CHROME_PATH } : {}),
  args: ["--disable-background-networking", "--disable-sync", "--no-first-run",
    "--proxy-server=http://127.0.0.1:9", "--proxy-bypass-list=127.0.0.1;localhost"],
});
const report = { layer: "isolated_bridge_replay", checks: [], errors: [], layouts: [] };
const check = (name, value) => { assert.ok(value, name); report.checks.push({ name, passed: true }); };
const reads = page => page.evaluate(() => window.__fixture.calls.filter(c => c.path === "console/state").length);
async function open(scenario = "normal") {
  const page = await browser.newPage({ viewport: { width: 1440, height: 1100 }, reducedMotion: "reduce" });
  await page.route("**/*", route => new URL(route.request().url()).origin === new URL(url).origin
    ? route.continue() : route.abort());
  page.on("pageerror", error => report.errors.push(error.message));
  await page.clock.install();
  await page.goto(`${url}?scenario=${scenario}`);
  await page.locator("#content[aria-busy=false]").waitFor();
  await page.evaluate(() => {
    const bridge = window.AstrBotPluginView, original = bridge.apiGet.bind(bridge);
    window.__emotionProbe = { mode: "scoped", ticks: 0 };
    bridge.apiGet = async (path, params) => {
      const response = await original(path, params);
      if (path !== "console/state") return response;
      const data = response.data, probe = window.__emotionProbe;
      data.updated_at = 1800000000 + ++probe.ticks;
      data.emotion_analysis = { bot: { emotions: { joy: .6, anger: .1, sadness: 0,
        fear: .2, surprise: .3, affection: .4, wronged: .99 } } };
      data.context_emotions = { version: 1, enabled: true, scope_kind: "account",
        context_id: data.context_id, target: "10001",
        emotions: { wronged: .125, hurt: 0, shyness: .08 } };
      if (probe.mode === "global") {
        data.context_id = ""; data.context_emotions.context_id = "";
        data.context_emotions.target = "";
      }
      if (probe.mode === "mismatch") data.context_emotions.context_id = "other-context";
      if (probe.mode === "missing") data.context_emotions.emotions = {};
      if (probe.mode === "disabled") data.context_emotions.enabled = false;
      if (!data.config.fields.some(f => f.key === "context_emotions_enabled")) {
        data.config.values.context_emotions_enabled = true;
        data.config.fields.push({ key: "context_emotions_enabled", type: "boolean",
          label: "委屈、受伤与害羞", section: "emotion", level: 0, parent: "",
          help: "开启后采集；在设置 → 情绪设置。关闭后不采集。" });
        data.config.groups.find(g => g.id === "emotion").field_keys.push("context_emotions_enabled");
      }
      return response;
    };
  });
  return page;
}
async function poll(page) {
  const before = await reads(page);
  await page.clock.fastForward(60001);
  await page.waitForFunction(n => window.__fixture.calls.filter(c => c.path === "console/state").length > n, before);
  await page.locator("#content[aria-busy=false]").waitFor();
}
async function rememberInput(page, selector, start = 2, end = 4) {
  await page.locator(selector).focus();
  await page.locator(selector).evaluate((el, range) => {
    window.__draftNode = el;
    if (el.setSelectionRange && el.tagName !== "SELECT") el.setSelectionRange(...range);
  }, [start, end]);
}
async function preserved(page, selector, value, selection = true) {
  check(selector + "_draft", await page.locator(selector).inputValue() === value);
  check(selector + "_dom_focus_selection", await page.locator(selector).evaluate((el, ranged) =>
    el === window.__draftNode && document.activeElement === el &&
    (!ranged || el.selectionStart === 2 && el.selectionEnd === 4), selection));
}
try {
  let page = await open("save-fast");
  await page.locator('[data-section="settings"]').click();
  await page.locator("#config-home_city").fill("未保存的城市");
  await rememberInput(page, "#config-home_city");
  await poll(page);
  await preserved(page, "#config-home_city", "未保存的城市");
  check("settings_read_advances_while_focused", await page.evaluate(() => window.__emotionProbe.ticks > 0));
  await page.close();

  page = await open();
  await page.locator('[data-section="behavior"]').click();
  await page.locator('[data-operation="behavior.simulate"]').click();
  const options = await page.locator("#simulation-emotion option").evaluateAll(items => items.map(item => item.value));
  check("simulation_all_twelve", options.length === 12 &&
    ["disgust", "affection", "wronged", "hurt", "shyness"].every(v => options.includes(v)));
  await page.locator("#simulation-emotion").selectOption("hurt");
  await rememberInput(page, "#simulation-emotion");
  await poll(page);
  await preserved(page, "#simulation-emotion", "hurt", false);
  check("simulation_dialog_remains_open", await page.locator("#behavior-simulation-dialog").evaluate(el => el.open));
  check("focused_dialog_does_not_generate", await page.evaluate(() =>
    !window.__fixture.calls.some(c => c.path === "console/behavior-simulate")));
  await page.close();

  page = await open("relationship-conflict");
  await page.locator('[data-section="relationships"]').click();
  await page.locator(".relationship-table tbody tr").first().getByRole("button", { name: "编辑", exact: true }).click();
  await page.locator("#relationship-affinity").fill("64.5");
  await page.locator("#relationship-note").fill("保留未保存的关系备注");
  await page.locator("#relationship-frozen").check();
  await rememberInput(page, "#relationship-note");
  await poll(page);
  await page.locator("#relationship-body[aria-busy=false]").waitFor();
  await preserved(page, "#relationship-note", "保留未保存的关系备注");
  check("relationship_score_and_freeze_preserved",
    await page.locator("#relationship-affinity").inputValue() === "64.5" &&
    await page.locator("#relationship-frozen").isChecked());
  await page.getByRole("button", { name: "保存基础信息", exact: true }).click();
  await page.getByText("关系版本已变化。草稿保留，请读取最新关系并人工复核；未自动重试。", { exact: true }).waitFor();
  check("relationship_original_cas", await page.evaluate(() =>
    window.__fixture.calls.find(c => c.path === "console/relationship").payload.expected_version === 0));
  await page.getByRole("button", { name: "读取最新关系并复核", exact: true }).click();
  await page.locator("#relationship-body[aria-busy=false]").waitFor();
  check("explicit_review_preserves_draft", await page.locator("#relationship-note").inputValue() === "保留未保存的关系备注");
  check("explicit_review_unlocks_save", await page.getByRole("button", { name: "保存基础信息", exact: true }).isEnabled());
  await page.getByRole("button", { name: "保存基础信息", exact: true }).click();
  await page.locator(".relationship-row-editor").waitFor({ state: "hidden" });
  check("explicit_review_adopts_latest_cas", await page.evaluate(() =>
    window.__fixture.calls.filter(c => c.path === "console/relationship").at(-1).payload.expected_version === 1));
  await page.close();

  page = await open();
  await poll(page);
  check("concrete_context_picker_exists", await page.locator("#context-emotion-picker").count() === 1);
  await page.locator("#context-emotion-picker").selectOption("fixture-a");
  await page.waitForFunction(() => window.__fixture.calls.some(c => c.path === "console/state" &&
    c.payload.context_id === "fixture-a" && c.payload.view_scope === "private"));
  await page.locator("#content[aria-busy=false]").waitFor();
  check("concrete_context_picker_requests_scope", await page.locator("#context-emotion-picker").inputValue() === "fixture-a");
  const values = () => page.locator(".ta-emotion-stem-button").evaluateAll(rows =>
    Object.fromEntries(rows.map(el => [el.dataset.emotion, el.dataset.value])));
  let measured = await values();
  check("context_raw_values_below_threshold", measured.wronged === "0.125" && measured.shyness === "0.08");
  check("measured_zero_distinct_from_missing", measured.hurt === "0");
  for (const mode of ["global", "mismatch", "missing", "disabled"]) {
    await page.evaluate(mode => { window.__emotionProbe.mode = mode; }, mode);
    await poll(page);
    measured = await values();
    check(mode + "_does_not_leak_or_fill_zero", ["wronged", "hurt", "shyness"].every(k => measured[k] === "uncollected"));
  }
  await page.evaluate(() => { window.__emotionProbe.mode = "scoped"; });
  await poll(page);
  for (const width of [960, 1280, 1440]) {
    await page.setViewportSize({ width, height: 1100 });
    for (const theme of ["light", "dark"]) {
      await page.locator(`[data-theme-choice="${theme}"]`).click();
      for (const lang of ["zh-CN", "en", "ja"]) {
        await page.locator("#language").selectOption(lang);
        const result = await page.evaluate(theme => {
          const key = theme === "light" ? ".ta-emotion-stem-label" : ".ta-emotion-pixel-row > span:first-child";
          const rects = [...document.querySelectorAll(key)].map(el => el.getBoundingClientRect());
          return { overflow: document.documentElement.scrollWidth > innerWidth + 1,
            overlap: theme === "light" && rects.some((r, i) => i && r.left < rects[i - 1].right - 1),
            font: getComputedStyle(document.querySelector(key)).fontSize };
        }, theme);
        check(`layout_${width}_${theme}_${lang}`, !result.overflow && !result.overlap && Number.parseFloat(result.font) >= 16);
        report.layouts.push({ width, theme, lang, ...result });
      }
    }
  }
  await page.close();
  check("no_page_errors", report.errors.length === 0);
  report.success = true;
} catch (error) {
  report.success = false; report.failure = error.stack; process.exitCode = 1;
} finally {
  if (process.env.LE_UI_REPORT) await writeFile(process.env.LE_UI_REPORT, JSON.stringify(report, null, 2));
  console.log(JSON.stringify(report));
  await browser.close();
  await new Promise(resolve => server.close(resolve));
}
