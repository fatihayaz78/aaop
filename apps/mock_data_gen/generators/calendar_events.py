"""Calendar events for 91-day mock data period (01.01–31.03.2026).

Provides CalendarEvent dataclass, CALENDAR_EVENTS list, and
get_traffic_multiplier() for date-aware traffic shaping.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import date, datetime, time


@dataclass(frozen=True, slots=True)
class CalendarEvent:
    """A calendar event that affects traffic patterns."""

    date: date
    name: str
    multiplier: float  # traffic multiplier (1.0 = normal)
    anomaly: str | None = None  # anomaly type if applicable
    start_time: time | None = None  # local TR time (UTC+3)
    end_time: time | None = None  # local TR time (UTC+3)
    channels: tuple[str, ...] = ()  # affected channels (empty = all)
    competition: str | None = None


# ── 91-day calendar: 01.01.2026 – 31.03.2026 ──

CALENDAR_EVENTS: list[CalendarEvent] = [
    # Ocak
    CalendarEvent(
        date=date(2026, 1, 5),
        name="La Liga — Real Sociedad vs Atletico",
        multiplier=2.5,
        competition="La Liga",
        channels=("s_sport_1",),
    ),
    CalendarEvent(
        date=date(2026, 1, 12),
        name="EuroLeague — 4 maç",
        multiplier=1.8,
        competition="EuroLeague",
        channels=("s_sport_1", "s_sport_2"),
    ),
    CalendarEvent(
        date=date(2026, 1, 19),
        name="Serie A — Inter vs Juventus",
        multiplier=2.0,
        competition="Serie A",
        channels=("s_sport_2",),
    ),
    CalendarEvent(
        date=date(2026, 1, 25),
        name="UFC Fight Night",
        multiplier=1.8,
        competition="UFC",
        channels=("s_plus_live_1",),
    ),
    # Şubat
    CalendarEvent(
        date=date(2026, 2, 4),
        name="La Liga — Barcelona vs Sevilla",
        multiplier=2.5,
        competition="La Liga",
        channels=("s_sport_1",),
    ),
    CalendarEvent(
        date=date(2026, 2, 11),
        name="EuroLeague — 6 maç",
        multiplier=2.0,
        competition="EuroLeague",
        channels=("s_sport_1", "s_sport_2"),
    ),
    CalendarEvent(
        date=date(2026, 2, 15),
        name="MotoGP Portimao",
        multiplier=1.6,
        competition="MotoGP",
        channels=("s_sport_2",),
    ),
    CalendarEvent(
        date=date(2026, 2, 22),
        name="Bundesliga — Bayern vs Dortmund",
        multiplier=2.8,
        competition="Bundesliga",
        channels=("s_sport_1",),
    ),
    CalendarEvent(
        date=date(2026, 2, 28),
        name="CDN Kesintisi",
        multiplier=1.0,
        anomaly="cdn_outage",
        start_time=time(22, 15),
        end_time=time(22, 45),
    ),
    # Mart
    CalendarEvent(
        date=date(2026, 3, 1),
        name="Serie A — Milan vs Napoli",
        multiplier=2.2,
        competition="Serie A",
        channels=("s_sport_2",),
    ),
    CalendarEvent(
        date=date(2026, 3, 4),
        name="ElClasico + UFC PPV",
        multiplier=10.0,
        anomaly="peak_event",
        competition="La Liga",
        channels=("s_sport_1", "s_plus_live_1"),
    ),
    CalendarEvent(
        date=date(2026, 3, 8),
        name="EuroLeague — 8 maç",
        multiplier=2.0,
        competition="EuroLeague",
        channels=("s_sport_1", "s_sport_2"),
    ),
    CalendarEvent(
        date=date(2026, 3, 15),
        name="FairPlay Sertifika Sorunu",
        multiplier=1.0,
        anomaly="fairplay_cert_expired",
    ),
    CalendarEvent(
        date=date(2026, 3, 18),
        name="MotoGP Arjantin",
        multiplier=1.6,
        competition="MotoGP",
        channels=("s_sport_2",),
    ),
    CalendarEvent(
        date=date(2026, 3, 22),
        name="NBA — 4 maç",
        multiplier=1.5,
        competition="NBA",
        channels=("s_sport_1", "s_sport_2"),
    ),
    # Ramazan Bayramı — 3 gün
    CalendarEvent(
        date=date(2026, 3, 29),
        name="Ramazan Bayramı — 1. gün",
        multiplier=0.6,
        anomaly="holiday",
    ),
    CalendarEvent(
        date=date(2026, 3, 30),
        name="Ramazan Bayramı — 2. gün",
        multiplier=0.6,
        anomaly="holiday",
    ),
    CalendarEvent(
        date=date(2026, 3, 31),
        name="Ramazan Bayramı — 3. gün",
        multiplier=0.6,
        anomaly="holiday",
    ),
]

# Index by date for O(1) lookup
_EVENTS_BY_DATE: dict[date, list[CalendarEvent]] = {}
for _evt in CALENDAR_EVENTS:
    _EVENTS_BY_DATE.setdefault(_evt.date, []).append(_evt)


def get_events_for_date(target: date) -> list[CalendarEvent]:
    """Return all calendar events for a given date."""
    return _EVENTS_BY_DATE.get(target, [])


def get_traffic_multiplier(target: date) -> float:
    """Return the highest traffic multiplier for a given date.

    If multiple events overlap on the same day, the highest multiplier wins.
    Returns 1.0 for days with no events.
    """
    events = get_events_for_date(target)
    if not events:
        return 1.0
    return max(e.multiplier for e in events)


def get_anomaly_for_date(target: date) -> str | None:
    """Return the anomaly type for a given date, or None."""
    events = get_events_for_date(target)
    for e in events:
        if e.anomaly:
            return e.anomaly
    return None


def is_anomaly_active(target: datetime, anomaly_type: str) -> bool:
    """Check if a time-bounded anomaly is active at a specific datetime.

    For anomalies with start_time/end_time, checks if target falls within
    the window. For anomalies without time bounds, returns True for the
    entire day.
    """
    events = get_events_for_date(target.date())
    for e in events:
        if e.anomaly != anomaly_type:
            continue
        if e.start_time is None or e.end_time is None:
            return True
        local_time = target.time()
        return e.start_time <= local_time <= e.end_time
    return False
