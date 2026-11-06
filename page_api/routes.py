"""Host-registered private console handlers; no autonomous tasks or business I/O."""

from .errors import ConsoleError, public_error
from .guard import require_dashboard_user
from .protocols import ConsoleApplication, HostContext
from .validation import body_parameters, query_parameters

PLUGIN_NAME = "astrbot_plugin_livingemotion"
RESPONSE_HEADERS = {"Cache-Control": "no-store", "Pragma": "no-cache"}
ROUTES = (
    ("state", "GET"), ("records", "GET"), ("config", "POST"),
    ("preview", "POST"), ("action", "POST"),
)


class PageAPI:
    def __init__(self, host_context: HostContext, application: ConsoleApplication):
        self._host = host_context
        self._application = application
        self._closed = False

    def register(self) -> None:
        if self._closed:
            raise RuntimeError("A stopped console cannot be registered again")
        for operation, method in ROUTES:
            self._host.register_web_api(
                f"/{PLUGIN_NAME}/console/{operation}",
                getattr(self, operation), [method],
                f"livingEmotion authenticated console {operation}",
            )

    def stop_accepting(self) -> None:
        self._closed = True

    async def state(self):
        return await self._dispatch("state")

    async def records(self):
        return await self._dispatch("records")

    async def config(self):
        return await self._dispatch("config")

    async def preview(self):
        return await self._dispatch("preview")

    async def action(self):
        return await self._dispatch("action")

    async def _dispatch(self, operation: str):
        from astrbot.api.web import json_response, request

        try:
            actor_id = require_dashboard_user(self._host, request)
            if self._closed:
                raise ConsoleError("unavailable")
            expected_method = "GET" if operation in ("state", "records") else "POST"
            if request.method != expected_method:
                raise ConsoleError("validation_error")
            if expected_method == "GET":
                parameters = query_parameters(operation, request.query)
            else:
                parameters = await body_parameters(operation, request)
            if operation in ("config", "action"):
                parameters["actor_id"] = actor_id
            # Parsing may yield; never start business work on a stopped instance.
            if self._closed:
                raise ConsoleError("unavailable")
            if require_dashboard_user(self._host, request) != actor_id:
                raise ConsoleError("forbidden")
            method = "update_config" if operation == "config" else f"console_{operation}"
            result = await getattr(self._application, method)(**parameters)
            if self._closed:
                raise ConsoleError("unavailable")
            require_dashboard_user(self._host, request)
            self._validate_result(operation, result, parameters)
            return json_response({"status": "ok", "data": result}, headers=RESPONSE_HEADERS)
        except Exception as exc:
            error = public_error(exc)
            return json_response(
                {
                    "status": "error", "code": error.code,
                    "message": f"[livingemotion:{error.code}] {error.message}", "data": None,
                },
                status_code=error.status_code, headers=RESPONSE_HEADERS,
            )

    @staticmethod
    def _validate_result(operation: str, result, parameters: dict) -> None:
        if not isinstance(result, dict) or result.get("api_version") != 1:
            raise ConsoleError("unavailable")
        if operation == "preview":
            if result.get("model_calls") != 0 or result.get("sends") != 0:
                raise ConsoleError("unavailable")
        if operation == "records":
            items, total = result.get("items"), result.get("total")
            if (
                not isinstance(items, list) or len(items) > 10
                or type(total) is not int or total < len(items)
                or result.get("page") != parameters["page"] or result.get("page_size") != 10
            ):
                raise ConsoleError("unavailable")
