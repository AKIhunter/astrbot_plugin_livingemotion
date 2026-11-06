"""Read-only, revocable relationship projection over retained source ledgers."""

from __future__ import annotations

from dataclasses import replace

from ..adapters.identity import IdentityAdapter, IdentitySnapshot
from ..contracts import Relationship, RelationshipContribution, StateRecord
from ..domain.relationship import project_relationship
from ..storage import SQLiteStore
from .projector import snapshot

CONTEXT_LIMIT = 512
CONTRIBUTION_FIELDS = (
    "source_id", "account_id", "occurred_at", "delta", "reason_code", "day", "dimension",
)


async def read_relationship_projection(
    store: SQLiteStore,
    identities: IdentityAdapter,
    identity: IdentitySnapshot,
    *,
    event: object | None = None,
    record: StateRecord | None = None,
) -> Relationship | None:
    """Return a current projection, or None when authority/read freshness fails.

    identity must come from the live host bridge, never from a caller-supplied
    OneID. Persisted contexts identify ledger origins, not sending authority.
    No result is cached or persisted. The consumer must revalidate its context
    again after any later asynchronous work and before using generated output.
    """
    if not await identities.validate(identity, event=event):
        return None
    context = identity.context
    generation = await store.get_generation(context)
    if record is None:
        record = await store.get_state(context, "relationship", context.account_id)
    if record is not None and record.generation != generation:
        return None
    local = snapshot(record, Relationship)
    result = replace(local, identity_revision=context.identity_revision)
    generations = {context.scope_key: (context, generation)}
    if identity.provider_token and len(identity.accounts) > 1 and local.evidence_complete:
        contexts = await store.list_contexts(limit=CONTEXT_LIMIT)
        # A truncated inventory cannot establish a complete projection.
        if len(contexts) >= CONTEXT_LIMIT:
            return None
        sources = {source.account_key: source for source in contexts}
        sources[context.account_key] = context
        granted = await identities.project_sources(identity, sources.values(), event=event)
        if not granted:
            return None
        ledger = []
        for source in granted:
            source_generation = await store.get_generation(source)
            prior = generations.get(source.scope_key)
            if prior is not None and prior[1] != source_generation:
                return None
            generations[source.scope_key] = (source, source_generation)
            for row in await store.relationship_ledger(source):
                if (row["scope_key"] != source.scope_key
                        or row["generation"] != source_generation):
                    return None
                ledger.append((source, RelationshipContribution(**{
                    name: row[name] for name in CONTRIBUTION_FIELDS
                })))
        own = project_relationship(
            ledger, context=context, identity_revision=context.identity_revision,
        )
        fields = ("score", "trust", "familiarity", "boundary")
        if any(getattr(own, name) != getattr(local, name) for name in fields):
            # A source-only baseline is not decomposable ledger evidence.
            result = replace(result, evidence_complete=False,
                             reason_codes=("relationship_baseline_not_aggregatable",))
        else:
            result = project_relationship(
                ledger, context=context, identity_revision=context.identity_revision,
                authorized_account_keys=[source.account_key for source in granted],
            )
            result = replace(result, frozen=local.frozen,
                             updated_at=max(result.updated_at, local.updated_at))
    for source, expected in generations.values():
        if await store.get_generation(source) != expected:
            return None
    # This is the final await: a provider loss/unbind invalidates the whole result.
    if not await identities.validate(identity, event=event):
        return None
    return result
