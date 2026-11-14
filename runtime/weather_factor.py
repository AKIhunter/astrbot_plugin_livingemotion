"""按固定间隔轮询天气，换算成四维权重；请求路径只读内存快照。

天气是全天持续的环境项，与「消息 + 记忆」驱动的五维状态并行计算：

- 五维 S：由互动事件推动，有自己的闸门、半衰期与基线；
- 天气权重 W：只改四维的**回落目标**（baseline + W），不写当前值、不落库，
  也永远不进六情绪；
- 六情绪 = six_emotions(decay(S))，始终是纯函数，不含任何天气常数。

两者唯一的汇合点是衰减目标，因此天然互不覆盖：没有消息时 S 仍会随天气缓慢
漂移，消息很密时 W 影响的也只是「她平息下来会停在哪」。叠加是加法的，衰减
走原有半衰期，本节不新增任何乘性系数。
"""

from __future__ import annotations

import asyncio
import logging
import math
from dataclasses import dataclass, replace
from datetime import datetime, timedelta
from zoneinfo import ZoneInfo, ZoneInfoNotFoundError

from ..adapters.weather import WeatherReport
from ..domain.dreaming import weather_affect

logger = logging.getLogger("astrbot_plugin_livingemotion.weather")

NEUTRAL = (0.0, 0.0, 0.0, 0.0)
DEFAULT_POLL = 14400
DEFAULT_TRANSITION = 900
DEFAULT_STALE = 7200
DEFAULT_FORECAST_DAYS = 7
DEFAULT_FORECAST_REFRESH = 21600
DEFAULT_WINDOW_START = 6
DEFAULT_WINDOW_END = 1
DEFAULT_DEGRADE_AFTER = 3
DEFAULT_RECOVER_AFTER = 2
DEGRADED_INTERVAL = 86400.0
RETRY_CEILING = 300.0
RETRY_CAP = 1800.0


def _number(config, name: str, default: int) -> int:
    """读一个整数配置；缺失或脏数据一律回落到默认值，绝不在轮询里抛异常。"""
    value = getattr(config, name, default)
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        return default
    if not math.isfinite(value):
        return default
    return int(value)


def _today(now: float, zone: str) -> str:
    return datetime.fromtimestamp(now, ZoneInfo(zone)).date().isoformat()


def _target(config):
    """返回 (city, timezone)；未启用、缺城市或时区非法时返回空二元组。"""
    if getattr(config, "weather_factor_enabled", True) is False:
        return "", ""
    city = (getattr(config, "home_city", "") or "").strip()
    zone = (getattr(config, "timezone", "") or "").strip()
    if not city or not zone:
        return "", ""
    try:
        ZoneInfo(zone)
    except (ValueError, ZoneInfoNotFoundError):
        return "", ""
    return city, zone


@dataclass(frozen=True)
class WeatherWeight:
    """一次天气换算的结果；字段都可 JSON 化，便于诊断接口直接输出。"""

    at: float = 0.0
    city: str = ""
    timezone: str = ""
    code: int | None = None
    summary: str = ""
    source: str = "neutral"
    weights: tuple[float, ...] = NEUTRAL
    target: tuple[float, ...] = NEUTRAL
    failures: int = 0

    def drift(self, scale: float = 1.0) -> tuple[float, ...] | None:
        scaled = tuple(value * scale for value in self.weights)
        return scaled if any(scaled) else None

    def as_dict(self) -> dict:
        return {"at": self.at, "city": self.city, "timezone": self.timezone,
                "code": self.code, "summary": self.summary, "source": self.source,
                "weights": list(self.weights), "target": list(self.target),
                "failures": self.failures}


class WeatherFactor:
    """单实例后台轮询器；``snapshot()`` 是同步的，永不 await 网络。

    去重要点：
    - 只有一个轮询任务，``start()`` 幂等；
    - 底层 ``OpenMeteoWeather`` 自带 TTL 缓存 + single-flight，页面侧不会再发请求；
    - 失败走指数退避（最长到正常周期），不会形成重试风暴。
    """

    def __init__(self, *, config, weather, clock, sleep=asyncio.sleep):
        self._config = config
        self._weather = weather
        self._clock = clock
        self._sleep = sleep
        self._snapshot = WeatherWeight()
        self._previous: tuple[float, ...] = NEUTRAL
        self._target: tuple[float, ...] = NEUTRAL
        self._changed_at = 0.0
        self._last_ok = 0.0
        self._failures = 0
        self._task: asyncio.Task | None = None
        self._closed = False
        self._forecast: dict[str, WeatherReport] = {}
        self._forecast_at = 0.0
        # 调度状态机：高频抓取连续失败就退到每日粒度，连续若干日成功再升回来。
        self._degraded = False
        self._recover_streak = 0

    # ---------------- 只读路径（请求线程直接调用） ----------------

    def snapshot(self) -> WeatherWeight:
        cfg = self._config()
        now = self._clock()
        if self._closed:
            return replace(self._snapshot, at=now, source="disabled", weights=NEUTRAL)
        if not all(_target(cfg)):
            return WeatherWeight(at=now, source="disabled")
        if not self._last_ok:
            return WeatherWeight(at=now, source="neutral")
        stale_for = _number(cfg, "weather_stale_seconds", DEFAULT_STALE)
        if stale_for > 0 and now - self._last_ok > stale_for:
            return replace(self._snapshot, at=now, source="stale", weights=NEUTRAL)
        return replace(self._snapshot, at=now, weights=self._interpolate(now, cfg))

    def drift(self, scale: float | None = None) -> tuple[float, ...] | None:
        if scale is None:
            raw = getattr(self._config(), "weather_weight_scale", 1.0)
            if (isinstance(raw, bool) or not isinstance(raw, (int, float))
                    or not math.isfinite(raw)):
                raw = 1.0
            scale = float(raw)
        if scale <= 0:
            return None
        return self.snapshot().drift(scale)

    def report(self) -> WeatherReport | None:
        """把新鲜的成功快照还原成 WeatherReport，供既有 daily 口径复用。"""
        snap = self.snapshot()
        if snap.source not in ("live", "forecast") or snap.code is None or not snap.city:
            return None
        try:
            day = datetime.fromtimestamp(
                self._clock(), ZoneInfo(snap.timezone)).date().isoformat()
        except (ValueError, ZoneInfoNotFoundError, OSError):
            return None
        return WeatherReport(snap.city, day, snap.timezone, "ok", snap.summary,
                             fetched_at=snap.at, code=snap.code)

    # ---------------- 轮询 ----------------

    async def poll_once(self) -> WeatherWeight:
        cfg = self._config()
        city, zone = _target(cfg)
        now = self._clock()
        if not city:
            self._snapshot = WeatherWeight(at=now, source="disabled")
            return self._snapshot
        today = _today(now, zone)
        if self._degraded:
            # 降级期只刷「日粒度」预报表：一天一次，够兜底也不刷接口。
            await self._refresh_forecast(city, zone, now, cfg, force=True)
            forecast = self._forecast.get(today)
            if forecast is not None and isinstance(forecast.code, int):
                snap = self._publish(forecast, city=city, zone=zone, now=now, cfg=cfg,
                                     source="forecast")
                logger.warning("[LivingEmotion] 天气降级模式（每日一次）：%s code=%s",
                               forecast.summary, forecast.code)
                self._on_success(cfg)
                return snap
            logger.warning("[LivingEmotion] 天气降级模式下预报也失败，维持旧权重")
            self._on_failure(cfg)
            return self._fallback(now)
        # 先确保 7 天预报表新鲜（默认 6 小时刷新一次），它是实况失败时的兜底。
        await self._refresh_forecast(city, zone, now, cfg)
        report = None
        try:
            report = await self._weather.get_current(city, zone)
        except asyncio.CancelledError:
            raise
        except Exception:  # noqa: BLE001 - 单次失败不能带走轮询任务
            logger.warning("[LivingEmotion] 天气实况请求异常，尝试用当日预报兜底", exc_info=True)
        if report is not None and report.status == "ok" and isinstance(report.code, int):
            snap = self._publish(report, city=city, zone=zone, now=now, cfg=cfg, source="live")
            logger.warning(
                "[LivingEmotion] 天气权重更新（实况）：%s code=%s 目标=(%.3f,%.3f,%.3f,%.3f)",
                report.summary, report.code, *snap.target)
            self._on_success(cfg)
            return snap
        # 实况失败：优先用 7 天预报表里今天那一格，别直接掉到中性。
        forecast = self._forecast.get(today)
        if forecast is not None and isinstance(forecast.code, int):
            snap = self._publish(forecast, city=city, zone=zone, now=now, cfg=cfg,
                                 source="forecast")
            logger.warning("[LivingEmotion] 天气实况失败，改用当日预报：%s code=%s",
                           forecast.summary, forecast.code)
            self._on_success(cfg)
            return snap
        status = getattr(report, "status", "none") if report is not None else "exception"
        logger.warning("[LivingEmotion] 天气权重降级（第 %d 次，原因=%s，城市=%s）：%s",
                       self._failures + 1, status, city,
                       "沿用上次权重" if self._last_ok else "无历史值，用中性权重")
        self._on_failure(cfg)
        return self._fallback(now)

    def _on_success(self, cfg) -> None:
        """成功一次就清零失败计数；降级期累计到阈值后升回高频。"""
        self._failures = 0
        if not self._degraded:
            self._recover_streak = 0
            return
        self._recover_streak += 1
        need = max(1, _number(cfg, "weather_recover_after_successes", DEFAULT_RECOVER_AFTER))
        if self._recover_streak >= need:
            self._degraded = False
            self._recover_streak = 0
            logger.warning("[LivingEmotion] 天气抓取恢复高频（连续 %d 次日粒度成功）", need)

    def _on_failure(self, cfg) -> None:
        """连续失败到阈值就退到每日粒度，避免整点反复撞接口。"""
        self._failures += 1
        self._recover_streak = 0
        need = max(1, _number(cfg, "weather_degrade_after_failures", DEFAULT_DEGRADE_AFTER))
        if not self._degraded and self._failures >= need:
            self._degraded = True
            logger.warning(
                "[LivingEmotion] 天气抓取降级为每日一次（连续 %d 次失败，改用日粒度预报保底）",
                self._failures)

    def _fallback(self, now):
        self._snapshot = replace(
            self._snapshot, at=now,
            source="cache" if self._last_ok else "neutral",
            failures=self._failures)
        return self._snapshot

    def _publish(self, report, *, city, zone, now, cfg, source):
        """把一份天气换算成四维目标，并记下「变化瞬间」供读取侧平滑。"""
        day = datetime.fromtimestamp(now, ZoneInfo(zone)).date().isoformat()
        target = weather_affect(report, city=city, day=day, timezone=zone)
        self._previous = self._interpolate(now, cfg) if self._changed_at else target
        self._target, self._changed_at = target, now
        self._last_ok = now
        self._snapshot = WeatherWeight(
            at=now, city=city, timezone=zone, code=report.code,
            summary=report.summary, source=source, weights=target, target=target,
            failures=self._failures)
        return self._snapshot

    async def _refresh_forecast(self, city, zone, now, cfg, *, force=False):
        """按需拉一次 7 天预报；命中未过期的本地表就完全不发请求。"""
        refresh = _number(cfg, "weather_forecast_refresh_seconds", DEFAULT_FORECAST_REFRESH)
        if not force and self._forecast and now - self._forecast_at < max(600, refresh):
            return
        days = max(1, min(16, _number(cfg, "weather_forecast_days", DEFAULT_FORECAST_DAYS)))
        try:
            reports = await self._weather.get_forecast(city, zone, days)
        except asyncio.CancelledError:
            raise
        except Exception:  # noqa: BLE001 - 预报失败不影响实况主路径
            logger.warning("[LivingEmotion] 天气预报刷新异常，沿用旧表", exc_info=True)
            return
        if not reports:
            logger.warning("[LivingEmotion] 天气预报为空（5 分钟内重试），沿用旧表")
            return
        self._forecast, self._forecast_at = reports, now
        today = datetime.fromtimestamp(now, ZoneInfo(zone)).date().isoformat()
        head = reports.get(today) or next(iter(reports.values()))
        logger.warning("[LivingEmotion] 天气预报刷新：%d 天，今日 %s code=%s",
                       len(reports), head.summary, head.code)

    async def start(self) -> None:
        if self._task is None and not self._closed:
            self._task = asyncio.create_task(self._run(), name="le-weather-factor")

    async def close(self) -> None:
        self._closed = True
        task, self._task = self._task, None
        if task is not None:
            task.cancel()
            await asyncio.gather(task, return_exceptions=True)

    async def _run(self) -> None:
        while not self._closed:
            try:
                await self.poll_once()
            except asyncio.CancelledError:
                raise
            except Exception:  # noqa: BLE001 - 轮询任务必须活到最后
                logger.warning("[LivingEmotion] 天气权重轮询外层异常", exc_info=True)
            try:
                await self._sleep(self._delay())
            except asyncio.CancelledError:
                raise

    def _delay(self) -> float:
        """距下一次抓取的秒数（测试与 _run 共用同一套锚点计算）。"""
        cfg = self._config()
        city, zone = _target(cfg)
        now = self._clock()
        if not city:
            return float(max(300, _number(cfg, "weather_poll_seconds", DEFAULT_POLL)))
        return max(1.0, self._next_wake(now, cfg, zone) - now)

    def _interval(self, cfg) -> float:
        """当前抓取周期；降级期为一天一次。"""
        if self._degraded:
            return DEGRADED_INTERVAL
        return float(max(300, _number(cfg, "weather_poll_seconds", DEFAULT_POLL)))

    def _window(self, cfg):
        start = _number(cfg, "weather_window_start_hour", DEFAULT_WINDOW_START) % 24
        end = _number(cfg, "weather_window_end_hour", DEFAULT_WINDOW_END) % 24
        return start, end

    def _next_slot(self, now, cfg, zone) -> float:
        """窗口内按周期对齐的绝对时间点；窗口外等到下一个窗口起点。

        锚点从窗口起点开始等距展开：4 小时 -> 06/10/14/18/22，1 小时 -> 06…25(次日01)。
        """
        start, end = self._window(cfg)
        step = max(1.0, self._interval(cfg) / 3600.0)
        span = (end - start) % 24 or 24.0
        midnight = datetime.fromtimestamp(now, ZoneInfo(zone)).replace(
            hour=0, minute=0, second=0, microsecond=0)
        best = None
        # 前一天也要算：跨夜窗口的尾巴（如次日 01:00）属于「昨天的 25 点」。
        for shift in (-1, 0, 1):
            day = midnight + timedelta(days=shift)
            offset = 0.0
            while offset <= span + 1e-9:
                at = (day + timedelta(hours=start + offset)).timestamp()
                if at > now and (best is None or at < best):
                    best = at
                offset += step
        return best if best is not None else now + 3600.0

    def _next_wake(self, now, cfg, zone) -> float:
        try:
            slot = self._next_slot(now, cfg, zone)
        except (ValueError, ZoneInfoNotFoundError, OSError):
            return now + 3600.0
        if self._failures:
            # 失败后按 300s×次数重试（封顶 30 分钟），但绝不越过下一个正常锚点。
            return min(slot, now + min(RETRY_CAP, RETRY_CEILING * self._failures))
        return slot

    def _interpolate(self, now: float, cfg) -> tuple[float, ...]:
        transition = _number(cfg, "weather_transition_seconds", DEFAULT_TRANSITION)
        if transition <= 0 or not self._changed_at:
            return self._target
        elapsed = max(0.0, now - self._changed_at)
        alpha = 1.0 - math.exp(-elapsed / transition)
        return tuple(previous + (target - previous) * alpha
                     for previous, target in zip(self._previous, self._target))
