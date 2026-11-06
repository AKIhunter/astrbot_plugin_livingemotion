"""One native-persona resolver for both foreground and background work.

The host bridge supplies NativePersona through the public host contract. There
is deliberately no provider/model fallback and no bundled character prompt.
"""

from __future__ import annotations

from collections import OrderedDict
from collections.abc import Awaitable, Callable
from dataclasses import dataclass, replace
from uuid import uuid4

from ..contracts import Context, stable_key


@dataclass(frozen=True)
class NativePersona:
    persona_id: str
    prompt: str
    revision: str = "0"

    def __post_init__(self) -> None:
        if not self.persona_id or not isinstance(self.prompt, str) or not self.revision:
            raise ValueError("native_persona_invalid")


@dataclass(frozen=True)
class PersonaSnapshot:
    context: Context
    prompt: str
    mode: str


class PersonaAdapter:
    def __init__(
        self,
        resolve_native: Callable[[str, str | None], Awaitable[NativePersona]],
        *,
        mode: str = "follow",
        persona_id: str | None = None,
    ):
        if mode not in {"follow", "explicit", "none"}:
            raise ValueError("persona_mode_invalid")
        if mode == "explicit" and not persona_id:
            raise ValueError("explicit_persona_required")
        self.resolve_native = resolve_native
        self.mode = mode
        self.persona_id = persona_id
        self._versions: OrderedDict[str, tuple[str, str]] = OrderedDict()

    async def resolve(self, context: Context) -> PersonaSnapshot:
        if not context.route:
            raise ValueError("native_route_required")
        if self.mode == "none":
            persona = NativePersona("none", "", "none")
        else:
            persona = await self.resolve_native(
                context.route,
                self.persona_id if self.mode == "explicit" else None,
            )
            if not isinstance(persona, NativePersona):
                raise ValueError("native_persona_contract_invalid")
            if self.mode == "explicit" and persona.persona_id != self.persona_id:
                raise ValueError("explicit_persona_mismatch")
        fingerprint = stable_key(self.mode, persona.persona_id, persona.prompt, persona.revision)
        key = stable_key(context.bot_id, context.adapter_id, context.route)
        previous = self._versions.get(key)
        revision = previous[1] if previous and previous[0] == fingerprint else uuid4().hex
        self._versions[key] = (fingerprint, revision)
        self._versions.move_to_end(key)
        while len(self._versions) > 512:
            self._versions.popitem(last=False)
        return PersonaSnapshot(
            replace(context, persona_id=persona.persona_id, persona_revision=revision),
            persona.prompt,
            self.mode,
        )

    async def validate(self, snapshot: PersonaSnapshot) -> bool:
        try:
            current = await self.resolve(snapshot.context)
            return current.context == snapshot.context and current.mode == snapshot.mode
        except Exception:  # noqa: BLE001 - native resolution failure invalidates pending work.
            return False

    @staticmethod
    def foreground_suffix(state_text: str, *, max_chars: int = 1000) -> str:
        """Never repeat the native persona already installed in the host request."""
        if max_chars < 0:
            raise ValueError("state_budget_invalid")
        return state_text[:max_chars]


class AstrBotPersonaSource:
    """Native selection bridge; host-specific conversation/rendering stay injected.

    The signature of resolve_selected_persona was verified by host_contract
    against AstrBot 4.29.4. No conversation is fabricated for background work.
    """

    def __init__(
        self,
        persona_manager,
        *,
        conversation_persona: Callable[[str], Awaitable[str | None]],
        platform_name: Callable[[str], str],
        render: Callable[[object], str],
        explicit_lookup: Callable[[str], Awaitable[NativePersona]] | None = None,
    ):
        self.persona_manager = persona_manager
        self.conversation_persona = conversation_persona
        self.platform_name = platform_name
        self.render = render
        self.explicit_lookup = explicit_lookup

    async def __call__(self, route: str, explicit_id: str | None) -> NativePersona:
        if explicit_id is not None:
            if self.explicit_lookup is None:
                raise ValueError("native_explicit_lookup_unavailable")
            return await self.explicit_lookup(explicit_id)
        conversation_id = await self.conversation_persona(route)
        persona_id, persona, _, special = await self.persona_manager.resolve_selected_persona(
            umo=route,
            conversation_persona_id=conversation_id,
            platform_name=self.platform_name(route),
        )
        if special:
            raise ValueError("native_webchat_special_rendering_required")
        if persona_id == "[%None]":
            return NativePersona("[%None]", "")
        if not persona_id or persona is None:
            raise ValueError("native_persona_unavailable")
        return NativePersona(persona_id, self.render(persona))
