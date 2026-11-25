"""Loopback-only native host download fixture; no providers or platform sends.

Run in a pinned AstrBot interpreter. The pages/SDK/routes are real; the parent
is a minimal download bridge harness and unrelated console reads are rejected.
"""
import argparse
import asyncio
from contextlib import asynccontextmanager
import os
from pathlib import Path
import sys
from types import SimpleNamespace


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--host-source", required=True, type=Path)
    parser.add_argument("--data-root", required=True, type=Path)
    parser.add_argument("--port", required=True, type=int)
    args = parser.parse_args()
    root = args.data_root.resolve()
    root.mkdir(parents=True, exist_ok=True)
    plugin = Path(__file__).resolve().parents[2]
    host = args.host_source.resolve()
    sys.path[:0] = [str(host), str(plugin.parent), str(Path(__file__).parent)]
    os.environ.update(ASTRBOT_ROOT=str(root), ASTRBOT_TEST_MODE="true",
                      LIVINGEMOTION_CONSOLE_TEST_ROOT=str(root))
    from fastapi.responses import HTMLResponse, Response
    from fastapi.staticfiles import StaticFiles
    import uvicorn
    from test_console import ConsoleTests
    from astrbot_plugin_livingemotion.config import Config
    from astrbot_plugin_livingemotion.diagnostic_bundle import DiagnosticRecorder
    from astrbot_plugin_livingemotion.storage import SQLiteStore
    from astrbot_plugin_LivingHello.diagnostic_bundle import DiagnosticRecorder as LHRecorder
    from astrbot_plugin_LivingHello.console.guard_webui import register_webui
    from astrbot.dashboard.services.plugin_page_service import PluginPageService

    async def prepare():
        fixture = ConsoleTests("test_diagnostic_zip_native_auth_both_plugins_and_send_failure_cleanup")
        await fixture.asyncSetUp()
        store = SQLiteStore(root / "livingemotion.sqlite3")
        await store.open()
        le = DiagnosticRecorder(root, "astrbot_plugin_livingemotion", plugin)
        hello_root = plugin.parent / "astrbot_plugin_LivingHello"
        lh = LHRecorder(root / "lh", "astrbot_plugin_LivingHello", hello_root)
        fixture.page._application = SimpleNamespace(
            host=fixture.host, data_dir=root, diagnostics=le, config=Config(),
            closed=False, effective_mode=lambda: "active")
        register_webui(SimpleNamespace(context=fixture.host, data_dir=root / "lh",
                                      diagnostics=lh, config={}, request_trace=None), fixture.host)
        for recorder in (le, lh):
            recorder.record("fixture", {"status": "failed", "reason_code": "offline_example"})
        app = fixture.app

        @asynccontextmanager
        async def lifespan(_app):
            yield
            await fixture.asyncTearDown()
            await store.close()
            await asyncio.to_thread(le.close)
            await asyncio.to_thread(lh.close)
        app.router.lifespan_context = lifespan

        @app.get("/api/plugin/page/bridge-sdk.js")
        async def sdk():
            return Response((host / "astrbot/dashboard/plugin_page_bridge.js").read_text(),
                            media_type="application/javascript")
        # Prefer the fixture's SDK route over the native service locator while
        # preserving the host's authentication middleware and SDK bytes.
        app.router.routes.insert(0, app.router.routes.pop())

        parent = """
window.addEventListener("message", async event => {
  const message = event.data;
  if (event.source !== window || message?.channel !== "astrbot-plugin-page") return;
  if (message.kind === "ready") {
    window.postMessage({channel:message.channel, kind:"context", context:{locale:"zh-CN"}}, location.origin);
  }
  if (message.kind !== "request") return;
  const reply = {channel:message.channel, kind:"response", requestId:message.requestId};
  try {
    if (message.action !== "files:download") throw new Error("Export-only fixture");
    const plugin = location.pathname.includes("/le/") ? "astrbot_plugin_livingemotion" : "astrbot_plugin_LivingHello";
    const bad = new URLSearchParams(location.search).get("mode") === "expired";
    const response = await fetch("/api/v1/plugins/extensions/" + plugin + "/" + message.endpoint,
      {headers:{Authorization:"Bearer " + (bad ? "" : __TOKEN__)}});
    if (!response.ok) throw new Error(String(response.status));
    const link = document.createElement("a");
    const blob = URL.createObjectURL(await response.blob());
    link.href = blob;
    link.download = response.headers.get("content-disposition")?.match(/filename="([^"]+)"/)?.[1] || "diagnostics.zip";
    document.body.append(link); link.click(); link.remove();
    setTimeout(() => URL.revokeObjectURL(blob), 0);
    window.postMessage({...reply, ok:true, data:{filename:link.download}}, location.origin);
  } catch (error) {
    window.postMessage({...reply, ok:false, error:error.message}, location.origin);
  }
});
"""
        import json
        parent = parent.replace("__TOKEN__", json.dumps(fixture.token))
        for name, directory in (("le", plugin / "pages/livingemotion"),
                                ("lh", hello_root / "pages/guard")):
            def page_factory(source):
                async def page():
                    html = object.__new__(PluginPageService).process_plugin_page_html(source.read_text(), theme=None)
                    response = HTMLResponse(html.replace("<head>", "<head><script>" + parent + "</script>", 1))
                    response.set_cookie("astrbot_dashboard_jwt", fixture.token, httponly=True, samesite="strict")
                    return response
                return page
            app.add_api_route(f"/diagnostics/{name}/index.html", page_factory(directory / "index.html"))
            app.mount(f"/diagnostics/{name}", StaticFiles(directory=directory))
        return app
    uvicorn.run(asyncio.run(prepare()), host="127.0.0.1", port=args.port, log_level="warning")


if __name__ == "__main__":
    main()
