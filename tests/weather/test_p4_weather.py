import asyncio
import json
from datetime import UTC, datetime
from urllib.parse import parse_qs, urlparse

import pytest
from astrbot_plugin_livingemotion.adapters.weather import OpenMeteoWeather, WeatherReport
from astrbot_plugin_livingemotion.config import Config
from astrbot_plugin_livingemotion.runtime.background import BackgroundRuntime
from astrbot_plugin_livingemotion.services.experience import ExperiencePolicy
from astrbot_plugin_livingemotion.storage import SQLiteStore
from astrbot_plugin_livingemotion.tests.experience.test_experience import Harness

NOW = datetime(2026, 11, 6, 12, tzinfo=UTC).timestamp()


@pytest.fixture
async def h(tmp_path):
    config = Config(diary_enabled=True, dream_enabled=True, memory_export=True)
    store = SQLiteStore(tmp_path / "diary.sqlite3", config=config, clock=lambda: NOW)
    await store.open()
    runtime = BackgroundRuntime(store, config)
    harness = Harness(store, runtime)
    store.clock = lambda: harness.now
    harness.original_save = store.save_experience
    store.save_experience = harness.save
    await runtime.start()
    try:
        yield harness
    finally:
        await runtime.stop()
        await store.close()


class Transport:
    def __init__(self):
        self.calls = []
        self.bad_date, self.bad_units, self.fail = False, False, False
        self.started, self.release = asyncio.Event(), asyncio.Event()
        self.release.set()

    async def __call__(self, url, timeout):
        self.calls.append((url, timeout))
        self.started.set()
        await self.release.wait()
        if self.fail:
            raise TimeoutError("synthetic weather timeout")
        params = parse_qs(urlparse(url).query)
        if "geocoding-api" in url:
            return {"results": [{"latitude": 31.2, "longitude": 121.5}]}
        day = "2026-11-06" if self.bad_date else params["start_date"][0]
        return {
            "timezone": params["timezone"][0],
            "daily": {"time": [day], "weather_code": [3],
                      "temperature_2m_min": [10.0], "temperature_2m_max": [18.0]},
            "daily_units": {"temperature_2m_min": "F" if self.bad_units else "°C",
                            "temperature_2m_max": "°C"},
        }


async def test_p4_weather_real_date_city_cache_and_singleflight():
    clock = [NOW]
    transport = Transport()
    weather = OpenMeteoWeather(transport=transport, clock=lambda: clock[0])
    transport.release.clear()
    first = asyncio.create_task(weather.get("上海", "2026-11-05", "Asia/Shanghai"))
    await transport.started.wait()
    second = asyncio.create_task(weather.get("上海", "2026-11-05", "Asia/Shanghai"))
    transport.release.set()
    a, b = await asyncio.gather(first, second)
    assert a == b and a.status == "ok" and a.day == "2026-11-05"
    assert a.summary == "阴，10–18°C"
    assert len(transport.calls) == 2
    assert await weather.get("上海", "2026-11-05", "Asia/Shanghai") == a
    clock[0] += 3601
    await weather.get("上海", "2026-11-05", "Asia/Shanghai")
    # geocoding 已按城市缓存 7 天：第二次过期重取只多发一次天气请求。
    assert len(transport.calls) == 3
    assert all(timeout == 5 for _, timeout in transport.calls)
    await weather.close()


@pytest.mark.parametrize("mode", ["wrong_date", "wrong_units", "timeout", "failed"])
async def test_p4_weather_fail_closed_negative_cache_and_timeout(mode):
    transport = Transport()
    weather = OpenMeteoWeather(transport=transport, clock=lambda: NOW, timeout=0.02)
    if mode == "wrong_date":
        transport.bad_date = True
    elif mode == "wrong_units":
        transport.bad_units = True
    elif mode == "timeout":
        transport.release.clear()
    else:
        transport.fail = True
    report = await weather.get("上海", "2026-11-05", "Asia/Shanghai")
    assert report.status == "unavailable" and report.summary == "未获取"
    count = len(transport.calls)
    assert await weather.get("上海", "2026-11-05", "Asia/Shanghai") == report
    assert len(transport.calls) == count
    assert weather.health()["inflight"] == 0
    await weather.close()


async def test_p4_weather_archive_future_and_shutdown():
    transport = Transport()
    weather = OpenMeteoWeather(transport=transport, clock=lambda: NOW)
    await weather.get("上海", "2026-10-30", "Asia/Shanghai")
    assert "archive-api.open-meteo.com" in transport.calls[-1][0]
    count = len(transport.calls)
    assert (await weather.get("上海", "2026-11-07", "Asia/Shanghai")).status == "unavailable"
    assert len(transport.calls) == count
    transport.started.clear()
    transport.release.clear()
    task = asyncio.create_task(weather.get("北京", "2026-11-06", "Asia/Shanghai"))
    await transport.started.wait()
    await weather.close()
    with pytest.raises(asyncio.CancelledError):
        await task
    assert weather.health()["cache_entries"] == 0


@pytest.mark.parametrize("returned_zone,offset,expected", [
    ("GMT", 0, "ok"), ("Etc/UTC", 0, "ok"),
    ("GMT", 3600, "unavailable"), ("Asia/Shanghai", 28800, "unavailable"),
])
async def test_p4_weather_utc_alias_does_not_disable_default_diary(
    returned_zone, offset, expected,
):
    transport = Transport()

    async def normalized(url, timeout):
        value = await transport(url, timeout)
        if "daily" in value:
            value["timezone"], value["utc_offset_seconds"] = returned_zone, offset
        return value

    weather = OpenMeteoWeather(transport=normalized, clock=lambda: NOW)
    try:
        report = await weather.get("上海", "2026-11-05", "UTC")
        assert report.status == expected and report.timezone == "UTC"
    finally:
        await weather.close()


@pytest.mark.parametrize("mode", ["ok", "unavailable", "wrong_date"])
async def test_p4_diary_program_header_and_bot_narrator(h, mode):
    class Weather:
        def __init__(self):
            self.calls = []

        async def get(self, city, day, zone):
            self.calls.append((city, day, zone))
            return WeatherReport(city, "2026-11-06" if mode == "wrong_date" else day, zone,
                                 "ok" if mode != "unavailable" else "unavailable", "真实测试天气")
    weather = Weather()
    h.service = h.make_service(
        weather=weather, policy=ExperiencePolicy(home_city="上海", backfill_yesterday=True),
    )
    await h.event(occurred=h.now - 86400)
    ticket = await h.diary(day="2026-11-04")
    outcome = h.service.outcome(ticket["job_id"])
    assert outcome["status"] == "created", outcome
    entry = h.records[ticket["experience_id"]][0]
    assert entry.body.startswith("日期：2026-11-04（UTC）\n城市：上海\n天气：")
    expected = "真实测试天气" if mode == "ok" else "未获取"
    assert f"天气：{expected}\n\n" in entry.body
    # Current mood and the backfilled diary header use their own calendar dates.
    assert weather.calls == [
        ("上海", "2026-11-05", "UTC"),
        ("上海", "2026-11-04", "UTC"),
    ]
    data = json.loads(h.model.calls[0].data)
    assert data["narrator"] == "bot_first_person"
    assert data["program_header"]["date"] == "2026-11-04"
    assert "first-person subject is the BOT" in h.model.calls[0].system
    assert h.model.calls[0].purpose == "diary"


async def test_p4_weather_does_not_create_experience_without_material(h):
    async def forbidden(*args):
        raise AssertionError("empty_diary_must_not_query_weather")
    h.service = h.make_service(
        weather=type("Weather", (), {"get": forbidden})(),
        policy=ExperiencePolicy(home_city="上海"),
    )
    assert (await h.diary())["reason_code"] == "no_qualified_material"
    assert h.model.calls == []


async def test_p4_diary_weather_await_cannot_bypass_authority_recheck(h):
    class Weather:
        async def get(self, city, day, zone):
            h.invalid.add((h.context.scope_key, h.context.persona_revision,
                           h.context.identity_revision))
            return WeatherReport(city, day, zone, "ok", "真实测试天气")
    h.service = h.make_service(weather=Weather(), policy=ExperiencePolicy(home_city="上海"))
    await h.event()
    ticket = await h.diary()
    assert h.service.outcome(ticket["job_id"])["status"] == "failed"
    assert h.model.calls == [] and not h.records
