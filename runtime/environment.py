"""Read-only local clock and current weather for the life console."""
import asyncio
from zoneinfo import ZoneInfo, ZoneInfoNotFoundError

from ..adapters.weather import OpenMeteoWeather, WeatherReport


async def environment_state(app):
    config = app.config
    city = getattr(config, "home_city", "").strip()
    zone = getattr(config, "timezone", "").strip()
    disabled = {"enabled": False}
    if not city or not zone:
        return disabled
    try:
        ZoneInfo(zone)
    except (ValueError, ZoneInfoNotFoundError):
        return disabled
    weather = getattr(app, "_manual_weather", None)
    if weather is None or getattr(weather, "_closed", False):
        # 与日记天气共用限时、有界、single-flight 客户端；停机由现有业务收尾关闭。
        weather = app._manual_weather = OpenMeteoWeather(clock=app.store.clock)
    try:
        # 客户端内部 shield + single-flight：页面最多等50ms，后台查询仍有5秒上限。
        # 取消外层等待不会取消共享查询，也不再另起无限积压的轮询任务。
        report = await asyncio.wait_for(weather.get_current(city, zone), timeout=.05)
    except asyncio.TimeoutError:
        report = WeatherReport(city, "", zone, status="loading", summary="天气更新中")
    # 网络请求期间地区配置可能改变；旧地区的响应不能贴到新地区下。
    if (city, zone) != (app.config.home_city.strip(), app.config.timezone.strip()):
        return disabled
    return {
        "enabled": True, "city": city, "timezone": zone, "server_time": app.store.clock(),
        "weather": {"status": report.status, "summary": report.summary,
                    "temperature": report.temperature, "code": report.code,
                    "observed_at": report.observed_at, "fetched_at": report.fetched_at},
    }
