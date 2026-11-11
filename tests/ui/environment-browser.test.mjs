import assert from "node:assert/strict";
import { createRequire } from "node:module";
import { writeFile } from "node:fs/promises";
import { startServer } from "./server.mjs";
const { chromium } = createRequire(import.meta.url)("playwright");
const { server, url } = await startServer();
const browser = await chromium.launch({ headless: true });
const folder = "/tmp/livingemotion-environment-20261110";
const report = { cases: [], errors: [] };
const env = (overrides = {}) => ({
  enabled: true, city: "上海", timezone: "Asia/Shanghai",
  server_time: Date.parse("2026-11-10T15:59:58Z") / 1000,
  weather: { status: "ok", summary: "阴 · 17.5°C", observed_at: Date.parse("2026-11-10T15:55:00Z") / 1000 },
  ...overrides,
});
try {
  for (const width of [1440, 1280, 390, 320]) for (const theme of ["light", "dark"]) {
    const page = await browser.newPage({ viewport: { width, height: 1000 }, colorScheme: theme,
      timezoneId: "America/Los_Angeles", reducedMotion: "reduce" });
    page.on("pageerror", e => report.errors.push(e.message));
    await page.clock.install({ time: new Date("2030-01-01T00:00:00Z") });
    await page.goto(`${url}?scenario=native-dto`);
    await page.locator("#content[aria-busy=false]").waitFor();
    assert.equal(await page.locator("#environment").isVisible(), false);
    assert.equal(await page.locator(".scope-bar,.nav-device,.mood-card,input[type=file]").count(), 0);
    assert.equal(await page.locator(".masthead #refresh").count(), 1);
    assert.equal(await page.evaluate(() => window.__fixture.calls.some(c => /emotion.images/.test(c.path))), false);
    await page.evaluate(value => window.__fixture.setEnvironment(value), env());
    await page.locator("#refresh").click();
    await page.locator("#environment").waitFor();
    assert.equal(await page.locator("#environment-clock").textContent(), "23:59:58");
    assert.equal(await page.locator("#environment-weather").textContent(), "阴 · 17.5°C");
    const yesterday = await page.locator("#environment-date").textContent();
    await page.clock.runFor(3000);
    assert.equal(await page.locator("#environment-clock").textContent(), "00:00:01");
    assert.notEqual(await page.locator("#environment-date").textContent(), yesterday);
    await page.selectOption("#language", "en");
    assert.equal(await page.locator("#environment-clock").textContent(), "00:00:01", "切换语言不让时钟倒退");
    await page.selectOption("#language", "zh-CN");
    const { hero, radar } = await page.locator(".ta-layout").evaluate(layout => {
      const box = el => { const { y, height } = el.getBoundingClientRect(); return { y, height }; };
      return { hero: box(layout.children[0]), radar: box(layout.children[1]) };
    });
    if (width >= 1280) assert.ok(Math.abs(hero.y + hero.height - radar.y - radar.height) < 1);
    else assert.ok(radar.y >= hero.y + hero.height);
    assert.ok(await page.evaluate(() => document.documentElement.scrollWidth <= innerWidth + 1));
    await page.screenshot({ path: `${folder}/environment-${width}-${theme}.png`, fullPage: true });
    // 10 分钟环境轮询必须保留未保存输入以及浮动保存栏。
    await page.locator('[data-section="settings"]').click();
    const input = page.locator("#config-home_city");
    await input.fill("未保存城市");
    await page.locator("#editor").waitFor();
    const before = await input.inputValue();
    const reads = await page.evaluate(() => window.__fixture.calls.filter(c => /console\/state/.test(c.path)).length);
    await page.evaluate(value => window.__fixture.setEnvironment(value), env({ weather: { status: "unavailable" } }));
    await page.clock.runFor(600000);
    assert.ok(await page.evaluate(() => window.__fixture.calls.filter(c => /console\/state/.test(c.path)).length) > reads);
    assert.equal(await input.inputValue(), before);
    assert.ok(await page.locator("#editor").isVisible());
    assert.equal(await page.locator("#environment-weather").textContent(), "天气暂不可用");
    assert.equal(await page.evaluate(() => window.__fixture.calls.filter(c => c.method === "POST").length), 0);
    // 新配置缺失时区时整张卡消失；卡片内容不会保留到隐藏 DOM。
    await page.evaluate(value => window.__fixture.setEnvironment(value), env({ timezone: "" }));
    await page.locator("#refresh").click();
    await page.locator("#content[aria-busy=false]").waitFor();
    assert.equal(await page.locator("#environment").isVisible(), false);
    assert.equal((await page.locator("#environment").textContent()).trim(), "");
    await page.evaluate(value => window.__fixture.setEnvironment(value), env({ timezone: "Invalid/Zone" }));
    await page.locator("#refresh").click();
    await page.locator("#content[aria-busy=false]").waitFor();
    assert.equal(await page.locator("#environment").isVisible(), false);
    await page.evaluate(value => window.__fixture.setEnvironment(value), env());
    await page.locator("#refresh").click();
    await page.locator("#environment").waitFor();
    await page.evaluate(() => window.__fixture.denyAccess());
    await page.clock.runFor(600000);
    await page.getByText("私人内容已清空。请在 AstrBot 宿主重新登录并确认管理权限。", { exact: true }).waitFor();
    assert.equal(await page.locator("#environment").isVisible(), false);
    assert.equal((await page.locator("#environment").textContent()).trim(), "");
    report.cases.push({ width, theme, clock_rollover: true, host_time: true, drafts_preserved: true,
      no_images: true, no_overflow: true, aligned: true, configuration_gate: true, auth_clears: true });
    await page.close();
  }
  assert.deepEqual(report.errors, []);
  report.success = true;
} catch (error) { report.success = false; report.failure = error.stack; process.exitCode = 1; }
finally {
  await writeFile(`${folder}/ui-report.json`, JSON.stringify(report, null, 2));
  console.log(JSON.stringify(report)); await browser.close(); server.close();
}
