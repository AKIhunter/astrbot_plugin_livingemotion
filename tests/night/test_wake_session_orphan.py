"""唤醒会话不得脱离夜间周期独立存在（2026-11-14 静默拒答事故回归）。"""

from astrbot_plugin_livingemotion.contracts import NightPhase, NightState, SleepState
from astrbot_plugin_livingemotion.domain.night import (
    LifePolicy, advance_life, start_life_reply, submit_life_reply,
)

NOW = 1_800_000_000.0
SESSION = "e0c40907dfb068181db8b0732b1388ab216f1c73cd878fd41045e598b55f42ec"


def orphan_state(**overrides):
    """白天：没有周期，却挂着一个额度已用尽的唤醒会话。"""
    fields = dict(
        phase=NightPhase.AWAKE, energy=100.0, updated_at=NOW - 60,
        reason_codes=("recovery",), display_state=SleepState.AWAKE, policy_version=2,
        energy_units=1000, energy_remainder=0, energy_direction="recovery",
        wake_session=SESSION, wake_replies_used=3, wake_reply_limit=3,
        first_reply_submitted_at=NOW - 900, wake_window_deadline=NOW - 300,
        wake_at=None, cycle_id=None, deep_sleep_at=None, wake_failures=5, wake_score=6,
    )
    fields.update(overrides)
    return NightState(**fields)


def test_orphan_session_never_blocks_reply():
    """根因场景：孤儿会话 3/3 时仍然允许回复，并就地作废账本。"""
    state, allowed = start_life_reply(orphan_state())

    assert allowed is True
    assert state.wake_session is None
    assert state.wake_replies_used == 0
    assert state.wake_reply_limit == 0
    assert state.wake_window_deadline is None
    assert state.first_reply_submitted_at is None


def test_advance_life_settles_orphan_session():
    """时间推进结算必须清掉孤儿会话，而不是留到下一次判定。"""
    state, _ = advance_life(orphan_state(), now=NOW, cycle=None)

    assert state.wake_session is None
    assert state.wake_replies_used == 0
    assert state.display_state is SleepState.AWAKE


def test_clock_rollback_still_does_not_deadlock():
    """时钟回拨时 advance_life 直接早退，放行仍由 start_life_reply 兜住。"""
    stale = orphan_state(updated_at=NOW + 600)
    settled, _ = advance_life(stale, now=NOW, cycle=None)
    assert settled.wake_session == SESSION  # 早退，未结算

    _, allowed = start_life_reply(settled)
    assert allowed is True


def test_submit_life_reply_clears_ledger_when_cycle_ends():
    """精力耗尽并结束周期的那一刻，就地把唤醒账本一起清干净。"""
    state = orphan_state(energy=11.0, energy_units=110, wake_at=NOW - 10)

    state, _ = submit_life_reply(state, now=NOW, policy=LifePolicy(), allow_sleep=True)

    assert state.wake_at is None
    assert state.cycle_id is None
    assert state.wake_session is None
    assert state.wake_replies_used == 0
    assert state.wake_reply_limit == 0
    assert state.display_state is SleepState.DROWSY


def test_active_cycle_still_enforces_round_limit():
    """回归保护：有活跃夜间周期时，额度耗尽依然必须拒答。"""
    state = orphan_state(wake_at=NOW + 3600, cycle_id="cycle-night")
    state, allowed = start_life_reply(state, now=NOW)

    assert allowed is False
    assert state.display_state is SleepState.DROWSY
    assert state.wake_session == SESSION


def test_expired_cycle_releases_ledger_when_settlement_skipped():
    """周期已过期但结算没跑到（时钟回拨早退）：传了 now 就必须放行。

    这类状态里 wake_at / cycle_id 都还在，按「缺字段即孤儿」是判不出来的，
    只有把 now 一起看才能认出「周期已经走完了」。
    """
    stale = orphan_state(wake_at=NOW - 600, cycle_id="cycle-night", updated_at=NOW + 600)
    settled, _ = advance_life(stale, now=NOW, cycle=None)
    assert settled.wake_session == SESSION      # 时钟回拨，advance_life 早退未结算
    assert settled.wake_at is not None          # 周期字段还在，不属于「缺字段」型孤儿

    state, allowed = start_life_reply(settled, now=NOW)

    assert allowed is True
    assert state.wake_session is None
    assert state.wake_replies_used == 0
    assert state.wake_reply_limit == 0


def test_zero_quota_is_not_exhaustion():
    """0/0 不是「用尽」：没有配置额度时不该拿它拒答。"""
    state = orphan_state(wake_at=NOW + 3600, cycle_id="cycle-night",
                         wake_replies_used=0, wake_reply_limit=0)

    state, allowed = start_life_reply(state, now=NOW)

    assert allowed is True
    assert state.wake_session is None
    assert state.wake_replies_used == 0


def test_active_cycle_consumes_round_then_blocks():
    """回归保护：周期内的轮次消耗与终点判定不被本次修复放宽。"""
    state = orphan_state(wake_at=NOW + 3600, cycle_id="cycle-night",
                         wake_replies_used=0, wake_reply_limit=1)

    state, first = start_life_reply(state)
    assert first is True
    assert state.wake_replies_used == 1
    assert state.display_state is SleepState.DROWSY

    _, second = start_life_reply(state)
    assert second is False
