"""Narrow host bridge. No host imports are required for offline domain tests."""

from __future__ import annotations

import weakref
from collections import OrderedDict
from dataclasses import dataclass, replace

from ..contracts import ActorRole, Context, Event, SceneKind, stable_key
from .identity import IdentityAdapter, IdentitySnapshot, context_from_event
from .persona import NativePersona, PersonaAdapter, PersonaSnapshot


@dataclass(frozen=True)
class Source:
    context: Context
    persona: PersonaSnapshot
    identity: IdentitySnapshot
    event_ref: object

    def event(self):
        return self.event_ref()


class AstrBotBridge:
    def __init__(self, host, instance_id, config):
        self.host, self.instance_id, self.config = host, instance_id, config
        self.sources: OrderedDict[str, Source] = OrderedDict()
        self.identity = IdentityAdapter(lambda: self.discover("astrbot_plugin_livingmemory"))
        self.persona = PersonaAdapter(self.resolve_native)

    def discover(self, name):
        meta = self.host.get_registered_star(name)
        return getattr(meta, "star_cls", None) if meta and meta.activated else None

    async def resolve_native(self, route, explicit_id):
        manager = self.host.persona_manager
        if explicit_id:
            persona = await manager.get_persona(explicit_id)
            if persona is None:
                raise ValueError("native_persona_unavailable")
            return NativePersona(explicit_id, persona.system_prompt,
                                 stable_key(persona.system_prompt, persona.begin_dialogs))
        conversations = self.host.conversation_manager
        cid = await conversations.get_curr_conversation_id(route)
        conv = await conversations.get_conversation(route, cid) if cid else None
        source = next((s for s in self.sources.values() if s.context.route == route), None)
        platform = source.event().platform_meta.name if source and source.event() else ""
        pid, persona, _, special = await manager.resolve_selected_persona(
            umo=route, conversation_persona_id=conv.persona_id if conv else None,
            platform_name=platform,
        )
        if special:
            raise ValueError("webchat_special_persona_unsupported")
        if pid == "[%None]":
            return NativePersona(pid, "")
        if not pid or persona is None:
            raise ValueError("native_persona_unavailable")
        return NativePersona(pid, persona["prompt"],
                             stable_key(persona["prompt"], persona.get("begin_dialogs", [])))

    async def normalize(self, event, now):
        config = self.config()
        self.persona.mode, self.persona.persona_id = config.persona_mode, config.persona_id or None
        adapter = event.platform_meta.name
        platform = {"aiocqhttp": "qq", "qq_official": "qq", "qq": "qq",
                    "telegram": "telegram", "discord": "discord"}.get(adapter, adapter)
        account, bot, group = str(event.get_sender_id()), str(event.get_self_id()), str(
            event.get_group_id() or "")
        if not account or account == bot:
            raise ValueError("not_human_source")
        audience = (("group:" + stable_key(event.platform_meta.id, platform, group),)
                    if group else (platform + ":" + bot, platform + ":" + account))
        base = replace(context_from_event(
            event, host_instance_id=self.instance_id, platform=platform,
            persona_id="unresolved", persona_revision="unresolved", audience=audience,
        ), instance_id=self.instance_id)
        # WebChat's default needs a different host renderer; never silently substitute.
        if adapter == "webchat":
            raise ValueError("webchat_special_persona_unsupported")
        persona = await self.persona.resolve(base)
        identity = await self.identity.resolve(persona.context, event=event)
        persona = replace(persona, context=identity.context)
        source = Source(identity.context, persona, identity, weakref.ref(event))
        self.sources[source.context.account_key] = source
        self.sources.move_to_end(source.context.account_key)
        while len(self.sources) > 128:
            self.sources.popitem(last=False)
        message = event.message_obj
        source_id = str(getattr(message, "message_id", "") or "")
        if not source_id:
            raise ValueError("native_message_id_required")
        timestamp = getattr(message, "timestamp", now)
        if hasattr(timestamp, "timestamp"):
            timestamp = timestamp.timestamp()
        if not isinstance(timestamp, (int, float)) or timestamp <= 0:
            timestamp = now
        normalized = Event(
            event_id=source_id, producer="astrbot", event_type="message",
            context=source.context, actor_role=ActorRole.HUMAN,
            occurred_at=min(float(timestamp), now), source_id=source_id, actor_id=account,
            body=str(event.message_str or "")[:config.body_max_chars],
        )
        return source, normalized

    def source(self, context):
        source = self.sources.get(context.account_key)
        if source and replace(source.context, route=context.route) == context:
            return source
        return None

    async def current(self, context):
        source = self.source(context)
        if not source:
            return None
        config = self.config()
        self.persona.mode, self.persona.persona_id = config.persona_mode, config.persona_id or None
        if not await self.persona.validate(source.persona):
            return None
        if not await self.identity.validate(source.identity, event=source.event()):
            # A real event is required for LM; do not fabricate one for background use.
            if source.identity.provider_token or not source.context.identity_revision.startswith("local:"):
                return None
            if self.discover("astrbot_plugin_livingmemory") is not None:
                return None
        return source

    def conflicts(self, context=None):
        plugin = self.discover("astrbot_plugin_congling")
        if plugin is None:
            return False
        source = self.source(context) if context else None
        method = getattr(plugin, "enabled_for", None)
        if source and source.event() and callable(method):
            try:
                return method(source.event()) is not False
            except Exception:
                pass
        # No verified negative scope decision: defer instead of guessing its config.
        return True

    async def recorded_route(self, context):
        source = await self.current(context)
        if not source or source.context.scene_kind == SceneKind.PUBLIC_COMMENT:
            return None
        return source.context.route

    @staticmethod
    def text_part(text):
        from astrbot.core.agent.message import TextPart
        return TextPart(text=text)

    @staticmethod
    def chain(text):
        from astrbot.api.event import MessageChain
        return MessageChain().message(text)
