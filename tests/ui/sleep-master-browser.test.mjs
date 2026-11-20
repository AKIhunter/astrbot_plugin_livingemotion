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
const metadata = await readFile(path.join(root, "metadata.yaml"), "utf8");
const version = metadata.match(/^version:\s*(\d+\.\d+\.\d+)\s*$/m)?.[1];
assert.ok(version, "metadata version is required");
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
const items = Array.from({ length: 6 }, (_, i) => ({
  promise_id: `synthetic-promise-${i}`, status: i === 0 ? "waiting" : "scheduled",
  reason: i === 0 ? "content_rejected" : "", description: `合成图片承诺${i}`,
  created_at: 1795046400, original_due_at: 1795050000, due_at: 1795050600 + i,
  target_label: "QQ号", target_id: `1234567${i}`, advance_count: i === 0 ? 1 : 0,
}));
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
          "const configKey =", `data.config = ${JSON.stringify(dto)};\ndata.behavior.promises = ${
            JSON.stringify({ enabled: true, total: items.length, items })};\nconst configKey =`) });
      }
      return route.continue();
    });
    await page.clock.install();
    await page.goto(url);
    await page.locator("#content[aria-busy=false]").waitFor();
    assert.equal(await page.locator(".plugin-version").innerText(), `v${version}`);
    const header = await page.locator(".masthead").boundingBox();
    const controls = await page.locator("#refresh, #language, [data-theme-choice]").evaluateAll(
      nodes => nodes.map(el => { const r = el.getBoundingClientRect(); return r.y + r.height / 2; }));
    assert(Math.max(...controls) - Math.min(...controls) < 4);
    assert(header.height < (width < 600 ? 115 : 85));
    await page.locator('[data-section="behavior"]').click();
    const promise = page.locator('details.promise-card[data-promise-id="synthetic-promise-0"]');
    await promise.waitFor();
    assert.equal(await page.locator("details.promise-card").count(), 6);
    assert((await page.locator("#behavior-promises").innerText()).includes("共 6 项"));
    assert((await promise.innerText()).includes("等待调整需求"));
    assert((await promise.innerText()).includes("12345670"));
    assert((await promise.innerText()).includes("原定时间"));
    await promise.locator("summary").click();
    assert((await promise.innerText()).includes("图片服务拒绝了这次画面请求"));
    await promise.locator("summary").focus();
    const next = [...items, { ...items[5], promise_id: "synthetic-promise-6" }];
    await page.evaluate(value => window.__fixture.setPromises(value),
      { enabled: true, total: next.length, items: next });
    await page.clock.fastForward(61000);
    await page.waitForFunction(() => document.querySelectorAll("details.promise-card").length === 7);
    assert((await page.locator("#behavior-promises").innerText()).includes("共 7 项"));
    assert.equal(await promise.evaluate(el => el.open), true);
    assert.equal(await page.evaluate(() => document.activeElement.closest(".promise-card")?.dataset.promiseId),
      "synthetic-promise-0");
    await page.screenshot({ path: path.join(evidence, `${width}-${theme}-promises.png`) });
    await page.locator('[data-section="settings"]').click();
    await page.locator('[data-settings-jump="prompt_injection"]').click();
    const character = page.locator('[data-prompt-stem="character"]');
    const core = page.locator('[data-prompt-stem="core"]');
    assert((await character.boundingBox()).y < (await core.boundingBox()).y);
    assert.equal(await core.innerText(), "通用说明 · 预置");
    assert.equal(await page.locator(".prompt-core summary").innerText(), "预置提示词");
    await page.locator('[data-settings-jump="night"]').click();
    assert.equal(await page.locator("#config-night_schedule_enabled").count(), 0);
    const toggle = page.locator("#config-allow_sleep");
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
    // 已发布控制台是PC布局；窄宿主iframe保留700px最小宽度。
    assert.ok(await page.evaluate(() => document.documentElement.scrollWidth <= Math.max(innerWidth, 700) + 1));
    results.push({ width, theme, headerHeight: header.height, completeList: true,
      autoRefreshChangesTotal: true, preservesExpansionAndFocus: true, promptOrder: true,
      singleSleepToggle: true, exactSavePatch: true, reloadReadback: true });
    await context.close();
  }
  assert.deepEqual(errors, []);
  assert.deepEqual(externalRequests, []);
  const report = { browser: browser.version(), scope: "实际页面与真实Config DTO；合成桥，无模型与生产调用",
    results, errors, externalRequests };
  await writeFile(path.join(evidence, "sleep-master-results.json"), JSON.stringify(report, null, 2));
  console.log(JSON.stringify(report, null, 2));
} finally {
  await browser.close();
  await new Promise(resolve => server.close(resolve));
}
