"""Page-facing application port; no business storage or host runtime imports."""

from collections.abc import Callable, Mapping
from typing import Any, Protocol


class ConsoleApplication(Protocol):
    async def console_state(self, context_id: str = "", persona_id: str = "",
                            view_scope: str = "", platform: str = "") -> dict: ...

    async def console_records(
        self, context_id: str, kind: str, page: int = 1,
        page_size: int = 10, query: str = "", persona_id: str = "",
        view_scope: str = "", platform: str = "",
    ) -> dict: ...

    async def update_config(
        self, patch: dict, *, expected_revision: str | int,
        reason: str, actor_id: str, context_id: str = "",
    ) -> dict: ...

    async def console_preview(self, context_id: str) -> dict: ...

    async def console_action(
        self, context_id: str, action: str, *, expected_revision: str | int,
        reason: str, actor_id: str, confirmed: bool, entry_id: str = "",
        pinned: bool | None = None, expected_pinned: bool | None = None,
    ) -> dict: ...

    async def console_scopes(self, persona_id: str = "", view_scope: str = "global",
                             context_id: str = "", platform: str = "") -> dict: ...

    async def console_relationships(
        self, persona_id: str, view_scope: str = "global", context_id: str = "",
        platform: str = "", page: int = 1, page_size: int = 10,
        query: str = "", limit: int = 200,
    ) -> dict: ...

    async def console_relationship(
        self, persona_id: str, platform: str, account_id: str, *,
        expected_version: int, actor_id: str, reason: str, context_id: str = "",
        score: float | None = None, frozen: bool | None = None,
    ) -> dict: ...

    async def console_energy(
        self, persona_id: str, view_scope: str = "global", context_id: str = "",
        platform: str = "", page: int = 1, page_size: int = 10, event_type: str = "",
    ) -> dict: ...

    async def console_settings_options(self) -> dict: ...


class HostContext(Protocol):
    def get_config(self) -> Mapping[str, Any]: ...

    def register_web_api(
        self, route: str, view_handler: Callable, methods: list[str], desc: str,
    ) -> None: ...
