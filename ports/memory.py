"""Memory boundary values. Host events are passed separately, never serialized."""

from __future__ import annotations

from dataclasses import dataclass
from enum import Enum
from typing import Protocol

from ..contracts import Context, EvidenceRef, stable_key


class MemoryMode(str, Enum):
    NONE = "none"
    LOCAL_LITE = "local_lite"
    LOCAL_VECTOR = "local_vector"
    EXTERNAL = "external"


@dataclass(frozen=True)
class Material:
    evidence: EvidenceRef
    text: str

    def __post_init__(self) -> None:
        if not isinstance(self.text, str) or not self.text.strip() or len(self.text) > 16000:
            raise ValueError("material_text_invalid")


@dataclass(frozen=True)
class MemoryRequest:
    request_id: str
    purpose: str
    context: Context
    query: str = ""
    limit: int = 4

    def __post_init__(self) -> None:
        for value in (self.request_id, self.purpose):
            if not isinstance(value, str) or not value.strip() or len(value) > 256:
                raise ValueError("memory_request_identifier_invalid")
        if not isinstance(self.query, str) or len(self.query) > 4096:
            raise ValueError("memory_query_invalid")
        if type(self.limit) is not int or not 1 <= self.limit <= 20:
            raise ValueError("memory_limit_invalid")

    @property
    def key(self) -> str:
        return stable_key(self.request_id, self.purpose, self.context)


@dataclass(frozen=True)
class MemoryCapabilities:
    mode: MemoryMode
    recall: bool
    background_recall: bool
    append_experience: bool = False
    reason_codes: tuple[str, ...] = ()


@dataclass(frozen=True)
class RecallResult:
    materials: tuple[Material, ...] = ()
    reason_codes: tuple[str, ...] = ()
    reused: bool = False


@dataclass(frozen=True)
class ValidationResult:
    valid: bool
    materials: tuple[Material, ...] = ()
    reason_codes: tuple[str, ...] = ()


@dataclass(frozen=True)
class AppendResult:
    accepted: bool = False
    reason_code: str = "export_unsupported"


class MemoryPort(Protocol):
    def capabilities(self) -> MemoryCapabilities: ...

    async def recall(
        self,
        request: MemoryRequest,
        *,
        event: object | None = None,
        available: tuple[Material, ...] = (),
    ) -> RecallResult: ...

    async def validate_evidence(
        self,
        request: MemoryRequest,
        materials: tuple[Material, ...],
        *,
        event: object | None = None,
    ) -> ValidationResult: ...

    async def append_experience(
        self,
        request: MemoryRequest,
        material: Material,
        *,
        idempotency_key: str,
    ) -> AppendResult: ...
