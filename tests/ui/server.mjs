import http from "node:http";
import { readFile } from "node:fs/promises";
import { fileURLToPath, pathToFileURL } from "node:url";
import path from "node:path";

const root = fileURLToPath(new URL("../../", import.meta.url));
const assets = new Map([
  ...["theme.js", "style.css", "model.mjs", "api.mjs", "app.mjs", "dom.mjs", "settings.mjs",
    "charts/radar.mjs", "charts/relationships.mjs", "charts/energy.mjs", "vendor/d3-force.mjs"
  ].map(name => [`/pages/livingemotion/${name}`, `pages/livingemotion/${name}`]),
  ...["fixture-bridge.mjs", "fixtures.mjs", "native-dto.mjs"].map(name => [`/tests/ui/${name}`, `tests/ui/${name}`]),
]);
export async function startServer(port = 0) {
  const template = await readFile(path.join(root, "pages/livingemotion/index.html"), "utf8");
  const fixture = template.replaceAll('src="./', 'src="/pages/livingemotion/').replaceAll('href="./', 'href="/pages/livingemotion/')
    .replace('<script type="module" src="/pages/livingemotion/app.mjs">',
      '<script type="module" src="/tests/ui/fixture-bridge.mjs"></script>\n  <script type="module" src="/pages/livingemotion/app.mjs">');
  const server = http.createServer(async (request, response) => {
    const pathname = new URL(request.url, "http://127.0.0.1").pathname;
    response.setHeader("Cache-Control", "no-store");
    response.setHeader("X-Content-Type-Options", "nosniff");
    if (request.method !== "GET") { response.writeHead(405); response.end(); return; }
    try {
      if (pathname === "/tests/ui/fixture.html" || pathname === "/pages/livingemotion/index.html") {
        response.setHeader("Content-Type", "text/html; charset=utf-8");
        response.end(pathname.includes("fixture.html") ? fixture : template);
      } else if (pathname === "/api/plugin/page/bridge-sdk.js") {
        response.setHeader("Content-Type", "text/javascript; charset=utf-8");
        response.end("/* Test-only: no real host SDK or credentials. */");
      } else if (assets.has(pathname)) {
        response.setHeader("Content-Type", pathname.endsWith(".css") ? "text/css; charset=utf-8" : "text/javascript; charset=utf-8");
        response.end(await readFile(path.join(root, assets.get(pathname))));
      } else { response.writeHead(404); response.end("Not found"); }
    } catch (_) { response.writeHead(500); response.end("Fixture asset error"); }
  });
  await new Promise(resolve => server.listen(port, "127.0.0.1", resolve));
  return { server, url: `http://127.0.0.1:${server.address().port}/tests/ui/fixture.html` };
}
if (process.argv[1] && pathToFileURL(path.resolve(process.argv[1])).href === import.meta.url) {
  const { url } = await startServer(Number(process.env.PORT || 0));
  console.log(`仅合成测试页面：${url}`);
}
