"""EPG generator — daily program guide per channel.

Output: epg/YYYY/MM/DD/{YYYY-MM-DD}.json
"""

from __future__ import annotations

import uuid
from datetime import date, datetime, timedelta, timezone

import structlog

from apps.mock_data_gen.generators.base_generator import BaseGenerator
from apps.mock_data_gen.generators.calendar_events import get_events_for_date

logger = structlog.get_logger(__name__)

CHANNELS = {
    "s_sport_1": "S Sport",
    "s_sport_2": "S Sport 2",
    "s_plus_live_1": "S+ Live 1",
    "cnn_turk": "CNN Türk",
    "trt_spor": "TRT Spor",
    "a_spor": "A Spor",
}

# Filler program templates
FILLER_PROGRAMS = [
    ("Spor Bülteni", "news", 30),
    ("Stüdyo Analiz", "magazine", 60),
    ("Maç Özeti", "highlight", 45),
    ("Transfer Gündemi", "magazine", 30),
    ("Spor Sabahı", "news", 60),
    ("Devre Arası", "magazine", 30),
    ("Gece Raporu", "news", 30),
    ("Kısa Özetler", "highlight", 15),
]

# Viewer estimates by competition
VIEWER_ESTIMATES: dict[str, tuple[int, int]] = {
    "La Liga": (80_000, 150_000),
    "Serie A": (60_000, 100_000),
    "Bundesliga": (40_000, 70_000),
    "EuroLeague": (50_000, 90_000),
    "NBA": (30_000, 60_000),
    "UFC": (120_000, 180_000),
    "MotoGP": (45_000, 80_000),
}

VENUES = {
    "La Liga": ["Santiago Bernabéu", "Camp Nou", "Anoeta", "Sánchez-Pizjuán"],
    "Serie A": ["San Siro", "Allianz Stadium", "Stadio Diego Armando Maradona"],
    "Bundesliga": ["Allianz Arena", "Signal Iduna Park"],
    "EuroLeague": ["Sinan Erdem Dome", "WiZink Center", "Ülker Sports Arena"],
    "NBA": ["Madison Square Garden", "Crypto.com Arena", "TD Garden"],
    "UFC": ["T-Mobile Arena", "UFC Apex"],
    "MotoGP": ["Portimão", "Termas de Río Hondo"],
}


class EPGGenerator(BaseGenerator):
    """Generates daily EPG program schedules."""

    @property
    def source_name(self) -> str:
        return "epg"

    def _make_program(self, channel_id: str, start: datetime, duration_min: int,
                      title: str, category: str, is_live: bool = False,
                      sport_type: str | None = None, competition: str | None = None,
                      teams: list[str] | None = None, venue: str | None = None,
                      expected_viewers: int = 5000, is_derby: bool = False) -> dict:
        end = start + timedelta(minutes=duration_min)
        peak = int(expected_viewers * self.rng.uniform(1.1, 1.4))
        pre_scale = expected_viewers > 50_000
        pre_time = (start - timedelta(minutes=30)).replace(tzinfo=None).isoformat() + "Z" if pre_scale else None

        return {
            "program_id": f"PRG-{uuid.UUID(int=self.rng.getrandbits(128)).hex[:8]}",
            "channel_id": channel_id,
            "channel_name": CHANNELS[channel_id],
            "start_time": start.replace(tzinfo=None).isoformat() + "Z",
            "end_time": end.replace(tzinfo=None).isoformat() + "Z",
            "duration_min": duration_min,
            "title": title,
            "category": category,
            "is_live": is_live,
            "is_premium": category == "live_sport",
            "language": "tr",
            "sport_type": sport_type,
            "competition": competition,
            "season": "2025-26" if sport_type else None,
            "week": self.rng.randint(1, 38) if sport_type == "football" else None,
            "teams": teams,
            "venue": venue,
            "is_derby": is_derby,
            "expected_viewers": expected_viewers,
            "expected_peak_viewers": peak,
            "pre_scale_required": pre_scale,
            "pre_scale_time": pre_time,
            "historical_avg_viewers": int(expected_viewers * self.rng.uniform(0.8, 1.0)),
        }

    def _fill_channel_day(self, channel_id: str, target_date: date,
                          sport_slots: list[dict]) -> list[dict]:
        """Fill a 24h schedule with sport events + filler programs."""
        programs: list[dict] = []
        day_start = datetime(target_date.year, target_date.month, target_date.day,
                             0, 0, 0, tzinfo=timezone.utc)

        # Place sport events first
        occupied: list[tuple[datetime, datetime]] = []
        for slot in sport_slots:
            programs.append(slot)
            st = datetime.fromisoformat(slot["start_time"].replace("Z", "")).replace(tzinfo=timezone.utc)
            et = datetime.fromisoformat(slot["end_time"].replace("Z", "")).replace(tzinfo=timezone.utc)
            occupied.append((st, et))

        occupied.sort(key=lambda x: x[0])

        # Fill gaps with filler
        cursor = day_start
        day_end = day_start + timedelta(hours=24)

        for occ_start, occ_end in occupied:
            while cursor < occ_start:
                title, cat, dur = self.rng.choice(FILLER_PROGRAMS)
                gap_min = int((occ_start - cursor).total_seconds() / 60)
                if gap_min <= 0:
                    break
                dur = min(dur, gap_min)
                if dur < 15:
                    cursor = occ_start
                    break
                programs.append(self._make_program(
                    channel_id, cursor, dur, title, cat,
                    expected_viewers=self.rng.randint(2000, 15000),
                ))
                cursor += timedelta(minutes=dur)
            cursor = max(cursor, occ_end)

        # Fill remaining time after last event
        while cursor < day_end:
            title, cat, dur = self.rng.choice(FILLER_PROGRAMS)
            remaining = int((day_end - cursor).total_seconds() / 60)
            if remaining < 15:
                break
            dur = min(dur, remaining)
            programs.append(self._make_program(
                channel_id, cursor, dur, title, cat,
                expected_viewers=self.rng.randint(2000, 15000),
            ))
            cursor += timedelta(minutes=dur)

        return programs

    def generate_day(self, target_date: date) -> int:
        """Generate EPG for all channels for a single day."""
        events = get_events_for_date(target_date)
        all_programs: list[dict] = []

        # Build sport slots from calendar events
        channel_sport_slots: dict[str, list[dict]] = {ch: [] for ch in CHANNELS}

        for evt in events:
            if not evt.competition:
                continue

            lo, hi = VIEWER_ESTIMATES.get(evt.competition, (20_000, 50_000))

            # ElClasico special
            is_derby = evt.name.startswith("ElClasico")
            if is_derby:
                lo, hi = 420_000, 480_000

            expected = self.rng.randint(lo, hi)
            venues = VENUES.get(evt.competition, ["TBD"])
            venue = self.rng.choice(venues)

            # Match start time: 18:00-21:00 UTC for most, UFC later
            if evt.competition == "UFC":
                match_hour = 23
                duration = 180
            elif evt.competition == "MotoGP":
                match_hour = 13
                duration = 120
            else:
                match_hour = self.rng.choice([18, 19, 20])
                duration = 120

            match_start = datetime(
                target_date.year, target_date.month, target_date.day,
                match_hour, 0, 0, tzinfo=timezone.utc,
            )

            sport_type_map = {
                "La Liga": "football", "Serie A": "football", "Bundesliga": "football",
                "Türkiye Kupası": "football", "EuroLeague": "basketball",
                "NBA": "basketball", "UFC": "ufc", "MotoGP": "motorsport",
            }

            teams = None
            if "vs" in evt.name or " - " in evt.name:
                parts = evt.name.split(" — ")[-1] if " — " in evt.name else evt.name
                teams = [t.strip() for t in parts.replace(" vs ", " - ").split(" - ")][:2]

            target_channels = list(evt.channels) if evt.channels else ["s_sport_1"]

            for ch in target_channels:
                if ch not in CHANNELS:
                    continue
                slot = self._make_program(
                    ch, match_start, duration,
                    evt.name, "live_sport", is_live=True,
                    sport_type=sport_type_map.get(evt.competition),
                    competition=evt.competition,
                    teams=teams, venue=venue,
                    expected_viewers=expected, is_derby=is_derby,
                )
                channel_sport_slots[ch].append(slot)

        # Fill each channel's day
        for ch_id in CHANNELS:
            ch_programs = self._fill_channel_day(ch_id, target_date, channel_sport_slots[ch_id])
            all_programs.extend(ch_programs)

        # Sort by start_time
        all_programs.sort(key=lambda p: (p["channel_id"], p["start_time"]))

        # Write as single JSON file
        self.write_json(
            all_programs,
            target_date.strftime("%Y"),
            target_date.strftime("%m"),
            target_date.strftime("%d"),
            filename=f"{target_date.isoformat()}.json",
        )

        logger.info("epg_day_complete", date=target_date.isoformat(), programs=len(all_programs))
        return len(all_programs)


if __name__ == "__main__":
    EPGGenerator().generate_all()
