"""EPG (Electronic Program Guide) schema — daily schedule per channel."""

from __future__ import annotations

from pydantic import BaseModel


class EPGProgram(BaseModel):
    """Single EPG program slot."""

    # ── META ──
    program_id: str  # PRG-{8hex}
    channel_id: str
    channel_name: str
    start_time: str  # UTC ISO 8601
    end_time: str
    duration_min: int

    # ── İÇERİK ──
    title: str
    category: str  # live_sport | news | magazine | vod | highlight
    is_live: bool
    is_premium: bool
    language: str  # tr | en

    # ── SPOR DETAYI ──
    sport_type: str | None = None  # football | basketball | ufc | motorsport
    competition: str | None = None
    season: str | None = None  # 2025-26
    week: int | None = None
    teams: list[str] | None = None
    venue: str | None = None
    is_derby: bool = False

    # ── KAPASİTE ──
    expected_viewers: int
    expected_peak_viewers: int
    pre_scale_required: bool  # expected_viewers > 50K
    pre_scale_time: str | None = None  # 30 min before start
    historical_avg_viewers: int | None = None


FIELD_CATEGORIES: dict[str, str] = {
    "program_id": "meta", "channel_id": "meta", "channel_name": "meta",
    "start_time": "meta", "end_time": "meta", "duration_min": "meta",
    "title": "content", "category": "content", "is_live": "content",
    "is_premium": "content", "language": "content",
    "sport_type": "sport", "competition": "sport", "season": "sport",
    "week": "sport", "teams": "sport", "venue": "sport", "is_derby": "sport",
    "expected_viewers": "capacity", "expected_peak_viewers": "capacity",
    "pre_scale_required": "capacity", "pre_scale_time": "capacity",
    "historical_avg_viewers": "capacity",
}

FIELD_DESCRIPTIONS: dict[str, str] = {
    "program_id": "Unique program identifier (PRG-{8hex})",
    "channel_id": "Channel identifier",
    "channel_name": "Channel display name",
    "start_time": "Program start time (UTC ISO 8601)",
    "end_time": "Program end time (UTC ISO 8601)",
    "duration_min": "Program duration in minutes",
    "title": "Program title",
    "category": "Content category (live_sport/news/magazine/vod/highlight)",
    "is_live": "Whether the program is broadcast live",
    "is_premium": "Whether premium subscription is required",
    "language": "Broadcast language (tr/en)",
    "sport_type": "Sport type (football/basketball/ufc/motorsport)",
    "competition": "Competition name (La Liga, EuroLeague, etc.)",
    "season": "Sports season (e.g. 2025-26)",
    "week": "Competition week/matchday number",
    "teams": "Teams playing (for sports events)",
    "venue": "Event venue name",
    "is_derby": "Whether this is a high-profile derby match",
    "expected_viewers": "Expected concurrent viewers",
    "expected_peak_viewers": "Expected peak concurrent viewers",
    "pre_scale_required": "Whether infrastructure pre-scaling is needed (>50K viewers)",
    "pre_scale_time": "When to start pre-scaling (30 min before start)",
    "historical_avg_viewers": "Historical average viewers for similar events",
}
