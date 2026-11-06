import assert from "node:assert/strict";
import { createRequire } from "node:module";
import { mkdir, readFile, writeFile } from "node:fs/promises";
import { createHash } from "node:crypto";
import { fileURLToPath } from "node:url";
import os from "node:os";
import { startServer } from "./server.mjs";
import { ATTACK } from "./fixtures.mjs";

const require = createRequire(import.meta.url);
const { chromium } = require(process.env.PLAYWRIGHT_MODULE || "playwright");
const { server, url } = await startServer();
const evidence = new URL("./evidence/", import.meta.url);
await mkdir(evidence, { recursive: true });
const browser = await chromium.launch({
  headless: true,
  ...(process.env.CHROME_PATH ? { executablePath: process.env.CHROME_PATH } : {}),
});
const report = {
  environment: { os: `${os.platform()} ${os.release()}`, arch: os.arch(), node: process.version, browser: browser.version() },
  scope: "纯合成 fixture；无生产调用；不证明宿主鉴权与后端业务接线",
  cases: [], layouts: [], contrast: [], pageErrors: [], externalRequests: [], screenshots: [],
};
report.source_sha256 = {};
for (const name of ["index.html", "theme.js", "style.css", "app.mjs", "api.mjs", "model.mjs"]) {
  const source = await readFile(new URL(`../../pages/livingemotion/${name}`, import.meta.url));
  report.source_sha256[name] = createHash("sha256").update(source).digest("hex");
}
const navigation = ["overview", "persona", "emotion", "behavior", "night", "experience", "memory"];
async function open(scenario = "normal", options = {}, init) {
  const context = await browser.newContext({ viewport: { width: 1280, height: 900 }, colorScheme: "light", reducedMotion: "reduce", ...options });
  if (init) await context.addInitScript(init);
  const page = await context.newPage();
  page.on("pageerror", error => report.pageErrors.push({ scenario, message: error.message }));
  page.on("dialog", dialog => dialog.type() === "beforeunload" ? dialog.accept() : dialog.dismiss());
  await page.route("**/*", route => {
    if (new URL(route.request().url()).origin === new URL(url).origin) return route.continue();
    report.externalRequests.push(route.request().url()); return route.abort();
  });
  await page.goto(`${url}?scenario=${scenario}`);
  await page.locator("#content[aria-busy=false]").waitFor();
  return { context, page };
}
async function section(page, name) {
  await page.locator(`[data-section="${name}"]`).click();
  if (["emotion", "behavior", "experience"].includes(name)) await page.locator("#record-body[aria-busy=false]").waitFor();
}
async function caseRun(name, task) {
  try { await task(); report.cases.push({ name, passed: true }); console.log(`通过：${name}`); }
  catch (error) { report.cases.push({ name, passed: false, error: error.message }); console.error(`失败：${name}：${error.message}`); }
}
async function shot(page, name) {
  await page.screenshot({ path: fileURLToPath(new URL(name, evidence)), fullPage: true });
  report.screenshots.push(name);
}
async function measure(page, theme, component) {
  const measured = await page.evaluate(inspectContrast);
  report.contrast.push({ width: await page.evaluate(() => innerWidth), theme, component, ...measured });
  assert.ok(measured.textMin >= 4.5, `${theme}/${component} 正文对比度 ${measured.textMin}`);
  assert.ok(measured.controlMin >= 3, `${theme}/${component} 控件对比度 ${measured.controlMin}`);
  assert.ok(measured.focusMin >= 3);
}
function inspectContrast() {
  const rgb = string => {
    const nums = string.match(/[\d.]+/g)?.map(Number) || [0, 0, 0];
    return nums.length < 4 || nums[3] > 0 ? nums.slice(0, 3) : null;
  };
  const luminance = color => color.map(channel => channel / 255).map(channel => channel <= .04045 ? channel / 12.92 : ((channel + .055) / 1.055) ** 2.4)
    .reduce((sum, channel, i) => sum + channel * [.2126, .7152, .0722][i], 0);
  const ratio = (a, b) => {
    const [high, low] = [luminance(a), luminance(b)].sort((x, y) => y - x);
    return (high + .05) / (low + .05);
  };
  const background = element => {
    while (element) {
      const color = rgb(getComputedStyle(element).backgroundColor);
      if (color) return color;
      element = element.parentElement;
    }
    return [255, 255, 255];
  };
  const visible = element => element.checkVisibility({ checkVisibilityCSS: true }) && element.getBoundingClientRect().width > 0;
  const texts = [], borders = [];
  for (const element of document.querySelectorAll("body *")) {
    if (!(element instanceof HTMLElement) || !visible(element)) continue;
    const style = getComputedStyle(element);
    const hasText = [...element.childNodes].some(child => child.nodeType === Node.TEXT_NODE && child.textContent.trim());
    if (hasText || element.matches("input,select,textarea")) {
      const color = rgb(style.color);
      if (color) texts.push({ ratio: ratio(color, background(element)), tag: element.tagName, class: element.className });
    }
    if (element.matches("button,input,select,textarea")) {
      for (const side of ["Top", "Bottom", "Left", "Right"]) {
        const color = rgb(style[`border${side}Color`]);
        if (parseFloat(style[`border${side}Width`]) && color && style[`border${side}Style`] !== "none") {
          borders.push({ ratio: ratio(color, background(element.parentElement)), tag: element.tagName });
        }
      }
    }
  }
  // Semantic focus/graph tokens are checked against every surface they touch.
  const css = getComputedStyle(document.documentElement);
  const hex = name => {
    const value = css.getPropertyValue(name).trim();
    return value.startsWith("#") ? [1, 3, 5].map(index => parseInt(value.slice(index, index + 2), 16)) : null;
  };
  const tokens = {};
  for (const name of ["--bg", "--surface", "--subtle", "--accent-bg", "--focus", "--accent"]) tokens[name] = hex(name);
  const focus = ["--bg", "--surface", "--subtle", "--accent-bg"].map(name => ratio(tokens["--focus"], tokens[name]));
  return {
    textMin: Math.min(...texts.map(item => item.ratio)), controlMin: Math.min(...borders.map(item => item.ratio)),
    focusMin: Math.min(...focus), textCount: texts.length, controlEdges: borders.length,
    failures: texts.filter(item => item.ratio < 4.5).slice(0, 5),
    borderFailures: borders.filter(item => item.ratio < 3).slice(0, 5),
  };
}

try {
  await caseRun("双主题 × 390/1280 × 七区布局、正文与控件对比度", async () => {
    for (const width of [1280, 390]) {
      const { context, page } = await open("normal", { viewport: { width, height: width === 390 ? 844 : 900 } });
      for (const theme of ["light", "dark"]) {
        await page.locator(`[data-theme-choice="${theme}"]`).click();
        for (const name of navigation) {
          await section(page, name);
          const metrics = await page.evaluate(() => ({
            width: innerWidth, scrollWidth: document.documentElement.scrollWidth,
            navigationCount: document.querySelectorAll("[data-section]").length,
            unnamed: [...document.querySelectorAll("button")].filter(button => button.checkVisibility() && !button.textContent.trim() && !button.getAttribute("aria-label")).length,
            small: [...document.querySelectorAll("button,input,select,summary")].filter(element => element.checkVisibility() &&
              element.getAttribute("type") !== "checkbox" && element.getBoundingClientRect().height < 43).length,
          }));
          report.layouts.push({ width, theme, section: name, ...metrics });
          assert.ok(metrics.scrollWidth <= width, `${width}/${theme}/${name} 页面横向溢出`);
          assert.equal(metrics.unnamed, 0); assert.equal(metrics.small, 0); assert.equal(metrics.navigationCount, 7);
          const contrast = await page.evaluate(inspectContrast);
          report.contrast.push({ width, theme, section: name, ...contrast });
          assert.ok(contrast.textMin >= 4.5, `${theme}/${name} 正文对比度 ${contrast.textMin} ${JSON.stringify(contrast.failures)}`);
          assert.ok(contrast.controlMin >= 3, `${theme}/${name} 控件对比度 ${contrast.controlMin}`);
          assert.ok(contrast.focusMin >= 3, `${theme}/${name} 焦点对比度 ${contrast.focusMin}`);
          if (name === "overview") await shot(page, `${width}-${theme}-overview.png`);
          if (name === "emotion" && width === 390) await shot(page, `${width}-${theme}-emotion.png`);
        }
      }
      await context.close();
    }
  });
  await caseRun("首帧系统偏好、手动持久化、存储失败仍切换与减少动效", async () => {
    for (const colorScheme of ["dark", "light"]) {
      const { context, page } = await open("normal", { colorScheme }, () => {
        document.addEventListener("DOMContentLoaded", () => { window.__themeAtReady = document.documentElement.dataset.leTheme; }, { once: true });
      });
      assert.equal(await page.locator("html").getAttribute("data-le-theme"), colorScheme);
      assert.equal(await page.evaluate(() => window.__themeAtReady), colorScheme);
      const opposite = colorScheme === "dark" ? "light" : "dark";
      await page.locator(`[data-theme-choice="${opposite}"]`).click();
      await page.reload(); await page.locator("#content[aria-busy=false]").waitFor();
      assert.equal(await page.locator("html").getAttribute("data-le-theme"), opposite);
      assert.equal(await page.evaluate(() => matchMedia("(prefers-reduced-motion: reduce)").matches), true);
      await context.close();
    }
    const { context, page } = await open("normal", { colorScheme: "dark" }, () => {
      Object.defineProperty(window, "localStorage", { get() { throw new DOMException("blocked", "SecurityError"); } });
      Object.defineProperty(window, "sessionStorage", { get() { throw new DOMException("blocked", "SecurityError"); } });
    });
    await page.locator('[data-theme-choice="light"]').click();
    assert.equal(await page.locator("html").getAttribute("data-le-theme"), "light");
    assert.equal(await page.locator("#theme-status").textContent(), "仅本次页面有效");
    await section(page, "memory");
    assert.equal(await page.locator("html").getAttribute("data-le-theme"), "light");
    await context.close();
  });
  await caseRun("每页10条、筛选与刷新保留、主题不改业务或触发请求", async () => {
    const { context, page } = await open();
    await section(page, "emotion");
    assert.equal(await page.locator("#record-body > article").count(), 10);
    await page.locator("#record-body").getByRole("button", { name: "下一页" }).click();
    await page.locator('[data-record-id="fixture-emotion-11"]').waitFor();
    assert.equal(await page.evaluate(() => document.activeElement.textContent), "下一页");
    await page.locator("#record-query").fill("fixture-source-2");
    await page.locator("#records").getByRole("button", { name: "筛选", exact: true }).click();
    await page.locator("#record-body[aria-busy=false]").waitFor();
    const count = await page.locator("#record-body > article").count();
    assert.equal(count, 5);
    const before = await page.evaluate(() => ({ calls: window.__fixture.calls.length, config: window.__fixture.state.config }));
    await page.locator('[data-theme-choice="dark"]').click();
    const after = await page.evaluate(() => ({ calls: window.__fixture.calls.length, config: window.__fixture.state.config }));
    assert.deepEqual(after, before);
    assert.equal(await page.locator("#record-query").inputValue(), "fixture-source-2");
    await page.reload(); await page.locator("#record-body[aria-busy=false]").waitFor();
    assert.equal(await page.locator("#record-query").inputValue(), "fixture-source-2");
    assert.equal(await page.locator("#record-body > article").count(), count);
    assert.equal(await page.locator("#record-body details[open]").count(), 0);
    await context.close();
  });
  await caseRun("原生配置草稿、409冲突复核、保存仅发patch与版本", async () => {
    const { context, page } = await open("conflict");
    await section(page, "emotion");
    await page.locator("#settings summary").click();
    await page.getByLabel("工作模式", { exact: true }).selectOption("active");
    await page.locator("#change-reason").fill("合成验证：切换模式");
    await page.locator('[data-theme-choice="dark"]').click();
    assert.equal(await page.getByLabel("工作模式", { exact: true }).inputValue(), "active");
    await page.locator("#refresh").click(); await page.locator("#content[aria-busy=false]").waitFor();
    await page.locator("#settings summary").click();
    assert.equal(await page.getByLabel("工作模式", { exact: true }).inputValue(), "active");
    await page.locator("#save").click();
    await page.locator("#rebase").waitFor();
    assert.equal(await page.locator("#save").isDisabled(), true);
    await page.locator("#rebase").click(); await page.locator("#content[aria-busy=false]").waitFor();
    await page.locator("#save").click();
    await page.getByText("已保存到原生配置。", { exact: true }).waitFor();
    const writes = await page.evaluate(() => window.__fixture.calls.filter(call => call.path === "console/config"));
    assert.equal(writes.length, 2);
    assert.equal(writes[0].payload.expected_revision, "config-1");
    assert.equal(writes[1].payload.expected_revision, "config-2");
    assert.deepEqual(writes[1].payload.patch, { mode: "active" });
    assert.equal(await page.locator("#editor").isVisible(), false);
    await context.close();
  });
  await caseRun("键盘导航、详情、模拟、确认弹窗与unknown不重试", async () => {
    const { context, page } = await open("action-unknown");
    await page.keyboard.press("Tab");
    assert.equal(await page.evaluate(() => document.activeElement.className), "skip-link");
    await page.keyboard.press("Enter");
    assert.equal(await page.evaluate(() => document.activeElement.id), "main");
    await page.locator('[data-section="overview"]').focus();
    await page.keyboard.press("ArrowRight"); await page.keyboard.press("Enter");
    assert.equal(await page.locator("#section-title").textContent(), "人格");
    await section(page, "behavior");
    await page.locator('[data-operation="preview"]').focus(); await page.keyboard.press("Enter");
    await page.getByText("模型调用 0 · 消息发送 0", { exact: true }).waitFor();
    const previewCalls = await page.evaluate(() => window.__fixture.calls.filter(call => call.method === "POST"));
    assert.deepEqual(previewCalls.map(call => call.path), ["console/preview"]);
    await page.getByText("实际生成与发送", { exact: true }).click();
    assert.equal(await page.locator('[data-operation="behavior.send"]').isDisabled(), true);
    await section(page, "night");
    await page.getByText("手动作息操作", { exact: true }).focus(); await page.keyboard.press("Enter");
    await page.locator('[data-operation="night.sleep"]').click();
    assert.equal(await page.evaluate(() => document.activeElement.id), "action-reason");
    await page.keyboard.press("Escape"); assert.equal(await page.locator("#action-dialog").isVisible(), false);
    await page.locator('[data-operation="night.sleep"]').click();
    await page.locator("#action-reason").fill("仅合成测试");
    await page.locator("#confirm-action").click();
    await page.getByText(/操作结果：unknown/).waitFor();
    await page.locator("#refresh").click(); await page.locator("#content[aria-busy=false]").waitFor();
    await page.getByText("手动作息操作", { exact: true }).click();
    assert.equal(await page.locator('[data-operation="night.sleep"]').isDisabled(), true);
    const sends = await page.evaluate(() => window.__fixture.calls.filter(call => call.path === "console/action"));
    assert.equal(sends.length, 1); assert.equal(sends[0].payload.confirmed, true);
    await context.close();
  });
  await caseRun("恶意文本仅作为文字、私人正文与四类来源分型", async () => {
    const { context, page } = await open("malicious");
    assert.equal(await page.locator(".hero-value").textContent(), ATTACK);
    await section(page, "experience");
    const first = page.locator("#record-body > article").first();
    await first.getByText("阅读私人正文", { exact: true }).click();
    assert.equal(await first.locator(".body").first().textContent(), ATTACK);
    await first.getByText("素材来源与角色", { exact: true }).click();
    assert.equal(await first.getByText("我做的", { exact: true }).isVisible(), true);
    assert.equal(await first.getByText("来源不明", { exact: true }).isVisible(), true);
    assert.equal(await page.locator("img").count(), 0);
    assert.equal(await page.evaluate(() => window.__injected === true), false);
    await page.locator("#record-kind").selectOption("dream");
    await page.locator("#record-body[aria-busy=false]").waitFor();
    assert.equal(await page.getByText("梦境 · 想象，不是现实事实", { exact: true }).count(), 10);
    await context.close();
  });
  await caseRun("缺失/非法数值、空记录、接口失败、缺bridge均不伪造状态", async () => {
    for (const scenario of ["missing-state", "invalid-numbers", "empty", "records-error", "bad-pagination", "missing-bridge", "no-context", "malformed-optional"]) {
      const { context, page } = await open(scenario);
      if (scenario === "missing-state") {
        assert.equal(await page.locator(".hero-value").textContent(), "尚无 Bot 状态");
        assert.equal(await page.getByText("只有对方观察，不能变成 Bot 感受", { exact: true }).isVisible(), true);
      } else if (scenario === "invalid-numbers") {
        assert.equal(await page.locator(".metric-value").allTextContents().then(values => values.every(value => value === "未提供")), true);
      } else if (scenario === "missing-bridge") {
        assert.match(await page.locator("#notice").textContent(), /missing_bridge/);
        assert.equal(await page.locator(".hero").count(), 0);
      } else if (scenario === "no-context") {
        await section(page, "emotion");
        assert.match(await page.locator("#record-body").textContent(), /没有已授权范围/);
      } else if (scenario === "malformed-optional") {
        await section(page, "emotion");
        await page.locator("#settings summary").click();
        assert.equal(await page.getByLabel("工作模式", { exact: true }).inputValue(), "observe_only");
      } else {
        await page.locator('[data-section="emotion"]').click();
        await page.locator("#record-body[aria-busy=false]").waitFor();
        assert.equal(await page.locator("#record-body > article").count(), 0);
        assert.match(await page.locator("#record-body").textContent(), scenario === "empty" ? /暂无记录/ : /读取失败/);
      }
      await context.close();
    }
  });
  await caseRun("401/403及读取中认证失效清空私人视图与草稿", async () => {
    for (const scenario of ["unauthorized", "forbidden", "records-denied", "message-only-auth", "untyped-auth"]) {
      const { context, page } = await open(scenario);
      if (scenario === "records-denied") await page.locator('[data-section="emotion"]').click();
      await page.getByText("私人内容已清空。请在 AstrBot 宿主重新登录并确认管理权限。", { exact: true }).waitFor();
      assert.equal(await page.locator(".hero").count(), 0);
      assert.equal(await page.locator("#context").isDisabled(), true);
      assert.equal(await page.locator("#records > *").count(), 0);
      assert.equal(await page.locator("#settings > *").count(), 0);
      assert.equal(await page.locator("#editor").isVisible(), false);
      await context.close();
    }
  });
  await caseRun("未配置生成能力禁用；生产页面不载入fixture", async () => {
    const { context, page } = await open("no-capabilities");
    await section(page, "experience");
    await page.getByText("手动生成 · 可能消耗模型额度", { exact: true }).click();
    assert.equal(await page.locator('[data-operation="diary.generate"]').isDisabled(), true);
    assert.equal(await page.locator('[data-operation="dream.generate"]').isDisabled(), true);
    await page.goto(url.replace("/tests/ui/fixture.html", "/pages/livingemotion/index.html"));
    await page.locator("#content[aria-busy=false]").waitFor();
    assert.match(await page.locator("#notice").textContent(), /missing_bridge/);
    assert.equal(await page.evaluate(() => typeof window.__fixture), "undefined");
    await context.close();
  });
  await caseRun("展开表单、私人正文、弹窗、空态与错误态双主题对比度", async () => {
    for (const theme of ["light", "dark"]) {
      const { context, page } = await open("normal", { colorScheme: theme, viewport: { width: 390, height: 844 } });
      await section(page, "emotion");
      await page.locator("#settings summary").click();
      await page.getByLabel("工作模式", { exact: true }).selectOption("active");
      await measure(page, theme, "expanded-form-and-editor");
      await page.locator("#discard").click();
      await section(page, "experience");
      await page.getByText("手动生成 · 可能消耗模型额度", { exact: true }).click();
      const first = page.locator("#record-body > article").first();
      await first.getByText("阅读私人正文", { exact: true }).click();
      await first.getByText("素材来源与角色", { exact: true }).click();
      await measure(page, theme, "private-body-and-source");
      await shot(page, `390-${theme}-private-reading.png`);
      await section(page, "night");
      await page.getByText("手动作息操作", { exact: true }).click();
      await page.locator('[data-operation="night.sleep"]').click();
      await measure(page, theme, "action-dialog");
      const box = await page.locator("#action-dialog").boundingBox();
      assert.ok(box.x >= 0 && box.x + box.width <= 390 && box.y >= 0);
      await page.keyboard.press("Escape");
      await page.goto(`${url}?scenario=loading`);
      await page.locator("#content[aria-busy=true]").waitFor();
      await measure(page, theme, "loading");
      await page.locator("#content[aria-busy=false]").waitFor();
      await context.close();
      for (const scenario of ["empty", "records-error", "unauthorized", "refresh-error"]) {
        const fixture = await open(scenario, { colorScheme: theme, viewport: { width: 390, height: 844 } });
        if (scenario === "refresh-error") {
          await fixture.page.locator("#refresh").click();
          await fixture.page.getByText(/当前显示旧快照/).waitFor();
        } else if (scenario !== "unauthorized") await section(fixture.page, "emotion");
        await measure(fixture.page, theme, scenario);
        await fixture.context.close();
      }
    }
  });
  await caseRun("跨页签同步主题、跟随系统变化、无效草稿跨分区仍阻止保存", async () => {
    const { context, page } = await open();
    await page.emulateMedia({ colorScheme: "dark" });
    await page.locator('html[data-le-theme="dark"]').waitFor();
    const second = await context.newPage();
    await second.goto(url); await second.locator("#content[aria-busy=false]").waitFor();
    await page.locator('[data-theme-choice="light"]').click();
    await second.locator('html[data-le-theme="light"]').waitFor();
    await section(page, "emotion");
    await page.locator("#settings summary").click();
    await page.getByLabel("每日模型预算", { exact: true }).fill("0");
    assert.equal(await page.locator("#save").isDisabled(), true);
    await section(page, "memory");
    assert.equal(await page.locator("#save").isDisabled(), true);
    await section(page, "emotion"); await page.locator("#settings summary").click();
    assert.equal(await page.getByLabel("每日模型预算", { exact: true }).inputValue(), "0");
    await page.getByLabel("每日模型预算", { exact: true }).fill("50");
    assert.equal(await page.locator("#save").isDisabled(), false);
    await page.locator("#discard").click();
    await context.close();
  });
  await caseRun("宿主通用主题属性不能覆盖页面偏好", async () => {
    const { context, page } = await open("host-theme", { colorScheme: "light" });
    assert.equal(await page.locator("html").getAttribute("data-theme"), "dark");
    assert.equal(await page.locator("html").getAttribute("data-le-theme"), "light");
    assert.equal(await page.evaluate(() => getComputedStyle(document.body).backgroundColor), "rgb(247, 248, 242)");
    await page.locator('[data-theme-choice="dark"]').click();
    await page.reload(); await page.locator("#content[aria-busy=false]").waitFor();
    assert.equal(await page.locator("html").getAttribute("data-le-theme"), "dark");
    await context.close();
  });
} finally {
  report.passed = report.cases.every(item => item.passed) && !report.pageErrors.length && !report.externalRequests.length;
  await writeFile(new URL("browser-results.json", evidence), `${JSON.stringify(report, null, 2)}\n`);
  await browser.close();
  await new Promise(resolve => server.close(resolve));
  console.log(`合成浏览器检查：${report.cases.filter(item => item.passed).length}/${report.cases.length}；异常 ${report.pageErrors.length}；外联 ${report.externalRequests.length}`);
  if (!report.passed) process.exitCode = 1;
}
