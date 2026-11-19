import assert from "node:assert/strict";
import { execFileSync } from "node:child_process";
import { createRequire } from "node:module";
import { mkdir, readFile, writeFile } from "node:fs/promises";
import { fileURLToPath } from "node:url";
import os from "node:os";
import path from "node:path";
import { startServer } from "./server.mjs";

const require = createRequire(import.meta.url);
const { chromium } = require(process.env.PLAYWRIGHT_MODULE || "playwright");
const root = fileURLToPath(new URL("../../", import.meta.url));
const code = `import json,sys
from pathlib import Path
from types import SimpleNamespace
sys.path.insert(0,str(Path.cwd().parent))
from astrbot_plugin_livingemotion.config import Config
from astrbot_plugin_livingemotion.runtime.console import Console
obj=SimpleNamespace(config=Config(timezone="UTC",allow_sleep=True),
                    config_revision="sleep-master-ui",_settings_groups=Console._settings_groups)
print(json.dumps(Console.config_dto(obj),ensure_ascii=False))`;
const dto = JSON.parse(execFileSync(process.env.LIVINGEMOTION_TEST_PYTHON || "python3",
  ["-c", code], { cwd: root, encoding: "utf8", env: { ...process.env, PYTHONDONTWRITEBYTECODE: "1" } }));
assert(!Object.hasOwn(dto.values, "night_schedule_enabled"));
const promises = { enabled: true, items: [{
  promise_id: "synthetic-waiting-image", status: "waiting", reason: "content_rejected",
  description: "合成图片承诺，等待调整画面。", created_at: 1795046400,
  original_due_at: 1795050000, due_at: 1795050600, target_label: "QQ号",
  target_id: "12345678", advance_count: 1,
}] };
const evidence = process.env.UI_EVIDENCE_DIR || path.join(os.tmpdir(), "le-sleep-master-ui");
await mkdir(evidence, { recursive: true });
const { server, url } = await startServer();
const browser = await chromium.launch({ headless: true });
const results = [], errors = [], externalRequests = [];
try {
  for (const [width, theme] of [[1280, "light"], [1280, "dark"], [390, "light"], [390, "dark"]]) {
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
      if (new URL(request.url()).pathname === "/tests/ui/fixture-bridge.mjs") {
        const source = await readFile(new URL("./fixture-bridge.mjs", import.meta.url), "utf8");
        return route.fulfill({ contentType: "text/javascript", body: source.replace(
          "const configKey =", `data.config = ${JSON.stringify(dto)};\ndata.behavior.promises = ${JSON.stringify(promises)};\nconst configKey =`) });
      }
      return route.continue();
    });
    await page.clock.install();
    await page.goto(url);
    await page.locator("#content[aria-busy=false]").waitFor();
    assert.equal(await page.locator(".plugin-version").innerText(), "v0.4.3");
    const header = await page.locator(".masthead").boundingBox();
    const controls = await page.locator("#refresh, #language, [data-theme-choice]").evaluateAll(
      nodes => nodes.map(el => { const r = el.getBoundingClientRect(); return r.y + r.height / 2; }));
    assert(Math.max(...controls) - Math.min(...controls) < 4);
    assert(header.height < (width < 600 ? 115 : 85));
    await page.locator(".masthead").screenshot({ path: path.join(evidence, `${width}-${theme}-header.png`) });
    await page.locator('[data-section="behavior"]').click();
    const promise = page.locator('details.promise-card[data-promise-id="synthetic-waiting-image"]');
    await promise.waitFor();
    assert((await promise.innerText()).includes("等待调整需求"));
    assert((await promise.innerText()).includes("12345678"));
    assert((await promise.innerText()).includes("原定时间"));
    await promise.locator("summary").click();
    assert((await promise.innerText()).includes("图片服务拒绝了这次画面请求"));
    await page.clock.fastForward(61000);
    await page.waitForFunction(() => document.querySelector("details.promise-card")?.open === true);
    assert.equal(await page.locator(".promise-eta").count(), 0);
    await page.locator('[data-section="settings"]').click();
    await page.locator('[data-settings-jump="prompt_injection"]').click();
    const character = page.locator('[data-prompt-stem="character"]');
    const core = page.locator('[data-prompt-stem="core"]');
    assert((await character.boundingBox()).y < (await core.boundingBox()).y);
    assert.equal(await core.innerText(), "通用说明 · 预置");
    const preset = page.locator(".prompt-core");
    assert.equal(await preset.locator("summary").innerText(), "预置提示词");
    assert((await core.boundingBox()).y < (await preset.boundingBox()).y);
    await core.scrollIntoViewIfNeeded();
    await page.screenshot({ path: path.join(evidence, `${width}-${theme}-prompts.png`) });
    await page.locator('[data-settings-jump="night"]').click();
    assert.equal(await page.locator("#config-night_schedule_enabled").count(), 0);
    const toggle = page.locator("#config-allow_sleep");
    assert.equal(await toggle.isChecked(), true);
    await toggle.uncheck();
    const reads = await page.evaluate(() => window.__fixture.calls.filter(c => c.path === "console/state").length);
    await page.clock.fastForward(61000);
    await page.waitForFunction(n => window.__fixture.calls.filter(c => c.path === "console/state").length > n, reads);
    assert.equal(await toggle.isChecked(), false);
    await page.locator("#save").click();
    await page.waitForFunction(() => document.getElementById("editor").hidden);
    const saves = await page.evaluate(() => window.__fixture.calls.filter(c => c.path === "console/config"));
    assert.deepEqual(saves[0].payload.patch, { allow_sleep: false });
    assert.equal(await page.evaluate(() => window.__fixture.state.config.values.allow_sleep), false);
    await page.reload();
    await page.locator("#content[aria-busy=false]").waitFor();
    await page.locator('[data-section="settings"]').click();
    await page.locator('[data-settings-jump="night"]').click();
    assert.equal(await toggle.isChecked(), false);
    assert.equal(await page.evaluate(() => document.documentElement.scrollWidth > innerWidth), false);
    results.push({ width, theme, headerHeight: header.height, controlsInOneRow: true,
      presetBelowCharacter: true, singleSleepToggle: true, autoRefreshPreservesDraft: true,
      exactSavePatch: true, syntheticReadback: true, noHorizontalOverflow: true,
      existingPromiseDetailsAndExpansionPreserved: true });
    await context.close();
  }
  assert.deepEqual(errors, []);
  assert.deepEqual(externalRequests, []);
  const report = { browser: browser.version(), scope: "实际页面及配置DTO；合成宿主保存；无模型和线上调用",
    results, errors, externalRequests };
  await writeFile(path.join(evidence, "results.json"), JSON.stringify(report, null, 2));
  console.log(JSON.stringify(report, null, 2));
} finally {
  await browser.close();
  await new Promise(resolve => server.close(resolve));
}
