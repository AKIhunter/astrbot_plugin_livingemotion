import asyncio
from datetime import UTC, datetime
from types import SimpleNamespace
from urllib.parse import parse_qs, urlparse

import pytest

from astrbot_plugin_livingemotion.adapters.weather import OpenMeteoWeather
from astrbot_plugin_livingemotion.runtime.environment import environment_state

NOW = datetime(2026, 11, 10, 12, tzinfo=UTC).timestamp()


def transport_for(clock, calls, mutate=None):
    async def transport(url, timeout):
        calls.append(url)
        if "geocoding-api" in url:
            return {"results": [{"latitude": 31.2, "longitude": 121.5}]}
        params = parse_qs(urlparse(url).query)
        assert params["current"] == ["weather_code,temperature_2m"]
        assert params["timeformat"] == ["unixtime"]
        result = {"timezone": params["timezone"][0],
                  "current": {"time": clock[0] - 300, "weather_code": 3, "temperature_2m": 17.5},
                  "current_units": {"time": "unixtime", "temperature_2m": "°C"}}
        if mutate:
            mutate(result)
        return result
    return transport


async def test_current_singleflight_bounded_ttl_and_clock():
    clock, calls = [NOW], []
    started, release = asyncio.Event(), asyncio.Event()
    original = transport_for(clock, calls)

    async def blocking(url, timeout):
        started.set()
        await release.wait()
        return await original(url, timeout)
    weather = OpenMeteoWeather(transport=blocking, clock=lambda: clock[0])
    try:
        first = asyncio.create_task(weather.get_current("上海", "Asia/Shanghai"))
        await started.wait()
        second = asyncio.create_task(weather.get_current("上海", "Asia/Shanghai"))
        release.set()
        a, b = await asyncio.gather(first, second)
        assert a == b and a.status == "ok" and a.temperature == 17.5
        assert a.summary == "阴 · 17.5°C" and a.day == "2026-11-10"
        assert len(calls) == 2
        clock[0] += 599
        assert await weather.get_current("上海", "Asia/Shanghai") == a
        assert len(calls) == 2
        clock[0] += 2
        assert (await weather.get_current("上海", "Asia/Shanghai")).fetched_at == clock[0]
        assert len(calls) == 4
        assert all(key[1] == "current" for key in weather._cache)
    finally:
        await weather.close()


@pytest.mark.parametrize("mode", ["stale", "future", "units", "code", "temperature", "zone", "daily"])
async def test_current_rejects_invalid_or_daily_payload_with_negative_cache(mode):
    clock, calls = [NOW], []

    def mutate(result):
        if mode == "stale":
            result["current"]["time"] = NOW - 3601
        elif mode == "future":
            result["current"]["time"] = NOW + 301
        elif mode == "units":
            result["current_units"]["temperature_2m"] = "°F"
        elif mode == "code":
            result["current"]["weather_code"] = True
        elif mode == "temperature":
            result["current"]["temperature_2m"] = float("nan")
        elif mode == "zone":
            result["timezone"] = "Asia/Tokyo"
        else:
            result["daily"] = result.pop("current")
    weather = OpenMeteoWeather(transport=transport_for(clock, calls, mutate), clock=lambda: clock[0])
    try:
        report = await weather.get_current("上海", "Asia/Shanghai")
        assert report.status == "unavailable" and report.temperature is None
        assert await weather.get_current("上海", "Asia/Shanghai") == report
        assert len(calls) == 2
    finally:
        await weather.close()


async def test_current_timeout_and_shutdown_are_bounded():
    started, release = asyncio.Event(), asyncio.Event()

    async def blocked(url, timeout):
        started.set()
        await release.wait()
    weather = OpenMeteoWeather(transport=blocked, clock=lambda: NOW, timeout=.01)
    assert (await weather.get_current("上海", "UTC")).status == "unavailable"
    assert weather.health()["inflight"] == 0
    started.clear()
    task = asyncio.create_task(weather.get_current("北京", "UTC"))
    await started.wait()
    await weather.close()
    with pytest.raises(asyncio.CancelledError):
        await task


@pytest.mark.parametrize("city,zone", [("", "UTC"), ("上海", ""), ("上海", "Invalid/Zone")])
async def test_environment_missing_configuration_never_fetches(city, zone):
    app = SimpleNamespace(config=SimpleNamespace(home_city=city, timezone=zone),
                          store=SimpleNamespace(clock=lambda: NOW))
    assert await environment_state(app) == {"enabled": False}
    assert not hasattr(app, "_manual_weather")


async def test_environment_configuration_change_during_fetch_discards_old_region():
    config = SimpleNamespace(home_city="上海", timezone="UTC")
    app = SimpleNamespace(config=config, store=SimpleNamespace(clock=lambda: NOW))

    async def current(city, zone):
        config.home_city = "北京"
        return SimpleNamespace()
    app._manual_weather = SimpleNamespace(get_current=current)
    assert await environment_state(app) == {"enabled": False}


async def test_environment_reuses_client_and_refreshes_server_clock_on_cache_hit():
    clock, calls = [NOW], []
    weather = OpenMeteoWeather(transport=transport_for(clock, calls), clock=lambda: clock[0])
    app = SimpleNamespace(config=SimpleNamespace(home_city="上海", timezone="Asia/Shanghai"),
                          store=SimpleNamespace(clock=lambda: clock[0]), _manual_weather=weather)
    try:
        first = await environment_state(app)
        clock[0] += 10
        second = await environment_state(app)
        assert second["server_time"] == NOW + 10 and first["weather"] == second["weather"]
        assert app._manual_weather is weather and len(calls) == 2
    finally:
        await weather.close()


async def test_cold_environment_does_not_wait_for_network_and_singleflight_survives():
    clock, calls = [NOW], []
    release = asyncio.Event()
    original = transport_for(clock, calls)

    async def blocked(url, timeout):
        await release.wait()
        return await original(url, timeout)

    weather = OpenMeteoWeather(transport=blocked, clock=lambda: NOW)
    app = SimpleNamespace(config=SimpleNamespace(home_city="成都", timezone="Asia/Shanghai"),
                          store=SimpleNamespace(clock=lambda: NOW), _manual_weather=weather)
    try:
        first, second = await asyncio.wait_for(
            asyncio.gather(environment_state(app), environment_state(app)), timeout=.3)
        assert first["weather"]["status"] == second["weather"]["status"] == "loading"
        assert weather.health()["inflight"] == 1
        release.set()
        await weather.get_current("成都", "Asia/Shanghai")
        fresh = await environment_state(app)
        assert fresh["weather"]["status"] == "ok" and len(calls) == 2
    finally:
        await weather.close()
