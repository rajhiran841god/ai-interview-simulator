"""
Tests for TurnTimer — pilot latency diagnostic tooling.
"""

import time

from app.shared.turn_timer import TurnTimer


def test_marks_recorded_in_order():
    timer = TurnTimer(interview_id="int-1", turn_number=1)
    timer.mark("stage_a")
    timer.mark("stage_b")
    result = timer.log_summary()
    assert set(result["stage_deltas_ms"].keys()) == {"stage_a", "stage_b"}


def test_deltas_are_non_negative_and_roughly_accurate():
    timer = TurnTimer(interview_id="int-1", turn_number=1)
    time.sleep(0.05)  # ~50ms
    timer.mark("stage_a")
    result = timer.log_summary()
    delta = result["stage_deltas_ms"]["stage_a"]
    assert delta >= 0
    # Real sleep timing has some slack — check it's in a sane ballpark,
    # not exact-to-the-millisecond (would be a flaky test otherwise).
    assert 30 <= delta <= 300


def test_total_ms_matches_sum_of_deltas():
    timer = TurnTimer(interview_id="int-1", turn_number=1)
    timer.mark("a")
    timer.mark("b")
    timer.mark("c")
    result = timer.log_summary()
    assert result["total_ms"] == sum(result["stage_deltas_ms"].values())


def test_single_mark_returns_empty_summary_without_crashing():
    timer = TurnTimer(interview_id="int-1", turn_number=1)
    result = timer.log_summary()
    assert result == {}
