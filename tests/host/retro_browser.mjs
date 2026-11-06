/* Real native Dashboard iframe acceptance. No fixture API or bridge injection. */
import fs from "node:fs/promises";
import path from "node:path";
import crypto from "node:crypto";
import { createRequire } from "node:module";
import { setTimeout as delay } from "node:timers/promises";

const [readyPath, playwrightPath, chromePath] = process.argv.slice(2);
const ready = JSON.parse(await fs.readFile(readyPath, "utf8"));
const root = path.dirname(readyPath);
const require = createRequire(import.meta.url);
const { chromium } = require(playwrightPath);
const sha = data => crypto.createHash("sha256").update(data).digest("hex");
const report = {
  phase: "final", tag: ready.tag, checks: [], real_model_calls: 0,
  real_platform_deliveries: "not_executed", fixture_responses: 0,
  native_dashboard_bundle_sha256: ready.dashboard.source_sha256_bundle,
  product_source_sha256: ready.product.source_sha256,
  browser_version: null, harness_sha256: sha(await fs.readFile(new URL(import.meta.url))),
  requests: [], blocked_nonloopback_requests: 0, page_errors: [],
};
function check(name, passed, detail) {
  report.checks.push({ name: "browser." + name, passed: Boolean(passed),
    layer: "real_native_dashboard_iframe", ...(detail === undefined ? {} : { detail }) });
  if (!passed) throw new Error(name);
}
const origin = new URL(ready.base_url).origin;
check("loopback_origin", new URL(origin).hostname === "127.0.0.1");
const safePath = url => new URL(url).pathname.replace(/\/_t\/[^/]+/g, "/_t/[redacted]");
const seen = new Map();
const pending = new Set();
let browser, page, frame;
try {
  browser = await chromium.launch({
    executablePath: chromePath, headless: true,
    args: [
      "--disable-background-networking", "--disable-component-update",
      "--disable-domain-reliability", "--disable-sync", "--no-first-run",
      "--disable-features=MediaRouter,OptimizationHints",
      "--force-webrtc-ip-handling-policy=disable_non_proxied_udp",
      "--host-resolver-rules=MAP * ~NOTFOUND, EXCLUDE localhost, EXCLUDE 127.0.0.1",
      "--proxy-server=http://127.0.0.1:9", "--proxy-bypass-list=127.0.0.1;localhost",
    ],
  });
  report.browser_version = browser.version();
  const context = await browser.newContext({
    viewport: { width: 1280, height: 900 }, serviceWorkers: "block",
    colorScheme: "light", reducedMotion: "no-preference",
  });
  context.setDefaultTimeout(15000);
  await context.route("**/*", async route => {
    if (new URL(route.request().url()).origin !== origin) {
      report.blocked_nonloopback_requests++;
      await route.abort("blockedbyclient");
    } else await route.continue();
  });
  await context.routeWebSocket("**/*", socket => {
    const url = new URL(socket.url());
    if (url.hostname !== "127.0.0.1" || url.port !== new URL(origin).port) {
      report.blocked_nonloopback_requests++;
      socket.close();
    } else socket.connectToServer();
  });
  page = await context.newPage();
  page.on("pageerror", error => {
    // Error messages can contain scoped URLs; retain only the class.
    report.page_errors.push(error.name);
  });
  page.on("response", response => {
    const url = new URL(response.url());
    const pathname = safePath(url);
    const work = (async () => {
      let digest;
      if (response.ok() && (
        url.pathname.startsWith("/assets/") || url.pathname.includes("/_t/")
        || url.pathname === "/api/plugin/page/bridge-sdk.js"
      )) digest = sha(await response.body());
      seen.set(pathname + ":" + response.status(), { path: pathname, status: response.status(),
        ...(digest ? { sha256: digest } : {}) });
    })().catch(() => { seen.set(pathname + ":" + response.status(),
      { path: pathname, status: response.status() }); });
    pending.add(work);
    void work.finally(() => pending.delete(work));
  });
  await page.goto(origin + "/#/auth/login");
  await page.locator('input[name="username"]').fill(ready.username);
  await page.locator('input[name="password"]').fill(ready.password);
  const loginResponse = page.waitForResponse(response =>
    new URL(response.url()).pathname === "/api/v1/auth/login"
    && response.request().method() === "POST");
  await page.locator('button[type="submit"]').click();
  check("native_ui_password_login", (await loginResponse).status() === 200);
  await page.waitForFunction(() => Boolean(localStorage.getItem("token")));
  await page.waitForURL(url => url.hash.startsWith("#/welcome")
    || url.hash.startsWith("#/dashboard/"));
  const firstNoticeResponse = page.waitForResponse(response =>
    new URL(response.url()).pathname === "/api/v1/stats/first-notice");
  await page.goto(origin + "/#/plugin-view/astrbot_plugin_livingemotion/livingemotion");
  const notice = await firstNoticeResponse;
  check("native_first_notice_loaded", notice.status() === 200);
  if ((await notice.json()).data?.content?.trim()) {
    // A real first-run README dialog appears asynchronously above the iframe.
    // Dismiss its ordinary close control; never bypass it with force clicks.
    const dialog = page.locator(".v-dialog.v-overlay--active").filter({
      has: page.getByRole("button", { name: /^(关闭|Close)$/ }),
    });
    await dialog.getByRole("button", { name: /^(关闭|Close)$/ }).click();
    await dialog.waitFor({ state: "hidden" });
    check("native_first_notice_closed_by_ui", true);
  }
  const iframe = page.locator("iframe.plugin-view-frame");
  await iframe.waitFor({ state: "visible" });
  check("native_iframe_sandbox", await iframe.getAttribute("sandbox") ===
    "allow-scripts allow-forms allow-downloads");
  const src = await iframe.getAttribute("src");
  check("native_resources_scoped_mapping", src?.includes(
    "/api/v1/plugins/astrbot_plugin_livingemotion/views/livingemotion/_t/"));
  frame = await iframe.contentFrame();
  await frame.locator("#content[aria-busy=false]").waitFor();
  await frame.locator("#scope-persona:not([disabled])").waitFor();
  check("native_sdk_loaded", await frame.locator("body").evaluate(() =>
    typeof window.AstrBotPluginPage?.apiGet === "function"
    || typeof window.AstrBotPluginView?.apiGet === "function"));
  const sections = ["overview", "persona", "emotion", "relationships", "behavior",
    "night", "experience", "memory", "settings"];
  check("exact_nine_sections", JSON.stringify(
    await frame.locator("[data-section]").evaluateAll(nodes => nodes.map(n => n.dataset.section))
  ) === JSON.stringify(sections));
  await page.evaluate(() => {
    window.__retroParentPointerTrace = [];
    for (const type of ["pointerdown", "pointerup", "click"]) {
      document.addEventListener(type, event => {
        window.__retroParentPointerTrace.push({
          type, x: event.clientX, y: event.clientY, tag: event.target.tagName,
          class: String(event.target.className).slice(0, 160),
        });
        if (window.__retroParentPointerTrace.length > 24) {
          window.__retroParentPointerTrace.shift();
        }
      }, true);
    }
  });
  await frame.locator("html").evaluate(() => {
    window.__retroPointerTrace = [];
    for (const type of ["pointerdown", "pointerup", "click"]) {
      document.addEventListener(type, event => {
        window.__retroPointerTrace.push({
          type, x: event.clientX, y: event.clientY, tag: event.target.tagName,
          section: event.target.closest?.("[data-section]")?.dataset.section,
          theme: event.target.closest?.("[data-theme-choice]")?.dataset.themeChoice,
        });
        if (window.__retroPointerTrace.length > 24) window.__retroPointerTrace.shift();
      }, true);
    }
  });
  async function resize(width) {
    await page.setViewportSize({ width, height: 900 });
    // Locator stability inside the child does not cover Vuetify moving its
    // iframe while the native sidebar changes between desktop and mobile.
    // Wait for the parent layout and compositor frames, without bypassing
    // pointer hit testing or retrying a dropped click.
    await iframe.evaluate(async element => {
      let previous, stable = 0;
      const deadline = performance.now() + 5000;
      while (stable < 4) {
        await new Promise(resolve => requestAnimationFrame(resolve));
        const bounds = element.getBoundingClientRect();
        const current = [bounds.x, bounds.y, bounds.width, bounds.height].join(",");
        const moving = document.getAnimations().some(animation =>
          animation.playState === "running" && animation.effect?.getTiming().iterations !== Infinity);
        stable = !moving && current === previous ? stable + 1 : 0;
        previous = current;
        if (performance.now() > deadline) throw new Error("native_layout_not_stable");
      }
    });
    await frame.locator("html").evaluate(async () => {
      await new Promise(resolve => requestAnimationFrame(resolve));
      await new Promise(resolve => requestAnimationFrame(resolve));
    });
  }
  for (let cycle = 0; cycle < 5; cycle++) {
    await resize(1280);
    await frame.locator('[data-section="settings"]').click();
    await frame.locator('[data-theme-choice="dark"]').click();
    await frame.locator('html[data-le-theme="dark"]:not([data-le-transition])').waitFor();
    await resize(390);
    await frame.locator('[data-theme-choice="light"]').click();
    await frame.locator('html[data-le-theme="light"]:not([data-le-transition])').waitFor();
    const bounds = await frame.locator('[data-section="overview"]').boundingBox();
    report.navigation_probe = await page.evaluate(bounds => {
      const hit = bounds ? document.elementFromPoint(bounds.x + bounds.width / 2,
        bounds.y + bounds.height / 2) : null;
      const iframe = document.querySelector("iframe.plugin-view-frame");
      return {
        bounds, iframe_bounds: iframe?.getBoundingClientRect().toJSON(),
        hit_tag: hit?.tagName,
        animations: document.getAnimations().map(animation => ({
          play_state: animation.playState, time: animation.currentTime,
          target: animation.effect?.target?.className,
        })),
      };
    }, bounds);
    await frame.locator('[data-section="overview"]').click();
    await frame.locator('[data-section="overview"][aria-current=page]').waitFor();
    check("responsive_theme_navigation_" + cycle, true);
  }
  report.frames = [];
  for (const width of [1280, 390]) {
    await resize(width);
    for (const theme of ["light", "dark"]) {
      await frame.locator(`[data-theme-choice="${theme}"]`).click();
      await frame.locator(`html[data-le-theme="${theme}"]:not([data-le-transition])`).waitFor();
      check(`${width}.${theme}.theme_pressed`, await frame.locator(
        `[data-theme-choice="${theme}"]`).getAttribute("aria-pressed") === "true");
      for (const section of sections) {
        await frame.locator(`[data-section="${section}"]`).click();
        await frame.locator(`[data-section="${section}"][aria-current=page]`).waitFor();
        await frame.locator("#content[aria-busy=false]").waitFor();
        if (section === "relationships") {
          await frame.locator("#relationship-body[aria-busy=false]").waitFor();
          await frame.locator(".relationship-table").waitFor();
          check(`${width}.${theme}.relationship_source_rows`,
            await frame.locator(".relationship-table tbody tr").count() > 0);
          await frame.getByRole("button", { name: "查看 / 修改", exact: true }).first().click();
          await frame.locator(".graph-detail:not([hidden])").waitFor();
        } else if (section === "night") {
          await frame.locator("#energy-body[aria-busy=false]").waitFor();
          await frame.locator(".energy-chart").waitFor();
        } else if (section === "settings") {
          await frame.locator("#settings:not([hidden]) .settings-group").first().waitFor();
          check(`${width}.${theme}.native_settings_fields`,
            await frame.locator("#settings [data-key]").count() > 0);
        }
        const metrics = await frame.locator("html").evaluate(element => ({
          width: element.clientWidth, scroll: element.scrollWidth,
          title: document.querySelector("#section-title")?.textContent,
          notice: Boolean(!document.querySelector("#notice").hidden
            && document.querySelector("#notice").classList.contains("error")),
        }));
        check(`${width}.${theme}.${section}.render`,
          Boolean(metrics.title) && !metrics.notice
          && metrics.width > 0 && metrics.scroll <= metrics.width + 2, metrics);
        report.frames.push({ width, theme, section, ...metrics });
        if (["overview", "relationships", "night", "settings"].includes(section)) {
          await iframe.screenshot({ path: path.join(root, `${width}-${theme}-${section}.png`) });
        }
      }
    }
  }
  await frame.locator('[data-section="persona"]').focus();
  await frame.locator('[data-section="persona"]').press("Enter");
  await frame.locator('[data-section="persona"][aria-current=page]').waitFor();
  check("keyboard_section_activation", true);
  await page.emulateMedia({ reducedMotion: "reduce" });
  await frame.locator('[data-theme-choice="light"]').click();
  await frame.locator('html[data-le-theme="light"]:not([data-le-transition])').waitFor();
  check("reduced_motion_theme", true);

  // Pin the diary seeded under the current real HTTP source, rather than the
  // oldest persona in the Dashboard's global selector.
  await frame.locator("#scope-persona").selectOption("retro-http-persona");
  await frame.locator("#content[aria-busy=false]").waitFor();
  await frame.locator('[data-section="experience"]').click();
  await frame.locator("#record-body[aria-busy=false]").waitFor();
  const diary = frame.locator("#record-body > article").first();
  await diary.getByText("阅读私人正文", { exact: true }).click();
  await diary.getByRole("button", { name: "置顶", exact: true }).click();
  await frame.locator("#action-reason").fill("Synthetic native iframe pin");
  const pinResponse = page.waitForResponse(response =>
    new URL(response.url()).pathname.endsWith("/console/action")
    && response.request().method() === "POST");
  await frame.locator("#confirm-action").click();
  const pinned = await pinResponse;
  check("native_pin_actual_authenticated_http", pinned.status() === 200);
  const pinData = (await pinned.json()).data;
  check("native_pin_no_model_or_send",
    pinData.status === "updated" && pinData.model_calls === 0 && pinData.sends === 0);
  await frame.locator("#refresh").click();
  // Selector/state refresh precedes rebuilding the records container. Waiting
  // on the old idle record-body alone can read the pre-pin snapshot.
  await frame.locator("#content[aria-busy=false]").waitFor();
  await frame.locator("#record-body[aria-busy=false]").waitFor();
  await diary.getByText("阅读私人正文", { exact: true }).click();
  check("native_pin_refresh_persistence",
    await diary.getByRole("button", { name: "取消置顶", exact: true }).count() === 1);

  // The child changes only the isolated native Dashboard administrator.
  // The existing valid token then fails the product's real identity guard.
  await fs.writeFile(path.join(root, "browser-revoke-request.json"), "{}");
  const deadline = Date.now() + 10000;
  while (true) {
    try { await fs.access(path.join(root, "browser-revoked.json")); break; }
    catch (_) {
      if (Date.now() >= deadline) throw new Error("native_role_revocation_timeout");
      await delay(50);
    }
  }
  check("native_role_revocation_acknowledged", true);
  const denied = page.waitForResponse(response =>
    /\/console\/(scopes|settings-options|state)$/.test(new URL(response.url()).pathname));
  await frame.locator("#refresh").click();
  // Refresh loads selectors/options before state. A denial there correctly
  // prevents any state request; all three reads must clear private UI/drafts.
  const deniedStatus = (await denied).status();
  check("native_guard_actual_denial", [401, 403].includes(deniedStatus), deniedStatus);
  await frame.getByText("私人内容已清空。", { exact: false }).waitFor();
  check("native_guard_clears_private_content",
    await frame.locator("#settings").getAttribute("hidden") !== null
    && await frame.locator("#records").getAttribute("hidden") !== null
    && await frame.locator("#scope-persona").isDisabled());
  await Promise.all([...pending]);
  const resources = [...seen.values()];
  for (const asset of resources.filter(item => item.path.startsWith("/assets/")
    && item.sha256)) {
    check("native_dashboard_hash." + path.basename(asset.path),
      ready.dashboard.files_sha256[asset.path.slice(1)] === asset.sha256);
  }
  const sdk = resources.find(item => item.path === "/api/plugin/page/bridge-sdk.js");
  check("actual_bridge_sdk_http", sdk?.status === 200 && Boolean(sdk.sha256));
  for (const asset of ["theme.js", "style.css", "app.mjs", "api.mjs", "model.mjs",
    "charts/relationships.mjs", "charts/energy.mjs", "vendor/d3-force.mjs"]) {
    const response = resources.find(item => item.path.endsWith("/" + asset));
    check("product_resource_hash." + asset, response?.status === 200
      && response.sha256 === ready.product.files_sha256["pages/livingemotion/" + asset]);
  }
  check("native_page_discovery_http", resources.some(item =>
    (item.path === "/api/v1/plugins/astrbot_plugin_livingemotion/views/livingemotion"
      || item.path === "/api/v1/plugins/view")
    && item.status === 200));
  for (const route of ["state", "scopes", "settings-options", "relationships", "energy", "records"]) {
    check("real_sdk_console_http." + route, resources.some(item =>
      item.path.endsWith("/console/" + route) && item.status === 200));
  }
  check("no_uncaught_page_errors", report.page_errors.length === 0, report.page_errors);
  report.requests = resources;
} catch (error) {
  report.fatal_type = error.name;
  try {
    report.parent_failure_state = await page.evaluate(() => ({
      pointer_trace: window.__retroParentPointerTrace,
      iframe_bounds: document.querySelector("iframe.plugin-view-frame")
        ?.getBoundingClientRect().toJSON(),
    }));
    report.ui_failure_state = await frame.locator("html").evaluate(element => {
      const button = document.querySelector('[data-section="overview"]');
      const bounds = button?.getBoundingClientRect();
      const hit = bounds ? document.elementFromPoint(bounds.x + bounds.width / 2,
        bounds.y + bounds.height / 2) : null;
      return {
        theme: element.dataset.leTheme, transition: element.dataset.leTransition,
        width: element.clientWidth, title: document.querySelector("#section-title")?.textContent,
        selected: document.querySelector("[data-section][aria-current=page]")?.dataset.section,
        hit_tag: hit?.tagName, hit_section: hit?.dataset.section,
        animations: document.getAnimations().map(animation => ({
          play_state: animation.playState, time: animation.currentTime,
          pseudo: animation.effect?.pseudoElement,
        })),
        pointer_trace: window.__retroPointerTrace,
      };
    });
    await page.screenshot({ path: path.join(root, "ui-failure.png"), fullPage: true });
  } catch (_) { /* Preserve the original failure if the frame was destroyed. */ }
  // Assertion names are constant. Playwright errors may contain private URLs.
  report.failure_check = error.name === "Error" && /^[a-zA-Z0-9_.-]+$/.test(error.message)
    ? error.message : "browser_operation_failed";
  report.error_summary = String(error.message).split("\n").slice(0, 20).join("\n")
    .replace(/https?:\/\/[^\s'"]+/g, "[local-url]")
    .replaceAll(root, "[evidence-root]").replaceAll(ready.password, "[redacted]");
} finally {
  if (browser) await browser.close();
  await Promise.all([...pending]);
  report.requests = [...seen.values()];
  report.success = !report.fatal_type && report.checks.every(check => check.passed);
  await fs.writeFile(path.join(root, "browser-report.json"), JSON.stringify(report, null, 2));
}
process.exitCode = report.success ? 0 : 2;
