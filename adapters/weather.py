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
    code: int | None = None
    hazard: str = ""
    temperature: float | None = None
    observed_at: float = 0.0


class WeatherProvider:
    async def get(self, city: str, day: str, timezone: str) -> WeatherReport:
        raise NotImplementedError

    async def get_current(self, city: str, timezone: str) -> WeatherReport:
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
                 ttl=3600, failure_ttl=30, max_cache=128, forecast_ttl=21600):
        finite(timeout, "weather_timeout", 0.001, 5)
        finite(ttl, "weather_ttl", 1, 3600)
        finite(failure_ttl, "weather_failure_ttl", 0.001, 60)
        finite(forecast_ttl, "weather_forecast_ttl", 60, 86400)
        if type(max_cache) is not int or not 1 <= max_cache <= 1024:
            raise ValueError("weather_cache_limit")
        self.transport, self.clock = transport or _json_transport, clock
        self.timeout, self.ttl, self.failure_ttl = timeout, ttl, failure_ttl
        self.forecast_ttl = forecast_ttl
        self.max_cache = max_cache
        self._cache, self._inflight = OrderedDict(), {}
        self._geo = {}
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
        return await self._lookup(key, fallback)

    async def get_current(self, city, timezone):
        ZoneInfo(timezone)
        if not isinstance(city, str) or len(city) > 128 or any(ord(c) < 32 for c in city):
            raise ValueError("weather_city_invalid")
        # 当前天气使用独立缓存键，不能拿日记的全天最高/最低温充当实况。
        key = (city.strip(), "current", timezone)
        fallback = WeatherReport(key[0], self._day(timezone), timezone)
        if self._closed or not key[0]:
            return fallback
        return await self._lookup(key, fallback)

    def _day(self, timezone):
        return datetime.fromtimestamp(self.clock(), ZoneInfo(timezone)).date().isoformat()

    async def _lookup(self, key, fallback):
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
        report = WeatherReport(city, self._day(timezone) if day == "current" else day, timezone)
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
                min(self.ttl, 600) if report.status == "ok" and day == "current"
                else self.ttl if report.status == "ok" else self.failure_ttl
            ), report)
            while len(self._cache) > self.max_cache:
                self._cache.popitem(last=False)
        return report

    async def _query(self, key):
        city, day, timezone = key
        async with self._semaphore:
            latitude, longitude = await self._locate(city)
            today = datetime.fromtimestamp(self.clock(), ZoneInfo(timezone)).date()
            current = day == "current"
            base = ("https://archive-api.open-meteo.com/v1/archive"
                    if not current and date.fromisoformat(day) < today - timedelta(days=5)
                    else "https://api.open-meteo.com/v1/forecast")
            params = {
                "latitude": latitude, "longitude": longitude, "timezone": timezone,
            }
            params.update({"current": "weather_code,temperature_2m", "timeformat": "unixtime"}
                          if current else {"start_date": day, "end_date": day,
                                           "daily": "weather_code,temperature_2m_max,temperature_2m_min"})
            payload = await self.transport(base + "?" + urlencode(params), self.timeout)
            returned_zone = payload.get("timezone")
            # Open-Meteo normalizes UTC to GMT; only known zero-offset aliases may differ.
            same_utc = (timezone in _UTC_ALIASES and returned_zone in _UTC_ALIASES
                        and payload.get("utc_offset_seconds", 0) == 0)
            if returned_zone != timezone and not same_utc:
                raise ValueError("weather_timezone_mismatch")
            if current:
                value, units = payload["current"], payload["current_units"]
                code, temperature, observed = value["weather_code"], value["temperature_2m"], value["time"]
                if type(code) is not int or code not in _CODES:
                    raise ValueError("weather_code_invalid")
                finite(temperature, "temperature_current", -100, 70)
                finite(observed, "weather_observed_at", self.clock() - 3600, self.clock() + 300)
                if units.get("temperature_2m") != "°C" or units.get("time") != "unixtime":
                    raise ValueError("weather_units_invalid")
                return WeatherReport(city, today.isoformat(), timezone, "ok",
                                     f"{_CODES[code]} · {temperature:g}°C",
                                     fetched_at=self.clock(), code=code,
                                     temperature=temperature, observed_at=observed)
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
                code=code,
            )

    async def _locate(self, city):
        """城市坐标缓存 7 天：geocoding 是第二个请求，不该每天重复打。"""
        cached = self._geo.get(city)
        if cached and self.clock() < cached[0]:
            return cached[1]
        geo = await self.transport(
            "https://geocoding-api.open-meteo.com/v1/search?" + urlencode({
                "name": city, "count": 1, "language": "zh", "format": "json",
            }), self.timeout)
        location = geo["results"][0]
        latitude, longitude = location["latitude"], location["longitude"]
        finite(latitude, "latitude", -90, 90)
        finite(longitude, "longitude", -180, 180)
        self._geo[city] = (self.clock() + 86400 * 7, (latitude, longitude))
        return latitude, longitude

    async def get_forecast(self, city, timezone, days=7):
        """一次取 N 天日天气码，全部写进按天缓存；后续 ``get(day)`` 直接命中。

        失败返回空字典而不是抛异常：调用方据此决定要不要继续用旧数据。
        """
        if not isinstance(city, str) or len(city) > 128 or any(ord(c) < 32 for c in city):
            raise ValueError("weather_city_invalid")
        ZoneInfo(timezone)
        if type(days) is not int or not 1 <= days <= 16:
            raise ValueError("weather_forecast_days")
        city = city.strip()
        if self._closed or not city:
            return {}
        key = (city, f"forecast:{days}", timezone)
        cached = self._cache.get(key)
        if cached and self.clock() < cached[0]:
            self._counts["hit"] += 1
            self._cache.move_to_end(key)
            return cached[1]
        task = self._inflight.get(key)
        if task is None:
            if len(self._inflight) >= 16:
                return {}
            self._counts["miss"] += 1
            task = asyncio.create_task(self._fetch_forecast(key))
            self._inflight[key] = task
            task.add_done_callback(lambda done: done.exception() if not done.cancelled() else None)
        return await asyncio.shield(task)

    async def _fetch_forecast(self, key):
        city, tag, timezone = key
        reports = {}
        try:
            # 一次批量查询含两步请求（geocoding + 预报），整体时限按两倍单请求给，
            # 否则冷启动那次必超时，一整天都没有预报表可兜底。
            reports = await asyncio.wait_for(
                self._query_range(city, timezone, int(tag.split(":", 1)[1])),
                self.timeout * 2)
        except asyncio.CancelledError:
            raise
        except Exception as exc:  # noqa: BLE001 - 失败即空结果，由调用方降级
            self._counts["unavailable"] += 1
            self._counts["forecast_error"] = type(exc).__name__
        finally:
            self._inflight.pop(key, None)
        if not self._closed:
            self._cache[key] = (self.clock() + (
                self.forecast_ttl if reports else self.failure_ttl), reports)
            for day, report in reports.items():
                self._cache[(city, day, timezone)] = (self.clock() + self.forecast_ttl, report)
            while len(self._cache) > self.max_cache:
                self._cache.popitem(last=False)
        return reports

    async def _query_range(self, city, timezone, days):
        async with self._semaphore:
            latitude, longitude = await self._locate(city)
            payload = await self.transport(
                "https://api.open-meteo.com/v1/forecast?" + urlencode({
                    "latitude": latitude, "longitude": longitude, "timezone": timezone,
                    "daily": "weather_code,temperature_2m_max,temperature_2m_min",
                    "forecast_days": days,
                }), self.timeout)
            returned_zone = payload.get("timezone")
            same_utc = (timezone in _UTC_ALIASES and returned_zone in _UTC_ALIASES
                        and payload.get("utc_offset_seconds", 0) == 0)
            if returned_zone != timezone and not same_utc:
                raise ValueError("weather_timezone_mismatch")
            daily = payload["daily"]
            times = daily.get("time")
            if not isinstance(times, list) or not 1 <= len(times) <= 16:
                raise ValueError("weather_range_invalid")
            units = payload.get("daily_units", {})
            if any(units.get(name) != "°C" for name in (
                    "temperature_2m_max", "temperature_2m_min")):
                raise ValueError("weather_units_invalid")
            reports = {}
            for index, day in enumerate(times):
                code = daily["weather_code"][index]
                high = daily["temperature_2m_max"][index]
                low = daily["temperature_2m_min"][index]
                if type(code) is not int or code not in _CODES or not isinstance(day, str):
                    continue
                finite(high, "temperature_high", -100, 70)
                finite(low, "temperature_low", -100, high)
                reports[day] = WeatherReport(
                    city, day, timezone, "ok", f"{_CODES[code]}，{low:g}–{high:g}°C",
                    fetched_at=self.clock(), code=code)
            if not reports:
                raise ValueError("weather_range_empty")
            return reports

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
