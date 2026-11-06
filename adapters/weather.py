"""Date-exact Open-Meteo weather with bounded cache, single-flight, and timeout."""

from __future__ import annotations

import asyncio
import json
import time
from collections import OrderedDict
from dataclasses import dataclass
from datetime import date, datetime, timedelta
from urllib.parse import urlencode
from urllib.request import urlopen
from zoneinfo import ZoneInfo

from ..contracts import finite


@dataclass(frozen=True)
class WeatherReport:
    city: str
    day: str
    timezone: str
    status: str = "unavailable"
    summary: str = "未获取"
    provider: str = "open-meteo"
    fetched_at: float = 0.0


class WeatherProvider:
    async def get(self, city: str, day: str, timezone: str) -> WeatherReport:
        raise NotImplementedError


_CODES = {
    0: "晴", 1: "大部晴朗", 2: "局部多云", 3: "阴",
    45: "雾", 48: "雾凇", 51: "小毛毛雨", 53: "毛毛雨", 55: "强毛毛雨",
    56: "轻度冻毛毛雨", 57: "强冻毛毛雨", 61: "小雨", 63: "雨", 65: "大雨",
    66: "轻度冻雨", 67: "强冻雨", 71: "小雪", 73: "雪", 75: "大雪",
    77: "雪粒", 80: "小阵雨", 81: "阵雨", 82: "强阵雨",
    85: "小阵雪", 86: "强阵雪", 95: "雷雨", 96: "雷雨伴冰雹", 99: "强雷雨伴冰雹",
}
_UTC_ALIASES = frozenset({"UTC", "GMT", "Etc/UTC", "Etc/GMT", "UCT", "Etc/UCT", "Zulu"})


async def _json_transport(url, timeout):
    def read():
        with urlopen(url, timeout=timeout) as response:
            raw = response.read(262145)
        if len(raw) > 262144:
            raise ValueError("weather_payload_too_large")
        return json.loads(raw)
    return await asyncio.to_thread(read)


class OpenMeteoWeather(WeatherProvider):
    def __init__(self, *, transport=None, clock=time.time, timeout=5.0,
                 ttl=3600, failure_ttl=30, max_cache=128):
        finite(timeout, "weather_timeout", 0.001, 5)
        finite(ttl, "weather_ttl", 1, 3600)
        finite(failure_ttl, "weather_failure_ttl", 0.001, 60)
        if type(max_cache) is not int or not 1 <= max_cache <= 1024:
            raise ValueError("weather_cache_limit")
        self.transport, self.clock = transport or _json_transport, clock
        self.timeout, self.ttl, self.failure_ttl = timeout, ttl, failure_ttl
        self.max_cache = max_cache
        self._cache, self._inflight = OrderedDict(), {}
        self._semaphore = asyncio.Semaphore(4)
        self._closed = False
        self._counts = {"hit": 0, "miss": 0, "unavailable": 0}

    async def get(self, city, day, timezone):
        selected = date.fromisoformat(day)
        zone = ZoneInfo(timezone)
        if not isinstance(city, str) or len(city) > 128 or any(ord(c) < 32 for c in city):
            raise ValueError("weather_city_invalid")
        key = (city.strip(), selected.isoformat(), timezone)
        fallback = WeatherReport(key[0], key[1], timezone)
        if self._closed or not key[0]:
            return fallback
        today = datetime.fromtimestamp(self.clock(), zone).date()
        if selected > today or selected < today - timedelta(days=365):
            return fallback
        cached = self._cache.get(key)
        if cached and self.clock() < cached[0]:
            self._counts["hit"] += 1
            self._cache.move_to_end(key)
            return cached[1]
        task = self._inflight.get(key)
        if task is None:
            if len(self._inflight) >= 16:
                return fallback
            self._counts["miss"] += 1
            task = asyncio.create_task(self._fetch(key))
            self._inflight[key] = task
            task.add_done_callback(lambda done: done.exception() if not done.cancelled() else None)
        return await asyncio.shield(task)

    async def _fetch(self, key):
        city, day, timezone = key
        report = WeatherReport(city, day, timezone)
        try:
            report = await asyncio.wait_for(self._query(key), self.timeout)
        except asyncio.CancelledError:
            raise
        except Exception:  # noqa: BLE001 - never retain dependency payloads in health.
            self._counts["unavailable"] += 1
        finally:
            self._inflight.pop(key, None)
        if not self._closed:
            self._cache[key] = (self.clock() + (
                self.ttl if report.status == "ok" else self.failure_ttl
            ), report)
            while len(self._cache) > self.max_cache:
                self._cache.popitem(last=False)
        return report

    async def _query(self, key):
        city, day, timezone = key
        async with self._semaphore:
            geo = await self.transport(
                "https://geocoding-api.open-meteo.com/v1/search?" + urlencode({
                    "name": city, "count": 1, "language": "zh", "format": "json",
                }), self.timeout,
            )
            location = geo["results"][0]
            latitude, longitude = location["latitude"], location["longitude"]
            finite(latitude, "latitude", -90, 90)
            finite(longitude, "longitude", -180, 180)
            today = datetime.fromtimestamp(self.clock(), ZoneInfo(timezone)).date()
            base = ("https://archive-api.open-meteo.com/v1/archive"
                    if date.fromisoformat(day) < today - timedelta(days=5)
                    else "https://api.open-meteo.com/v1/forecast")
            payload = await self.transport(base + "?" + urlencode({
                "latitude": latitude, "longitude": longitude, "timezone": timezone,
                "start_date": day, "end_date": day,
                "daily": "weather_code,temperature_2m_max,temperature_2m_min",
            }), self.timeout)
            returned_zone = payload.get("timezone")
            # Open-Meteo normalizes UTC to GMT; only known zero-offset aliases may differ.
            same_utc = (timezone in _UTC_ALIASES and returned_zone in _UTC_ALIASES
                        and payload.get("utc_offset_seconds", 0) == 0)
            if returned_zone != timezone and not same_utc:
                raise ValueError("weather_timezone_mismatch")
            daily = payload["daily"]
            # A current weather object, approximate timestamp, or wrong day is not a diary.
            if daily["time"] != [day]:
                raise ValueError("weather_date_mismatch")
            code, high, low = (daily[name][0] for name in (
                "weather_code", "temperature_2m_max", "temperature_2m_min",
            ))
            if type(code) is not int or code not in _CODES:
                raise ValueError("weather_code_invalid")
            finite(high, "temperature_high", -100, 70)
            finite(low, "temperature_low", -100, high)
            units = payload.get("daily_units", {})
            if any(units.get(name) != "°C" for name in (
                    "temperature_2m_max", "temperature_2m_min")):
                raise ValueError("weather_units_invalid")
            return WeatherReport(
                city, day, timezone, "ok", f"{_CODES[code]}，{low:g}–{high:g}°C",
                fetched_at=self.clock(),
            )

    def health(self):
        return {"closed": self._closed, "cache_entries": len(self._cache),
                "inflight": len(self._inflight), **self._counts}

    async def close(self):
        self._closed = True
        tasks = tuple(self._inflight.values())
        for task in tasks:
            task.cancel()
        await asyncio.gather(*tasks, return_exceptions=True)
        self._cache.clear()
        self._inflight.clear()
