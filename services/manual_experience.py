"""A bounded on-demand private generator, independent of automatic eligibility."""
import asyncio
from dataclasses import dataclass
from datetime import datetime
from zoneinfo import ZoneInfo

from ..adapters.weather import WeatherReport
from ..contracts import ContentKind, Experience, canonical_json
from ..runtime.background import ModelResultUnknown
from .experience import SYSTEM_PROMPT, parse_entry, perspective, _plain
from ..storage.experiences import owner_key
from ..domain.dreaming import DEFAULT_THEMES, dream_profile, apply_bonus, weather_bonus


@dataclass(frozen=True)
class ManualSnapshot:
    request_id: str
    context: object
    kind: str
    day: str
    timezone: str
    accepted_at: float
    persona: str
    fingerprint: str
    binding: object
    generations: tuple
    materials: tuple
    body_chars: int
    home_city: str
    retention_days: int = 30
    mood: object = None
    themes: tuple = DEFAULT_THEMES


class ManualExperienceService:
    def __init__(self, store, *, capture, current, commit, weather):
        self.store = store
        self.capture, self.current, self.commit, self.weather = capture, current, commit, weather
        self.queue = asyncio.Queue(maxsize=16)
        self.worker = None
        self.closed = False
        self.lock = asyncio.Lock()

    async def submit(self, request_id, persona_id, kind):
        async with self.lock:
            if self.closed:
                raise ValueError("executor_stopped")
            snapshot = await self.capture(request_id, persona_id, kind)
            result, created = await self.store.accept_experience_job(
                request_id, snapshot.context, kind, snapshot.day, snapshot.timezone,
                snapshot.generations, snapshot.fingerprint)
            if created:
                try:
                    self.queue.put_nowait(snapshot)
                except asyncio.QueueFull:
                    await self.store.mark_experience_job(request_id, "cancelled", "queue_full")
                    return await self.store.experience_job(request_id, owner_key(
                        snapshot.context.instance_id, persona_id))
                if self.worker is None or self.worker.done():
                    self.worker = asyncio.create_task(self._work(), name="livingemotion-manual-experience")
            return result

    async def _work(self):
        while not self.closed and not self.queue.empty():
            snapshot = self.queue.get_nowait()
            dispatched = False
            try:
                if not await self.current(snapshot):
                    raise ValueError("persona_or_model_changed")
                weather = WeatherReport(snapshot.home_city, snapshot.day, snapshot.timezone)
                if snapshot.home_city:
                    try:
                        candidate = await asyncio.wait_for(self.weather.get(
                            snapshot.home_city, snapshot.day, snapshot.timezone), 5)
                        if (isinstance(candidate, WeatherReport) and candidate.day == snapshot.day
                                and candidate.city == snapshot.home_city and candidate.timezone == snapshot.timezone
                                and candidate.status == "ok" and isinstance(candidate.summary, str)
                                and 0 < len(candidate.summary) <= 128 and _plain(candidate.summary)
                                and not any(ord(c) < 32 for c in candidate.summary)):
                            weather = candidate
                    except Exception:
                        pass
                emotions = apply_bonus(snapshot.mood or {}, weather_bonus(
                    weather, city=snapshot.home_city, day=snapshot.day, timezone=snapshot.timezone))
                data = canonical_json({
                    "purpose": snapshot.kind, "narrator": "bot_first_person",
                    "persona": snapshot.persona,
                    "program_header": {"date": snapshot.day, "timezone": snapshot.timezone,
                                       "city": snapshot.home_city or "未配置"},
                    "body_character_limit": max(1, snapshot.body_chars - 100),
                    "mood": {"emotions": emotions, "basis": "daily_recorded_mean"},
                    "dream": dream_profile(emotions, snapshot.themes) if snapshot.kind == "dream" else None,
                    "grounding": ("Use verified materials only." if snapshot.materials else
                                  "无已验证当日经历。日记仅作人格自省，不编造聊天、行程或真实事件；"
                                  "梦境是想象，必须明确说明。"),
                    "materials": [{"source_id": m.evidence.source_id,
                                   "kind": m.evidence.kind.value,
                                   "perspective": perspective(m.evidence), "text": m.text[:1200]}
                                  for m in snapshot.materials],
                })
                if not 0 < snapshot.binding.count(SYSTEM_PROMPT, data) <= 32768:
                    raise ValueError("input_token_limit")
                if not await self.current(snapshot):
                    raise ValueError("persona_or_model_changed")
                if not await self.store.mark_experience_job(snapshot.request_id, "running", "generating"):
                    continue
                await self.store.record_manual_dispatch(
                    snapshot.request_id, snapshot.context, snapshot.day, snapshot.kind)
                dispatched = True
                raw = await asyncio.wait_for(snapshot.binding.generate(SYSTEM_PROMPT, data, 8192, 90), 90)
                parsed = parse_entry(raw, allowed_sources={m.evidence.source_id for m in snapshot.materials},
                                     max_chars=max(1, snapshot.body_chars - 100))
                if not await self.current(snapshot):
                    raise ValueError("persona_or_model_changed")
                header = (f"日期：{snapshot.day}\n住所：{snapshot.home_city or '未配置'}\n"
                          f"天气：{weather.summary if weather.status == 'ok' else '未获取'}\n\n"
                          if snapshot.kind == "diary" else f"日期：{snapshot.day} · 想象\n\n")
                entry = Experience(
                    "", snapshot.context, ContentKind(snapshot.kind), snapshot.day,
                    snapshot.accepted_at, header + parsed.body,
                    evidence=tuple(m.evidence for m in snapshot.materials
                                   if m.evidence.source_id in parsed.source_ids),
                    expires_at=snapshot.accepted_at + snapshot.retention_days * 86400, clarity=1.0)
                await self.commit(snapshot, entry)
                await self.store.finish_quota("manual:" + snapshot.request_id,
                                             status="succeeded", reason_code="private_archive_updated")
            except asyncio.CancelledError:
                await self.store.mark_experience_job(
                    snapshot.request_id, "unknown" if dispatched else "cancelled",
                    "reload_after_dispatch" if dispatched else "reload_before_dispatch")
                if dispatched:
                    await self.store.finish_quota("manual:" + snapshot.request_id,
                                                 status="unknown", reason_code="reload_after_dispatch")
                raise
            except Exception as exc:
                unknown = isinstance(exc, (TimeoutError, ModelResultUnknown))
                status = "unknown" if unknown else "failed"
                known = {"input_token_limit", "persona_or_model_changed", "entry_changed",
                         "job_changed", "model_body_invalid", "model_sources_invalid",
                         "model_body_unsafe", "model_error_envelope", "stale_generation"}
                reason = str(exc) if str(exc) in known else ("model_result_unknown" if unknown else "generation_failed")
                await self.store.mark_experience_job(snapshot.request_id, status, reason)
                if dispatched:
                    await self.store.finish_quota("manual:" + snapshot.request_id,
                                                 status=status, reason_code=reason)
            finally:
                self.queue.task_done()

    async def close(self):
        self.closed = True
        if self.worker is not None:
            self.worker.cancel()
            await asyncio.gather(self.worker, return_exceptions=True)
        while not self.queue.empty():
            snapshot = self.queue.get_nowait()
            await self.store.mark_experience_job(snapshot.request_id, "cancelled", "reload_before_dispatch")
            self.queue.task_done()


def accepted_day(now, timezone):
    timezone = timezone or "Asia/Shanghai"
    return datetime.fromtimestamp(now, ZoneInfo(timezone)).date().isoformat(), timezone
