"""
Turn-level latency diagnostics — pilot-preparation tooling, not an
engine feature. Answers exactly one question: "where did the time go
on this turn?" Built specifically for VOICE_VALIDATION.md's Test 2
(latency measurement), which was explicitly flagged as not optional
polish — the test that tells you whether the voice approach works at
all.

Deliberately simple: named timestamp marks, deltas between them, one
structured log line per turn. No metrics backend, no dashboards — logs
only, per the "diagnostic mode," not "analytics dashboard" framing
(analytics dashboards were explicitly out of scope for this sprint).
"""

import logging
import time
from dataclasses import dataclass, field
from datetime import datetime

logger = logging.getLogger("placementos.latency")


@dataclass
class _Mark:
    label: str
    wall_clock: datetime
    monotonic: float


@dataclass
class TurnTimer:
    """One instance per conversational turn. Call .mark(label) at each
    stage boundary, then .log_summary() once at the end of the turn."""

    interview_id: str
    turn_number: int
    _marks: list = field(default_factory=list)

    def __post_init__(self):
        self.mark("turn_start")

    def mark(self, label: str) -> None:
        self._marks.append(
            _Mark(label=label, wall_clock=datetime.now(), monotonic=time.monotonic())
        )

    def log_summary(self) -> dict:
        """Logs a human-readable summary (matching the format requested:
        stage name, wall-clock time, delta from previous stage, total
        latency) and returns the same data as a dict for programmatic
        use (e.g. aggregating avg/max/p95 across a pilot session)."""
        if len(self._marks) < 2:
            logger.warning(
                "TurnTimer for interview %s turn %d has fewer than 2 marks — nothing to summarize.",
                self.interview_id,
                self.turn_number,
            )
            return {}

        lines = [f"Turn {self.turn_number} (interview {self.interview_id})"]
        stage_deltas_ms = {}
        for i in range(1, len(self._marks)):
            prev, curr = self._marks[i - 1], self._marks[i]
            delta_ms = (curr.monotonic - prev.monotonic) * 1000
            stage_deltas_ms[curr.label] = delta_ms
            lines.append(
                f"  {prev.label} -> {curr.label}: {curr.wall_clock.strftime('%H:%M:%S.%f')[:-3]} "
                f"(+{delta_ms:.0f}ms)"
            )

        total_ms = (self._marks[-1].monotonic - self._marks[0].monotonic) * 1000
        lines.append(f"  TOTAL: {total_ms / 1000:.2f}s")

        summary_text = "\n".join(lines)
        logger.info(summary_text)

        return {
            "interview_id": self.interview_id,
            "turn_number": self.turn_number,
            "stage_deltas_ms": stage_deltas_ms,
            "total_ms": total_ms,
        }
