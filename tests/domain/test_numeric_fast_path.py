"""F6 numeric validation compatibility and full-history regression checks."""

from copy import deepcopy
from decimal import Decimal
from fractions import Fraction
import math
import random
import struct
import sys

import pytest

from astrbot_plugin_livingemotion.contracts import finite
from astrbot_plugin_livingemotion.domain import emotion


class FloatSubclass(float):
    pass


class IntSubclass(int):
    pass


class FloatOverride(float):
    def __float__(self):
        return -0.0


class IntOverride(int):
    def __float__(self):
        return 0.25


class FloatLike:
    def __float__(self):
        return 0.5


def original_number(value, name, low=None, high=None):
    """Frozen pre-F6-fourth-round behavior, using the unchanged contract."""
    try:
        finite(value, name, low, high)
    except (OverflowError, TypeError) as exc:
        raise ValueError(f"{name}: expected finite number") from exc
    return float(value)


def exception_signature(exc):
    if exc is None:
        return None
    return (type(exc), str(exc), exception_signature(exc.__cause__),
            exception_signature(exc.__context__), exc.__suppress_context__)


def outcome(function, value, low=None, high=None):
    try:
        result = function(value, "numeric-field", low, high)
    except Exception as exc:
        return ("error", exception_signature(exc))
    return ("value", type(result), struct.pack("!d", result))


VALUES = [
    0.0, -0.0, 1.0, -1.0, 0.5,
    math.nextafter(0.0, -math.inf), math.nextafter(0.0, math.inf),
    math.nextafter(1.0, -math.inf), math.nextafter(1.0, math.inf),
    sys.float_info.max, -sys.float_info.max,
    math.nan, math.inf, -math.inf,
    0, 1, -1, 10**1000, -(10**1000), True, False,
    "0.5", None, 0.5 + 0j, Decimal("0.5"), Fraction(1, 2), FloatLike(),
    FloatSubclass(-0.0), FloatSubclass(math.inf), FloatSubclass(math.nan),
    IntSubclass(1), IntSubclass(10**1000), FloatOverride(0.5), IntOverride(1),
]
BOUNDS = [
    (None, None), (0, None), (None, 1), (0, 1), (-1.0, 1.0),
    (-0.0, 0.0), (1, 0), (-math.inf, math.inf),
    (math.nan, 1), (0, math.nan), (True, True), ("invalid", None),
    (None, "invalid"), (-(10**1000), 10**1000),
]


@pytest.mark.parametrize("value", VALUES, ids=[f"value-{i}" for i in range(len(VALUES))])
@pytest.mark.parametrize("low,high", BOUNDS, ids=[f"bounds-{i}" for i in range(len(BOUNDS))])
def test_numeric_validation_matches_original(value, low, high):
    assert outcome(emotion._number, value, low, high) == outcome(
        original_number, value, low, high,
    )


def test_float_bit_patterns_match_original():
    generator = random.Random(6404)
    for _ in range(1024):
        value = struct.unpack("!d", generator.getrandbits(64).to_bytes(8, "big"))[0]
        for low, high in ((None, None), (0, 1), (-1, 1)):
            assert outcome(emotion._number, value, low, high) == outcome(
                original_number, value, low, high,
            )


@pytest.mark.parametrize("error_type", [TypeError, OverflowError, ValueError, RuntimeError])
@pytest.mark.parametrize("side", ["low", "high"])
def test_bound_comparison_exceptions_keep_original_wrapping(error_type, side):
    class Bound:
        def __gt__(self, other):
            raise error_type("bound comparison failed")

        def __lt__(self, other):
            raise error_type("bound comparison failed")

    bounds = (Bound(), None) if side == "low" else (None, Bound())
    assert outcome(emotion._number, 0.5, *bounds) == outcome(
        original_number, 0.5, *bounds,
    )


@pytest.mark.parametrize("base", [float, int])
@pytest.mark.parametrize("error_type", [TypeError, OverflowError, ValueError, RuntimeError])
@pytest.mark.parametrize("fail_at", [1, 2])
def test_subclass_conversion_order_and_exceptions_match_original(base, error_type, fail_at):
    def run(function):
        calls = []

        class Number(base):
            def __float__(self):
                calls.append("float")
                if len(calls) == fail_at:
                    raise error_type("custom conversion failed")
                return -0.0

        return outcome(function, Number(1), 0, 1), calls

    assert run(emotion._number) == run(original_number)


def test_exact_floats_avoid_contract_dispatch_without_skipping_checks(monkeypatch):
    calls = []

    def counted(value, name, low=None, high=None):
        calls.append(value)
        return finite(value, name, low, high)

    monkeypatch.setattr(emotion, "finite", counted)
    value = -0.0
    assert emotion._number(value, "amount", 0, 1) is value
    for invalid in (math.nan, math.inf, -math.inf, -0.1, 1.1):
        with pytest.raises(ValueError, match="^amount: out of range$"):
            emotion._number(invalid, "amount", 0, 1)
    assert calls == []
    for fallback in (1, FloatSubclass(0.5), IntSubclass(1), True, "0.5"):
        assert outcome(emotion._number, fallback, 0, 1) == outcome(
            original_number, fallback, 0, 1,
        )
    assert len(calls) == 5


def guard_runtime(event):
    return {
        "version": 1, "scope_key": event.context.scope_key,
        "last_event_at": event.occurred_at,
        "seen": [{"key": f"seen-{i}", "at": event.occurred_at} for i in range(192)],
        "stimuli": [
            {"key": f"stimulus-{i}", "at": event.occurred_at, "amount": 0.0,
             "body_key": None} for i in range(192)
        ],
    }


def prepare(runtime, event):
    return emotion._prepare_guard(
        runtime, scope_key=event.context.scope_key, event=event,
        now=event.occurred_at, updated_at=event.occurred_at,
        ttl=7200.0, window=300.0, max_events=192,
    )


def test_guard_checks_every_numeric_value_at_full_capacity(le_event, monkeypatch):
    runtime = guard_runtime(le_event)
    before = deepcopy(runtime)
    calls = []
    number = emotion._number

    def counted(value, name, low=None, high=None):
        calls.append(name)
        return number(value, name, low, high)

    monkeypatch.setattr(emotion, "_number", counted)
    result, reason = prepare(runtime, le_event)
    assert reason == "guard_capacity"
    assert result == before == runtime
    assert result is not runtime and result["seen"][0] is not runtime["seen"][0]
    assert calls.count("last_event_at") == 1
    assert calls.count("seen.at") == 192
    assert calls.count("stimulus.at") == calls.count("stimulus.amount") == 192
    runtime["stimuli"][-1]["amount"] = math.nan
    with pytest.raises(ValueError, match="^stimulus.amount: out of range$"):
        prepare(runtime, le_event)


@pytest.mark.parametrize("expired", [False, True])
@pytest.mark.parametrize("position", [0, 191])
@pytest.mark.parametrize(
    "table,field,name",
    [("seen", "at", "seen.at"), ("stimuli", "at", "stimulus.at"),
     ("stimuli", "amount", "stimulus.amount")],
)
@pytest.mark.parametrize("invalid", [math.nan, math.inf, -math.inf, -1.0, True])
def test_guard_rejects_invalid_values_even_at_capacity_or_expired(
    le_event, expired, position, table, field, name, invalid,
):
    runtime = guard_runtime(le_event)
    if expired:
        for rows in (runtime["seen"], runtime["stimuli"]):
            for row in rows:
                row["at"] = 0.0
    runtime[table][position][field] = invalid
    expected = "expected finite number" if invalid is True else "out of range"
    with pytest.raises(ValueError) as caught:
        prepare(runtime, le_event)
    assert str(caught.value) == f"{name}: {expected}"
