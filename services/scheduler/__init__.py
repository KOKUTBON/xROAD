"""Celery-beat scheduler runtime for the Road Risk product platform.

This package owns the recurring schedule for background work. The
foundation step (#86) wires the beat schedule against the health task
only. Real recurring jobs (published refresh, stale-source checks,
reports) are added incrementally under #87, #94, and #95.

"""

from services.scheduler.beat_schedule import (
    BEAT_SCHEDULE,
    build_beat_schedule,
    register_beat_schedule,
)

__all__ = [
    "BEAT_SCHEDULE",
    "build_beat_schedule",
    "register_beat_schedule",
]
