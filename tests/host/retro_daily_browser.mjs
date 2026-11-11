/* Actual sandboxed native iframe. No injected bridge, mocked HTTP or paid model. */
import fs from "node:fs/promises";
import path from "node:path";
import { createRequire } from "node:module";
const [readyPath, playwrightPath, chromePath] = process.argv.slice(2);
const ready = JSON.parse(await fs.readFile(readyPath, "utf8"));
const root = path.dirname(readyPath);
const { chromium } = createRequire(import.meta.url)(playwrightPath);
const report = { tag: ready.tag, checks: [], frames: [], page_errors: [],
  native_dashboard_bundle_sha256: ready.dashboard.source_sha256_bundle,
  product_source_sha256: ready.product.source_sha256, fixture_responses: 0 };
function check(name, passed) {
  report.checks.push({ name, passed: Boolean(passed) });
  if (!passed) throw Error(name);
}
let browser;
try {
  browser = await chromium.launch({ executablePath: chromePath, headless: true,
    args: ["--disable-background-networking", "--disable-sync", "--no-first-run",
      "--host-resolver-rules=MAP * ~NOTFOUND, EXCLUDE localhost, EXCLUDE 127.0.0.1",
      "--proxy-server=http://127.0.0.1:9", "--proxy-bypass-list=127.0.0.1;localhost"] });
  report.browser_version = browser.version();
  // Playwright's "block" initializer reads navigator.serviceWorker inside the
  // opaque sandbox and itself throws SecurityError. Keep the real sandbox;
  // network isolation is enforced by the proxy, DNS guard and loopback routes.
  const context = await browser.newContext({ viewport: { width: 1280, height: 900 },
    reducedMotion: "no-preference" });
  context.setDefaultTimeout(15000);
  await context.route("**/*", route => new URL(route.request().url()).origin === ready.base_url ?
    route.continue() : route.abort());
  const page = await context.newPage();
  page.on("pageerror", e => report.page_errors.push({
    name: e.name, message: e.message.replace(/\/_t\/[^/]+/g, "/_t/[redacted]"),
    stack: e.stack?.replace(/\/_t\/[^/]+/g, "/_t/[redacted]").slice(0, 1600) }));
  await page.goto(ready.base_url + "/#/auth/login");
  await page.locator('input[name="username"]').fill(ready.username);
  await page.locator('input[name="password"]').fill(ready.password);
  const logged = page.waitForResponse(r => new URL(r.url()).pathname === "/api/v1/auth/login");
  await page.locator('button[type="submit"]').click();
  check("native.password_login", (await logged).status() === 200);
  await page.waitForURL(u => u.hash.startsWith("#/welcome") || u.hash.startsWith("#/dashboard/"));
  const noticed = page.waitForResponse(r => new URL(r.url()).pathname === "/api/v1/stats/first-notice");
  await page.goto(ready.base_url + "/#/plugin-view/astrbot_plugin_livingemotion/livingemotion");
  const notice = await noticed;
  if ((await notice.json()).data?.content?.trim()) {
    const dialog = page.locator(".v-dialog.v-overlay--active").filter({
      has: page.getByRole("button", { name: /^(关闭|Close)$/ }) });
    await dialog.getByRole("button", { name: /^(关闭|Close)$/ }).click();
    await dialog.waitFor({ state: "hidden" });
  }
  const iframe = page.locator("iframe.plugin-view-frame");
  await iframe.waitFor({ state: "visible" });
  check("native.real_sandbox", await iframe.getAttribute("sandbox") ===
    "allow-scripts allow-forms allow-downloads");
  const frame = await iframe.contentFrame();
  await frame.locator("#content[aria-busy=false]").waitFor();
  await frame.locator('[data-section="experience"]').click();
  await frame.locator("#record-body[aria-busy=false]").waitFor();
  check("native.three_tabs", JSON.stringify(await frame.getByRole("tab").allTextContents()) ===
    JSON.stringify(["设置", "日记", "梦境"]));
  for (const kind of ["diary", "dream"]) {
    await frame.getByRole("tab", { name: kind === "diary" ? "日记" : "梦境", exact: true }).click();
    const completed = page.waitForResponse(r => r.request().method() === "GET" &&
      new URL(r.url()).pathname.endsWith("/console/experience-task"));
    await frame.locator(`[data-operation="${kind}.generate"]`).click();
    check(`native.${kind}.get_task`, (await completed).status() === 200);
    await frame.locator(`[data-operation="${kind}.generate"]:not([disabled])`).waitFor();
    await frame.locator("article details[open]").first().waitFor();
    check(`native.${kind}.one_record`, await frame.locator("#record-body article").count() === 1);
    await frame.locator("#refresh").click();
    await frame.locator(`[data-operation="${kind}.generate"]:not([disabled])`).waitFor();
    check(`native.${kind}.refresh_preserves_tab`, await frame.getByRole("tab", { selected: true }).textContent() ===
      (kind === "diary" ? "日记" : "梦境"));
    await frame.locator("#experience-panel").screenshot({ path: path.join(root, `native-${kind}.png`) });
    report.frames.push({ kind, width: 1280 });
  }
  await frame.getByRole("tab", { name: "设置", exact: true }).click();
  check("native.settings", await frame.locator("#settings").isVisible());
  const city = frame.locator("#config-home_city");
  check("native.city_field_present", await city.count() === 1);
  {
    await city.fill("合成草稿");
    await frame.locator("#refresh").click();
    check("native.draft_survives_refresh", await city.inputValue() === "合成草稿");
  }
  report.frames.push({ kind: "settings", width: 1280 });
  await page.setViewportSize({ width: 390, height: 844 });
  await frame.getByRole("tab", { name: "梦境", exact: true }).click();
  check("native.mobile_no_overflow", await frame.locator("body").evaluate(() =>
    document.documentElement.scrollWidth <= innerWidth + 1));
  report.frames.push({ kind: "dream", width: 390 });
  check("native.no_page_errors", report.page_errors.length === 0);
  check("native.no_service_workers", context.serviceWorkers().length === 0);
  report.success = true;
} catch (error) { report.success = false; report.failure_check = error.message; report.fatal_type = error.name; process.exitCode = 1; }
finally {
  await browser?.close();
  await fs.writeFile(path.join(root, "browser-report.json"), JSON.stringify(report, null, 2));
  console.log(JSON.stringify({ success: report.success, checks: report.checks, failure: report.failure_check }));
}
