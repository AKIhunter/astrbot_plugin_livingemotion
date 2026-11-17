import assert from "node:assert/strict";
import { execFileSync } from "node:child_process";
import { mkdir, readFile, writeFile } from "node:fs/promises";
import { fileURLToPath } from "node:url";
import os from "node:os";
import path from "node:path";
import { chromium } from "playwright";
import { startServer } from "./server.mjs";

// 从当前后端导出真实字段；宿主桥、保存和时间均合成，不访问线上。
const root = fileURLToPath(new URL("../../", import.meta.url));
const code = `import json,sys
from pathlib import Path
from types import SimpleNamespace
sys.path.insert(0,str(Path.cwd().parent))
from astrbot_plugin_livingemotion.config import Config
from astrbot_plugin_livingemotion.runtime.console import Console
obj=SimpleNamespace(config=Config(timezone="Asia/Shanghai",night_schedule_enabled=True),
                    config_revision="sleep-rule-ui",_settings_groups=Console._settings_groups)
print(json.dumps(Console.config_dto(obj),ensure_ascii=False))`;
const dto = JSON.parse(execFileSync(process.env.LIVINGEMOTION_TEST_PYTHON || "python3",
  ["-c", code], { cwd: root, encoding: "utf8" }));
const evidence = process.env.UI_EVIDENCE_DIR || path.join(os.tmpdir(), "le-sleep-switches-ui");
await mkdir(evidence, { recursive: true });
const { server, url } = await startServer();
const browser = await chromium.launch({ headless: true });
const results = [], errors = [], externalRequests = [];
try {
  for (const [width, theme] of [[1280, "light"], [390, "light"], [390, "dark"]]) {
    const context = await browser.newContext({ viewport: { width, height: 1000 },
      colorScheme: theme, reducedMotion: "reduce" });
    const page = await context.newPage();
    page.setDefaultTimeout(6000);
    page.on("pageerror", error => errors.push(error.message));
    await page.route("**/*", async route => {
      const request = route.request();
      if (new URL(request.url()).origin !== new URL(url).origin) {
        externalRequests.push(request.url()); return route.abort();
      }
      if (new URL(request.url()).pathname === "/tests/ui/fixture.html") {
        // 生产页面带资源版本参数；在实际模板上注入夹具，不依赖无查询参数的标签。
        const template = await readFile(new URL("../../pages/livingemotion/index.html", import.meta.url), "utf8");
        const body = template.replaceAll('src="./', 'src="/pages/livingemotion/')
          .replaceAll('href="./', 'href="/pages/livingemotion/')
          .replace(/<script type="module" src="\/pages\/livingemotion\/app\.mjs[^"]*">/,
            '<script type="module" src="/tests/ui/fixture-bridge.mjs"></script>\n$&');
        return route.fulfill({ contentType: "text/html", body });
      }
      if (request.url().endsWith("/tests/ui/fixture-bridge.mjs")) {
        const source = await readFile(new URL("./fixture-bridge.mjs", import.meta.url), "utf8");
        return route.fulfill({ contentType: "text/javascript", body: source.replace(
          "const configKey =", `data.config = ${JSON.stringify(dto)};\nconst configKey =`) });
      }
      return route.continue();
    });
    await page.clock.install();
    await page.goto(url);
    await page.locator("#content[aria-busy=false]").waitFor();
    await page.locator('[data-section="settings"]').click();
    await page.locator('[data-settings-jump="night"]').click();
    const card = page.locator('[data-subsection="energy"]');
    const day = card.locator("#config-energy_daytime_recovery_enabled");
    const follow = card.locator("#config-recovery_follow_wake_at");
    const duration = card.locator("#config-recovery_max_minutes");
    assert.equal(await day.isChecked(), false);
    assert.equal(await follow.isChecked(), true);
    assert.equal(await duration.inputValue(), "120");
    assert.equal(await duration.getAttribute("min"), "1");
    assert.equal(await duration.getAttribute("max"), "1440");
    for (const input of [day, follow, duration]) {
      assert.equal(await input.isVisible(), true);
      assert.equal(await input.isEnabled(), true);
      assert.equal(await input.evaluate(el => el.closest(".field").dataset.level), "0");
    }
    await card.screenshot({ path: path.join(evidence, `${width}-${theme}-default.png`) });
    await day.focus();
    await page.keyboard.press("Space");
    assert.equal(await day.isChecked(), true);
    await follow.uncheck();
    for (const invalid of ["0", "1441", "1.5"]) {
      await duration.fill(invalid);
      assert.equal(await duration.getAttribute("aria-invalid"), "true");
      assert.equal(await page.locator("#save").isEnabled(), false);
    }
    await duration.fill("60");
    assert.equal(await duration.getAttribute("aria-invalid"), null);
    assert.equal(await page.locator("#save").isEnabled(), true);
    const calls = await page.evaluate(() =>
      window.__fixture.calls.filter(call => call.path === "console/state").length);
    await page.clock.fastForward(61000);
    await page.waitForFunction(n =>
      window.__fixture.calls.filter(call => call.path === "console/state").length > n, calls);
    assert.equal(await day.isChecked(), true);
    assert.equal(await follow.isChecked(), false);
    assert.equal(await duration.inputValue(), "60");
    await page.locator("#save").click();
    await page.waitForFunction(() =>
      window.__fixture.calls.some(call => call.path === "console/config"));
    const saves = await page.evaluate(() =>
      window.__fixture.calls.filter(call => call.path === "console/config"));
    assert.deepEqual(saves[0].payload.patch, {
      energy_daytime_recovery_enabled: true, recovery_follow_wake_at: false,
      recovery_max_minutes: 60,
    });
    await page.waitForFunction(() => document.getElementById("editor").hidden);
    await page.reload();
    await page.locator("#content[aria-busy=false]").waitFor();
    await page.locator('[data-section="settings"]').click();
    await page.locator('[data-settings-jump="night"]').click();
    assert.equal(await day.isChecked(), true);
    assert.equal(await follow.isChecked(), false);
    assert.equal(await duration.inputValue(), "60");
    await card.locator('[data-config-help="recovery_follow_wake_at"]').click();
    assert.match(await page.locator("#config-help-description").innerText(), /只影响新补觉周期/);
    await page.getByRole("button", { name: "知道了", exact: true }).click();
    assert.equal(await page.evaluate(() =>
      document.documentElement.scrollWidth > innerWidth), false);
    await card.screenshot({ path: path.join(evidence, `${width}-${theme}-edited.png`) });
    await page.locator("#language").selectOption("en");
    assert.equal(await page.getByLabel("Automatic daytime recovery", { exact: true }).isChecked(), true);
    assert.equal(await page.getByLabel("Maximum recovery duration", { exact: true }).inputValue(), "60");
    await page.locator("#language").selectOption("ja");
    assert.equal(await page.getByLabel("日中の自動回復", { exact: true }).isChecked(), true);
    await page.locator("#language").selectOption("zh-CN");
    results.push({ width, theme, realDTO: true, defaults: true, keyboard: true,
      bounds: true, automaticRefreshPreservesDraft: true, exactSavePatch: true,
      syntheticSaveReadback: true, noHorizontalOverflow: true, threeLocales: true });
    await context.close();
  }
  assert.deepEqual(errors, []);
  assert.deepEqual(externalRequests, []);
  const report = { browser: browser.version(), scope: "当前实际组件＋实际配置DTO；合成宿主桥，未验证生产",
    results, errors, externalRequests };
  await writeFile(path.join(evidence, "results.json"), JSON.stringify(report, null, 2));
  console.log(JSON.stringify(report, null, 2));
} finally {
  await browser.close();
  await new Promise(resolve => server.close(resolve));
}
