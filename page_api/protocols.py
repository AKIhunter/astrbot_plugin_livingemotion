"""Page-facing application port; no business storage or host runtime imports."""

from collections.abc import Callable, Mapping
from typing import Any, Protocol


class ConsoleApplication(Protocol):
    async def console_state(self, context_id: str = "") -> dict: ...

    async def console_records(
        self, context_id: str, kind: str, page: int = 1,
        page_size: int = 10, query: str = "",
    ) -> dict: ...

    async def update_config(
        self, patch: dict, *, expected_revision: str | int,
        reason: str, actor_id: str, context_id: str = "",
    ) -> dict: ...

    async def console_preview(self, context_id: str) -> dict: ...

    async def console_action(
        self, context_id: str, action: str, *, expected_revision: str | int,
        reason: str, actor_id: str, confirmed: bool,
    ) -> dict: ...


class HostContext(Protocol):
    def get_config(self) -> Mapping[str, Any]: ...

    def register_web_api(
        self, route: str, view_handler: Callable, methods: list[str], desc: str,
    ) -> None: ...
