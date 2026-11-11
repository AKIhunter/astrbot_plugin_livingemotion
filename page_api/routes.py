"""Host-registered private console handlers; no autonomous tasks or business I/O."""

from .errors import ConsoleError, public_error
from .guard import require_dashboard_user
from .protocols import ConsoleApplication, HostContext
from .validation import body_parameters, query_parameters

PLUGIN_NAME = "astrbot_plugin_livingemotion"
RESPONSE_HEADERS = {"Cache-Control": "no-store", "Pragma": "no-cache"}
ROUTES = (
    ("state", "GET"), ("records", "GET"), ("config", "POST"), ("configuration", "GET"),
    ("preview", "POST"), ("action", "POST"),
    ("scopes", "GET"), ("relationships", "GET"), ("relationship", "POST"),
    ("energy", "GET"), ("settings-options", "GET"), ("persona-description", "GET"),
    ("memory-sync", "POST"), ("behavior-simulate", "POST"),
    ("emotion-images", "GET"), ("emotion-image", "GET"), ("emotion-image-save", "POST"),
    ("experience-generate", "POST"), ("experience-task", "GET"),
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
                getattr(self, operation.replace("-", "_")), [method],
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

    async def configuration(self):
        return await self._dispatch("configuration")

    async def preview(self):
        return await self._dispatch("preview")

    async def action(self):
        return await self._dispatch("action")

    async def scopes(self):
        return await self._dispatch("scopes")

    async def relationships(self):
        return await self._dispatch("relationships")

    async def relationship(self):
        return await self._dispatch("relationship")

    async def energy(self):
        return await self._dispatch("energy")

    async def settings_options(self):
        return await self._dispatch("settings-options")

    async def persona_description(self):
        return await self._dispatch("persona-description")

    async def memory_sync(self):
        return await self._dispatch("memory-sync")

    async def behavior_simulate(self):
        return await self._dispatch("behavior-simulate")

    async def emotion_images(self):
        return await self._dispatch("emotion-images")

    async def emotion_image(self):
        return await self._dispatch("emotion-image")

    async def emotion_image_save(self):
        return await self._dispatch("emotion-image-save")

    async def experience_generate(self):
        return await self._dispatch("experience-generate")

    async def experience_task(self):
        return await self._dispatch("experience-task")

    async def _dispatch(self, operation: str):
        from astrbot.api.web import json_response, request

        try:
            actor_id = require_dashboard_user(self._host, request)
            if self._closed:
                raise ConsoleError("unavailable")
            expected_method = dict(ROUTES)[operation]
            if request.method != expected_method:
                raise ConsoleError("validation_error")
            if expected_method == "GET":
                parameters = query_parameters(operation, request.query)
            else:
                parameters = await body_parameters(operation, request)
            if operation in ("config", "action", "relationship", "memory-sync", "experience-generate", "behavior-simulate"):
                parameters["actor_id"] = actor_id
            # Parsing may yield; never start business work on a stopped instance.
            if self._closed:
                raise ConsoleError("unavailable")
            if require_dashboard_user(self._host, request) != actor_id:
                raise ConsoleError("forbidden")
            method = ("update_config" if operation == "config"
                      else f"console_{operation.replace('-', '_')}")
            handler = getattr(self._application, method, None)
            if not callable(handler):
                raise ConsoleError("unavailable")
            result = await handler(**parameters)
            if self._closed:
                raise ConsoleError("unavailable")
            if require_dashboard_user(self._host, request) != actor_id:
                raise ConsoleError("forbidden")
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
        if operation == "behavior-simulate" and result.get("sends") != 0:
            raise ConsoleError("unavailable")
        if operation in ("records", "relationships", "energy"):
            items, total = result.get("items"), result.get("total")
            if (
                not isinstance(items, list) or len(items) > 10
                or type(total) is not int or total < len(items)
                or result.get("page") != parameters["page"] or result.get("page_size") != 10
            ):
                raise ConsoleError("unavailable")
            if parameters.get("kind") == "emotion" and any(
                    not isinstance(item, dict) or "body" in item for item in items):
                raise ConsoleError("unavailable")
        if operation == "relationships":
            nodes = result.get("nodes")
            if (not isinstance(nodes, list) or len(nodes) > parameters["limit"]
                    or result.get("displayed") != len(nodes)
                    or (parameters.get("graph_scope", "matched") == "matched"
                        and len(nodes) > result["total"])
                    or not isinstance(result.get("edges"), list)
                    or len(result["edges"]) != len(nodes)):
                raise ConsoleError("unavailable")
