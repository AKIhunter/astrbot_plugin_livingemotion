"""Read-only identity projection over the optional public event facade."""

from __future__ import annotations

import asyncio
from collections.abc import Callable, Iterable, Mapping
from dataclasses import dataclass, replace
from typing import Any

from ..contracts import Context, SceneKind, stable_key


def context_from_event(
    event: object,
    *,
    host_instance_id: str,
    platform: str,
    persona_id: str,
    persona_revision: str,
    audience: tuple[str, ...],
) -> Context:
    """Build a source scope using the host_contract-verified native event fields.

    Canonical platform and audience come from the trusted host bridge, not the
    caller's chat text. UMO is preserved byte-for-byte and is never reconstructed.
    """
    meta = event.platform_meta
    adapter_id, adapter_type = meta.id, meta.name
    self_id, account_id = str(event.get_self_id() or ""), str(event.get_sender_id() or "")
    route = event.unified_msg_origin
    if not all(
        isinstance(value, str) and value.strip()
        for value in (
            host_instance_id,
            platform,
            adapter_id,
            adapter_type,
            self_id,
            account_id,
            route,
        )
    ):
        raise ValueError("native_source_incomplete")
    parts = route.split(":", 2)
    if len(parts) != 3 or parts[0] != adapter_id or not parts[2]:
        raise ValueError("native_route_mismatch")
    group = str(event.get_group_id() or "")
    if parts[1] == "GroupMessage" and group:
        kind, scene = "group", group
    elif parts[1] in {"FriendMessage", "PrivateMessage"} and not group:
        kind, scene = "private", account_id
    else:
        raise ValueError("native_scene_unsupported")
    if not audience:
        raise ValueError("native_audience_required")
    context = Context(
        bot_id=stable_key(host_instance_id, adapter_id, adapter_type, platform, self_id),
        persona_id=persona_id,
        adapter_id=adapter_id,
        platform=platform,
        scene_kind=kind,
        scene_id=scene,
        account_id=account_id,
        persona_revision=persona_revision,
        audience=audience,
        route=route,
    )
    if not is_real_event(event, context):
        raise ValueError("native_event_not_real")
    return context


def same_value_alias(value: Mapping[str, Any]) -> str:
    one, person = value.get("one_id"), value.get("person_id")
    if one and person and one != person:
        raise ValueError("identity_alias_conflict")
    result = one or person
    if not isinstance(result, str) or not result.strip():
        raise ValueError("identity_id_missing")
    return result


def is_real_event(event: object | None, context: Context) -> bool:
    """Only the host may supply events; reject known synthetic entry points."""
    if event is None or not context.route:
        return False
    origin = getattr(event, "unified_msg_origin", None)
    if origin != context.route or origin.split(":", 1)[0] in {"cron", "agent_wakeup"}:
        return False
    try:
        getter = getattr(event, "get_extra", None)
        if callable(getter):
            for key in ("cron", "agent_wakeup", "is_cron", "is_agent_wakeup"):
                value = getter(key)
                if value is True or (type(value) is int and value != 0):
                    return False
                if isinstance(value, str) and value.casefold().strip() in {"true", "1"}:
                    return False
        return str(event.get_sender_id()) == context.account_id
    except Exception:  # noqa: BLE001 - host adapter failures deny event authority.
        return False


@dataclass(frozen=True)
class IdentitySnapshot:
    context: Context
    one_id: str
    source_account: str
    accounts: tuple[tuple[str, str], ...]
    provider_token: int = 0
    owner_account: str = ""
    owner_one_id: str = ""
    reason_codes: tuple[str, ...] = ()

    @property
    def person_id(self) -> str:
        return self.one_id

    @property
    def fingerprint(self) -> str:
        return stable_key(
            self.context,
            self.one_id,
            self.accounts,
            self.owner_account,
            self.owner_one_id,
            self.provider_token,
        )

    def project_sources(self, sources: Iterable[Context]) -> tuple[Context, ...]:
        """Return original source keys, not copied evidence or a new binding table."""
        return tuple(source for source in sources if self._allows_source(source))

    def _allows_source(self, source: Context) -> bool:
        target = self.context
        if (source.instance_id != target.instance_id
                or source.bot_id != target.bot_id
                or source.persona_id != target.persona_id
                or source.scene_kind != target.scene_kind
                or (source.platform, source.account_id) not in self.accounts):
            return False
        if source.account_key == target.account_key:
            return set(source.audience) == set(target.audience)
        if not self.provider_token:
            return False
        # Account membership does not authorize another room, thread or audience.
        if source.scene_kind != SceneKind.PRIVATE:
            return (source.scope_key == target.scope_key
                    and bool(source.audience)
                    and set(source.audience) == set(target.audience))
        if (source.platform, source.account_id) == (target.platform, target.account_id):
            return False
        if not source.audience or not target.audience:
            return False
        members = {platform + ":" + account for platform, account in self.accounts}

        def audience(context: Context) -> set[tuple[str, ...]]:
            # Only provider-qualified account identifiers are interchangeable.
            # Unknown audience labels must match literally, never be inferred.
            return {("bound_subject",) if member in members else ("audience", member)
                    for member in context.audience}

        return audience(source) == audience(target)


class IdentityAdapter:
    def __init__(
        self, provider: Callable[[], object | None] = lambda: None, *, timeout: float = 2.0
    ):
        self.provider = provider
        self.timeout = timeout

    @staticmethod
    def local(context: Context, reason: str = "identity_service_unavailable") -> IdentitySnapshot:
        # The host/bot/adapter are deliberately part of the unbound identity.
        key = stable_key(context.bot_id, context.adapter_id, context.platform, context.account_id)
        revision = "local:" + key
        return IdentitySnapshot(
            replace(context, identity_revision=revision),
            "account:" + key,
            context.platform + ":" + context.account_id,
            ((context.platform, context.account_id),),
            reason_codes=(reason,),
        )

    async def resolve(self, context: Context, *, event: object | None = None) -> IdentitySnapshot:
        if not context.account_id:
            raise ValueError("identity_source_account_missing")
        if not is_real_event(event, context):
            return self.local(context, "identity_background_unsupported")
        try:
            provider = self.provider()
            method = getattr(provider, "resolve_identity_context", None)
            if not callable(method):
                return self.local(context)
            value = await asyncio.wait_for(
                method(event, persona_id=context.persona_id),
                self.timeout,
            )
            if self.provider() is not provider:
                return self.local(context, "identity_provider_changed")
            one_id = same_value_alias(value)
            for name in ("platform", "account_id", "scene_kind", "scene_id", "persona_id"):
                if value.get(name) != getattr(context, name):
                    raise ValueError("identity_source_mismatch")
            if value.get("origin_session_id") != context.route:
                raise ValueError("identity_route_mismatch")
            account = context.platform + ":" + context.account_id
            if value.get("source_account") != account or not value.get("audience"):
                raise ValueError("identity_source_missing")
            revision = value.get("identity_revision")
            if isinstance(revision, bool) or not isinstance(revision, (str, int)):
                return self.local(context, "identity_revision_missing")
            if not str(revision).strip():
                return self.local(context, "identity_revision_missing")
            accounts = {(context.platform, context.account_id)}
            if value.get("is_bound") is True:
                for row in value.get("bound_accounts", ()):
                    pair = (row["platform"], row["account_id"])
                    if not all(isinstance(part, str) and part for part in pair):
                        raise ValueError("identity_account_invalid")
                    accounts.add(pair)
            return IdentitySnapshot(
                replace(context, identity_revision="livingmemory:" + str(revision)),
                one_id,
                account,
                tuple(sorted(accounts)),
                id(provider),
                value.get("owner_account") or "",
                value.get("owner_one_id") or "",
            )
        except Exception:  # noqa: BLE001 - optional provider failures isolate the account.
            return self.local(context, "identity_resolution_failed")

    async def validate(self, snapshot: IdentitySnapshot, *, event: object | None = None) -> bool:
        current = await self.resolve(snapshot.context, event=event)
        return current.fingerprint == snapshot.fingerprint

    async def project_sources(
        self,
        snapshot: IdentitySnapshot,
        sources: Iterable[Context],
        *,
        event: object | None = None,
    ) -> tuple[Context, ...]:
        """Revalidate membership before exposing source keys to a consumer."""
        if not await self.validate(snapshot, event=event):
            return ()
        return snapshot.project_sources(sources)
