"""天气权重因子的离线测试：调度锚点、预报兜底、降级恢复、平滑与零重复请求。"""

from datetime import datetime
from types import SimpleNamespace
from zoneinfo import ZoneInfo

import pytest

from astrbot_plugin_livingemotion.adapters.weather import WeatherReport
from astrbot_plugin_livingemotion.runtime.weather_factor import NEUTRAL, WeatherFactor

NOW = 1794484800.0  # 2026-11-14 12:00 UTC
ZONE = "UTC"
CITY = "成都"
DAY = datetime.fromtimestamp(NOW, ZoneInfo(ZONE)).date().isoformat()
RAIN = (-0.05, -0.02, 0.03, 0.02)
SUN = (0.04, 0.01, -0.02, 0.0)


def config(**changes):
    values = {"home_city": CITY, "timezone": ZONE, "weather_factor_enabled": True,
              "weather_poll_seconds": 14400, "weather_transition_seconds": 900,
              "weather_weight_scale": 1.0, "weather_stale_seconds": 7200,
              "weather_forecast_days": 7, "weather_forecast_refresh_seconds": 21600,
              "weather_window_start_hour": 6, "weather_window_end_hour": 1,
              "weather_degrade_after_failures": 3, "weather_recover_after_successes": 2}
    values.update(changes)
    return SimpleNamespace(**values)


class Stub:
    """记录调用次数的天气替身；实况与预报可分别切换返回码或抛错。"""

    def __init__(self, code=61, error=None, forecast_error=None):
        self.code, self.error, self.calls = code, error, 0
        self.forecast_error = forecast_error
        self.forecast_calls = 0

    async def get_current(self, city, zone):
        self.calls += 1
        if self.error is not None:
            raise self.error
        return WeatherReport(city, DAY, zone, "ok", f"code-{self.code}", code=self.code)

    async def get_forecast(self, city, zone, days):
        self.forecast_calls += 1
        if self.forecast_error is not None:
            raise self.forecast_error
        return {DAY: WeatherReport(city, DAY, zone, "ok", f"code-{self.code}", code=self.code)}


class Clock:
    def __init__(self, value=NOW):
        self.value = value

    def __call__(self):
        return self.value


def build(code=61, *, cfg=None, clock=None, stub=None):
    stub = stub or Stub(code)
    clock = clock or Clock()
    factor = WeatherFactor(config=lambda: cfg or config(), weather=stub, clock=clock)
    return factor, stub, clock


# ---------------- 调度：窗口与锚点 ----------------

def test_schedule_aligns_to_four_hour_anchors():
    factor, _, _ = build(61)
    assert factor._delay() == 7200.0  # 12:00 -> 14:00


def test_schedule_hourly_uses_every_hour():
    factor, _, _ = build(61, cfg=config(weather_poll_seconds=3600))
    assert factor._delay() == 3600.0  # 12:00 -> 13:00


def test_schedule_outside_window_waits_for_next_start():
    factor, _, clock = build(61)
    clock.value = NOW + 11 * 3600  # 23:00，窗口已过
    assert factor._delay() == 7 * 3600  # 次日 06:00


def test_schedule_counts_slots_inside_window():
    """06:00–01:00 窗口内：4 小时 5 次，1 小时 20 次，都远低于限频。"""
    def slots(interval):
        cfg = config(weather_poll_seconds=interval)
        factor, _, clock = build(61, cfg=cfg)
        clock.value = NOW - 12 * 3600  # 00:00 起算
        base, cursor, points = clock.value, clock.value, []
        for _ in range(40):
            cursor = factor._next_slot(cursor, cfg, ZONE)
            points.append(cursor - base)
            clock.value = cursor
        return [p for p in points if p < 24 * 3600]
    assert len(slots(14400)) == 5
    assert len(slots(3600)) == 20


# ---------------- 抓取与兜底 ----------------

@pytest.mark.asyncio
async def test_poll_success_publishes_live_weight():
    factor, stub, _ = build(61)
    snap = await factor.poll_once()
    assert stub.calls == 1
    assert snap.source == "live" and snap.code == 61
    assert snap.target == RAIN and snap.weights == RAIN
    assert factor.drift() == RAIN


@pytest.mark.asyncio
async def test_snapshot_is_synchronous_and_never_requests():
    factor, stub, _ = build(61)
    await factor.poll_once()
    for _ in range(20):
        assert factor.snapshot().source == "live"
    assert stub.calls == 1
    assert stub.forecast_calls == 1


@pytest.mark.asyncio
async def test_live_failure_falls_back_to_forecast():
    """实况挂了不该掉到中性：7 天预报表里今天那一格就是兜底。"""
    factor, stub, _ = build(61)
    await factor.poll_once()
    stub.error = RuntimeError("timeout")
    snap = await factor.poll_once()
    assert snap.source == "forecast" and snap.code == 61
    assert factor.drift() == RAIN


@pytest.mark.asyncio
async def test_forecast_table_is_not_refetched_within_refresh_window():
    factor, stub, clock = build(61)
    await factor.poll_once()
    for step in (1, 2, 3):
        clock.value = NOW + step * 1800
        await factor.poll_once()
    assert stub.forecast_calls == 1


@pytest.mark.asyncio
async def test_failure_keeps_last_weight_without_forecast():
    factor, stub, _ = build(61, stub=Stub(61, error=None, forecast_error=RuntimeError("no")))
    await factor.poll_once()
    stub.error = RuntimeError("boom")
    snap = await factor.poll_once()
    assert snap.source == "cache" and snap.failures == 1
    assert factor.drift() == RAIN
    assert stub.calls == 2


@pytest.mark.asyncio
async def test_stale_cache_degrades_to_neutral():
    factor, stub, clock = build(61, stub=Stub(61, forecast_error=RuntimeError("no")))
    await factor.poll_once()
    stub.error = RuntimeError("boom")
    clock.value = NOW + 7201
    snap = factor.snapshot()
    assert snap.source == "stale"
    assert snap.weights == NEUTRAL
    assert factor.drift() is None


@pytest.mark.asyncio
async def test_first_failure_without_any_source_is_neutral():
    factor, _, _ = build(
        stub=Stub(error=RuntimeError("down"), forecast_error=RuntimeError("down")))
    snap = await factor.poll_once()
    assert snap.source == "neutral" and snap.weights == NEUTRAL
    assert factor.drift() is None


@pytest.mark.asyncio
async def test_disabled_or_missing_city_is_neutral():
    factor, stub, _ = build(cfg=config(home_city=""))
    assert factor.snapshot().source == "disabled"
    assert await factor.poll_once() is not None
    assert stub.calls == 0 and stub.forecast_calls == 0
    assert factor.drift() is None


# ---------------- 降级与恢复 ----------------

@pytest.mark.asyncio
async def test_degrade_after_consecutive_failures():
    """实况与预报都挂满阈值次数，才退到每日粒度。"""
    factor, _, _ = build(
        stub=Stub(error=RuntimeError("down"), forecast_error=RuntimeError("down")))
    for expected in (1, 2):
        await factor.poll_once()
        assert factor._degraded is False and factor._failures == expected
    await factor.poll_once()
    assert factor._degraded is True
    assert factor._interval(factor._config()) == 86400.0


@pytest.mark.asyncio
async def test_degraded_mode_skips_live_requests():
    factor, stub, _ = build(
        stub=Stub(error=RuntimeError("down"), forecast_error=RuntimeError("down")))
    for _ in range(3):
        await factor.poll_once()
    assert factor._degraded is True
    before = stub.calls
    await factor.poll_once()
    assert stub.calls == before  # 降级期不再打实况


@pytest.mark.asyncio
async def test_recover_after_daily_successes():
    stub = Stub(error=RuntimeError("down"), forecast_error=RuntimeError("down"))
    factor, _, clock = build(stub=stub)
    for _ in range(3):
        await factor.poll_once()
    assert factor._degraded is True
    stub.forecast_error = None  # 预报恢复，实况仍坏
    await factor.poll_once()
    assert factor._recover_streak == 1 and factor._degraded is True
    clock.value = NOW + 86400
    await factor.poll_once()
    assert factor._degraded is False


@pytest.mark.asyncio
async def test_forecast_fallback_does_not_trigger_degrade():
    """预报还能兜底说明数据源活着，不该降级。"""
    factor, stub, _ = build(61)
    await factor.poll_once()
    stub.error = RuntimeError("timeout")
    for _ in range(5):
        await factor.poll_once()
    assert factor._degraded is False and factor._failures == 0


# ---------------- 平滑与缩放 ----------------

@pytest.mark.asyncio
async def test_transition_interpolates_and_settles():
    factor, stub, clock = build(61)
    await factor.poll_once()
    stub.code = 0
    clock.value = NOW + 3600
    await factor.poll_once()
    assert factor.snapshot().weights == pytest.approx(RAIN, abs=1e-9)
    clock.value = NOW + 3600 + 450
    midway = factor.snapshot().weights
    assert midway != RAIN and midway != SUN
    clock.value = NOW + 3600 + 4500
    assert factor.snapshot().weights == pytest.approx(SUN, abs=1e-3)


@pytest.mark.asyncio
async def test_zero_transition_applies_immediately():
    factor, stub, clock = build(61, cfg=config(weather_transition_seconds=0))
    await factor.poll_once()
    stub.code = 0
    clock.value = NOW + 60
    await factor.poll_once()
    assert factor.snapshot().weights == SUN


@pytest.mark.asyncio
async def test_scale_multiplies_weight_and_zero_disables():
    factor, _, _ = build(61, cfg=config(weather_weight_scale=2.0))
    await factor.poll_once()
    assert factor.drift() == pytest.approx(tuple(v * 2 for v in RAIN))
    factor._config = lambda: config(weather_weight_scale=0)
    assert factor.drift() is None


@pytest.mark.asyncio
async def test_failure_backoff_never_crosses_next_slot():
    factor, stub, _ = build(61, stub=Stub(61, forecast_error=RuntimeError("no")))
    await factor.poll_once()
    stub.error = RuntimeError("boom")
    await factor.poll_once()
    delay = factor._delay()  # 12:00 失败，重试不超过下一个锚点 14:00
    assert 0 < delay <= 2 * 3600


@pytest.mark.asyncio
async def test_report_round_trips_live_and_forecast_snapshots():
    factor, stub, clock = build(61)
    assert factor.report() is None
    await factor.poll_once()
    report = factor.report()
    assert report is not None and report.code == 61 and report.city == CITY
    stub.error = RuntimeError("boom")
    await factor.poll_once()
    assert factor.report().code == 61
    clock.value = NOW + 7201
    assert factor.report() is None
