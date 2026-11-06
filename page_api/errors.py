"""Bounded public error surface, including message-only bridge compatibility."""

ERRORS = {
    "validation_error": (400, "Invalid console request; check fields and values."),
    "unauthorized": (401, "A valid Dashboard Bearer login is required."),
    "forbidden": (403, "Dashboard administration permission is required for this scope."),
    "version_conflict": (409, "Revision changed; reload and review before submitting again."),
    "unavailable": (503, "Service or action unavailable; no success is confirmed. Do not retry writes."),
}


class ConsoleError(Exception):
    def __init__(self, code: str):
        self.code = code
        self.status_code, self.message = ERRORS[code]
        super().__init__(self.message)


def public_error(exc: Exception) -> ConsoleError:
    # ApplicationError is deliberately a structural port, not a runtime import.
    code = getattr(exc, "code", None)
    if isinstance(code, str) and code in ERRORS:
        if getattr(exc, "status_code", None) == ERRORS[code][0]:
            return ConsoleError(code)
    return ConsoleError("unavailable")
