// Real Dashboard login + native iframe/SDK; no synthetic bridge or API responses.
import assert from "node:assert/strict";
import { createRequire } from "node:module";
import { readFile, writeFile, mkdir } from "node:fs/promises";
import path from "node:path";
const require = createRequire(import.meta.url);
const { chromium } = require(process.env.PLAYWRIGHT_MODULE || "/tmp/at-guard-ui-tools/node_modules/playwright");
const root = process.argv[2];
const ready = JSON.parse(await readFile(path.join(root, "browser-ready.json"), "utf8"));
const evidence = path.join(root, "browser-evidence");
await mkdir(evidence, { recursive: true });
const browser = await chromium.launch({
  headless: true,
  executablePath: process.env.CHROME_PATH || "/Applications/Google Chrome.app/Contents/MacOS/Google Chrome",
  args: ["--disable-background-networking", "--disable-component-update"],
});
const report = { scope: "real Dashboard bundle + real product, synthetic users/messages, no model/provider",
  browser: browser.version(), node: process.version, checks: [], layouts: [], contrast: [],
  apiResponses: [], pageErrors: [], blockedExternal: [], screenshots: [] };
function check(name, value, detail) {
  report.checks.push({ name, passed: !!value, ...(detail === undefined ? {} : { detail }) });
}
async function test(name, fn) {
  try { await fn(); check(name, true); }
  catch (error) { check(name, false, error.message.replace(/\/_t\/[^/]+/g, "/_t/[REDACTED]").slice(0, 800)); }
}
const context = await browser.newContext({
  viewport: { width: 1280, height: 900 }, colorScheme: "dark", reducedMotion: "reduce",
});
await context.route("**/*", route => {
  const url = new URL(route.request().url());
  if (url.origin === ready.base_url) return route.continue();
  report.blockedExternal.push({ host: url.hostname, type: route.request().resourceType() });
  return route.abort();
});
const page = await context.newPage();
page.setDefaultTimeout(12000);
page.on("pageerror", error => report.pageErrors.push(error.message.slice(0, 300)));
page.on("dialog", dialog => dialog.type() === "beforeunload" ? dialog.accept() : dialog.dismiss());
page.on("response", response => {
  const url = new URL(response.url());
  if (url.pathname.includes("/console/")) report.apiResponses.push({
    method: response.request().method(), endpoint: url.pathname.split("/").at(-1), status: response.status(),
  });
});
let frame;
async function getFrame() {
  await page.locator("iframe").waitFor({ state: "visible" });
  const handle = await page.locator("iframe").elementHandle();
  const result = await handle.contentFrame();
  await result.locator("#content[aria-busy=false]").waitFor();
  assert.ok(!(await result.locator("#connection").innerText()).includes("连接失败"));
  return result;
}
async function section(name) {
  await frame.locator(`[data-section="${name}"]`).focus();
  await page.keyboard.press("Enter");
  await frame.waitForFunction(n => document.querySelector(`[data-section="${n}"]`)?.getAttribute("aria-current") === "page", name);
  if (["emotion", "behavior", "experience"].includes(name)) {
    await frame.locator("#record-body[aria-busy=false]").waitFor();
  }
}
function inspect() {
  const visible = el => el.checkVisibility({ checkVisibilityCSS: true }) && el.getBoundingClientRect().width > 0;
  const rgb = text => {
    const values = text.match(/[\d.]+/g)?.map(Number);
    return values && (values.length < 4 || values[3] > 0) ? values.slice(0, 3) : null;
  };
  const bg = el => {
    while (el) {
      const color = rgb(getComputedStyle(el).backgroundColor);
      if (color) return color;
      el = el.parentElement;
    }
    return [255, 255, 255];
  };
  const luminance = color => color.map(x => x / 255).map(x => x <= .04045 ? x / 12.92 : ((x + .055) / 1.055) ** 2.4)
    .reduce((s, x, i) => s + x * [.2126, .7152, .0722][i], 0);
  const ratio = (a, b) => {
    const values = [luminance(a), luminance(b)].sort((x, y) => y - x);
    return (values[0] + .05) / (values[1] + .05);
  };
  const texts = [], controls = [], buttons = [];
  for (const el of document.querySelectorAll("body *")) {
    if (!(el instanceof HTMLElement) || !visible(el)) continue;
    const style = getComputedStyle(el);
    if ([...el.childNodes].some(n => n.nodeType === Node.TEXT_NODE && n.textContent.trim())
        || el.matches("input,select,textarea")) texts.push(ratio(rgb(style.color), bg(el)));
    if (el.matches("button,input,select,textarea") && parseFloat(style.borderTopWidth))
      controls.push(ratio(rgb(style.borderTopColor), bg(el.parentElement)));
    if (el.matches("button")) {
      const rect = el.getBoundingClientRect();
      buttons.push({ labeled: !!(el.textContent.trim() || el.getAttribute("aria-label")),
        height: rect.height, left: rect.left, right: rect.right });
    }
  }
  return { width: innerWidth, scrollWidth: document.documentElement.scrollWidth,
    theme: document.documentElement.dataset.leTheme,
    textMin: Math.min(...texts), controlMin: Math.min(...controls),
    textCount: texts.length, controlCount: controls.length,
    unlabeled: buttons.filter(x => !x.labeled).length,
    shortButtons: buttons.filter(x => x.height < 43.9).length };
}
try {
  await test("C44.real_login_and_iframe_bridge", async () => {
    await page.goto(ready.base_url + "/#/auth/login");
    await page.locator('input[name="username"]').fill(ready.username);
    await page.locator('input[name="password"]').fill(ready.password);
    await page.locator('button[type="submit"]').click();
    await page.waitForURL(url => !url.href.includes("/auth/"), { timeout: 20000 });
    await page.goto(ready.base_url + "/#/plugin-view/astrbot_plugin_livingemotion/livingemotion");
    // Dismiss the host's asynchronous first-use notice by its actual UI button.
    const notice = page.getByRole("dialog");
    await notice.waitFor({ state: "visible", timeout: 20000 });
    await notice.getByRole("button", { name: /关闭|Close/i }).last().click();
    await notice.waitFor({ state: "hidden" });
    check("host_first_notice_dismissed_by_ui", true);
    frame = await getFrame();
    assert.ok((await frame.locator("#context option").count()) > 0);
    assert.ok(await frame.locator("#content").getByText("Bot", { exact: false }).count());
    assert.ok(report.apiResponses.some(x => x.endpoint === "state" && x.status === 200));
    const sdk = await frame.locator('script[src*="bridge-sdk"]').getAttribute("src");
    assert.ok(sdk.includes("asset_token=") || sdk.includes("/_t/"));
  });
  if (frame) {
    check("C65.system_dark_initial", await frame.locator("html").getAttribute("data-le-theme") === "dark");
    const beforeThemes = report.apiResponses.length;
    for (const width of [390, 1280]) {
      await page.setViewportSize({ width, height: width === 390 ? 844 : 900 });
      // The native sidebar animates its breakpoint; measure the settled iframe.
      await frame.waitForFunction(w => innerWidth === w, width === 390 ? 390 : 1027);
      for (const theme of ["light", "dark"]) {
        await frame.locator(`[data-theme-choice="${theme}"]`).focus();
        await page.keyboard.press("Enter");
        await frame.waitForFunction(t => document.documentElement.dataset.leTheme === t, theme);
        for (const name of ["overview", "persona", "emotion", "behavior", "night", "experience", "memory"]) {
          await test(`C47.C65.layout_${width}_${theme}_${name}`, async () => {
            await section(name);
            if (name !== "overview") await frame.locator("#settings summary").click();
            const measure = await frame.evaluate(inspect);
            report.layouts.push({ parentWidth: width, expectedTheme: theme, section: name, ...measure });
            assert.equal(measure.theme, theme);
            assert.ok(measure.scrollWidth <= measure.width + 1);
            assert.equal(measure.unlabeled, 0);
            assert.equal(measure.shortButtons, 0);
            assert.ok(measure.textMin >= 4.5, `text contrast ${measure.textMin}`);
            assert.ok(measure.controlMin >= 3, `control contrast ${measure.controlMin}`);
            if (name === "overview") {
              const filename = `${width}-${theme}-dashboard.png`;
              await page.screenshot({ path: path.join(evidence, filename), fullPage: true });
              report.screenshots.push(filename);
            }
          });
          if (name === "overview") {
            await test(`F13.reply_confirmation_visible_${width}_${theme}`, async () => {
              const row = frame.locator("#content .health-row").filter({
                has: frame.getByText("reply_confirmation", { exact: true }),
              });
              assert.equal(await row.count(), 1);
              await row.scrollIntoViewIfNeeded();
              assert.ok(await row.isVisible());
              const status = row.locator(".status");
              assert.ok(await status.isVisible());
              assert.equal(await status.innerText(), "不可用");
              const hint = row.locator(".hint");
              assert.ok(await hint.isVisible());
              const reason = await hint.innerText();
              for (const part of ["unsupported", "当前宿主无可靠回复确认",
                "收尾 120 秒超时取消", "不将 after-sent/bool/None 视为发送成功"]) {
                assert.ok(reason.includes(part), `missing reply confirmation explanation: ${part}`);
              }
            });
          }
        }
      }
    }
    check("C65.theme_and_navigation_no_business_write",
          !report.apiResponses.slice(beforeThemes).some(x => x.method !== "GET"));
    await test("C47.keyboard_navigation", async () => {
      await frame.locator('[data-section="overview"]').focus();
      await page.keyboard.press("ArrowDown");
      await page.keyboard.press("Enter");
      assert.equal(await frame.locator('[aria-current="page"]').getAttribute("data-section"), "persona");
      const focus = await frame.evaluate(() => {
        const style = getComputedStyle(document.activeElement);
        return { width: parseFloat(style.outlineWidth), color: style.outlineColor };
      });
      check("C47.visible_focus", focus.width >= 2, focus);
    });
    await test("C65.native_storage_unavailable_refresh_fallback", async () => {
      await frame.locator('[data-theme-choice="light"]').focus();
      await page.keyboard.press("Enter");
      await frame.waitForFunction(() => document.documentElement.dataset.leTheme === "light");
      assert.equal(await frame.locator("#theme-status").innerText(), "仅本次页面有效");
      check("C65.native_iframe_storage_unavailable", true,
            await page.locator("iframe").getAttribute("sandbox"));
      await page.reload();
      frame = await getFrame();
      assert.equal(await frame.locator("html").getAttribute("data-le-theme"), "dark");
    });
    await test("C48.preview_real_bridge_no_send", async () => {
      await section("behavior");
      const before = report.apiResponses.length;
      const response = page.waitForResponse(r => r.url().includes("/console/preview") && r.status() === 200);
      await frame.getByRole("button", { name: /模拟/ }).click();
      await response;
      const responses = report.apiResponses.slice(before);
      assert.ok(responses.some(x => x.endpoint === "preview" && x.status === 200));
      assert.ok(!responses.some(x => x.endpoint === "action"));
    });
    await test("C45.real_records_ten_and_collapsed", async () => {
      await section("emotion");
      const value = await frame.evaluate(() => ({
        rows: document.querySelectorAll("#record-body .record").length,
        open: document.querySelectorAll("#record-body details[open]").length,
        details: document.querySelectorAll("#record-body details").length,
      }));
      assert.equal(value.open, 0);
      assert.equal(value.rows, 10);
      check("C45.record_details_exist", value.details > 0, value);
    });
    await test("C45.browser_config_save_refresh", async () => {
      await section("memory");
      await frame.locator("#settings summary").click();
      await frame.locator('[data-key="memory_mode"]').selectOption("local_lite");
      await frame.locator("#change-reason").fill("Synthetic browser acceptance.");
      const response = page.waitForResponse(r => r.url().includes("/console/config") && r.status() === 200);
      await frame.locator("#save").click();
      await response;
      await frame.locator("#editor").waitFor({ state: "hidden" });
      await page.reload();
      frame = await getFrame();
      await section("memory");
      await frame.locator("#settings summary").click();
      assert.equal(await frame.locator('[data-key="memory_mode"]').inputValue(), "local_lite");
    });
  }
} catch (error) {
  check("browser_suite_completed", false, error.name);
  report.visibleDialogs = await page.getByRole("dialog").allTextContents();
} finally {
  report.counts = { passed: report.checks.filter(x => x.passed).length, failed: report.checks.filter(x => !x.passed).length };
  await writeFile(path.join(evidence, "results.json"), JSON.stringify(report, null, 2));
  await browser.close();
  console.log(JSON.stringify({ browser: report.counts, layouts: report.layouts.length,
    pageErrors: report.pageErrors.length, blockedExternal: report.blockedExternal.length }));
}
process.exitCode = report.counts.failed ? 2 : 0;
