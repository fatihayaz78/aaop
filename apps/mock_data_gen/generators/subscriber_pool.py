"""Subscriber pool — 485K deterministic subscribers with Turkish demographics.

Lazy-loaded, memory-efficient pool using seed(42) for reproducibility.
"""

from __future__ import annotations

import hashlib
import random
from dataclasses import dataclass, field

# ── Distribution constants (from spec) ──

TOTAL_SUBSCRIBERS = 485_000

TIER_DISTRIBUTION: dict[str, float] = {
    "premium": 0.37,   # 180K
    "standard": 0.34,  # 165K
    "free": 0.29,      # 140K
}

COUNTRY_DISTRIBUTION: dict[str, float] = {
    "TR": 0.94,
    "DE": 0.02,
    "CY": 0.015,
    "NL": 0.008,
    "OTHER": 0.007,
}

TR_CITIES: dict[str, float] = {
    "İstanbul": 0.38,
    "Ankara": 0.14,
    "İzmir": 0.10,
    "Bursa": 0.05,
    "Antalya": 0.04,
    "Adana": 0.03,
    "Konya": 0.03,
    "Gaziantep": 0.02,
    "Diğer": 0.21,
}

DEVICE_DISTRIBUTION: dict[str, float] = {
    "android": 0.35,
    "ios": 0.22,
    "tizen_os": 0.14,
    "web_chrome": 0.08,
    "android_tv": 0.07,
    "webos": 0.06,
    "apple_tv": 0.04,
    "web_safari": 0.02,
    "web_firefox": 0.02,
}

DRM_BY_DEVICE: dict[str, str] = {
    "android": "widevine",
    "android_tv": "widevine",
    "web_chrome": "widevine",
    "web_firefox": "widevine",
    "tizen_os": "widevine",
    "webos": "widevine",
    "ios": "fairplay",
    "apple_tv": "fairplay",
    "web_safari": "fairplay",
}

# Foreign city pools
_FOREIGN_CITIES: dict[str, list[str]] = {
    "DE": ["Berlin", "München", "Frankfurt", "Hamburg", "Köln"],
    "CY": ["Lefkoşa", "Girne", "Gazimağusa"],
    "NL": ["Amsterdam", "Rotterdam", "Den Haag"],
    "OTHER": ["Londra", "Paris", "Brüksel", "Viyana"],
}


@dataclass(frozen=True, slots=True)
class Subscriber:
    """A single subscriber in the pool."""

    user_id: str
    device_id: str
    tier: str           # premium | standard | free
    country: str        # ISO 2-letter
    city: str
    device_type: str    # android | ios | tizen_os | ...
    drm_type: str       # widevine | fairplay
    email_hash: str     # SHA256 hash of synthetic email


def _weighted_choice(rng: random.Random, options: dict[str, float]) -> str:
    """Pick a key from a {key: probability} dict using the given RNG."""
    keys = list(options.keys())
    weights = list(options.values())
    return rng.choices(keys, weights=weights, k=1)[0]


def _generate_subscriber(rng: random.Random, index: int) -> Subscriber:
    """Generate a single deterministic subscriber."""
    user_id = f"u_{index:06d}"
    device_id = hashlib.sha256(f"device_{index}_{rng.randint(0, 999999)}".encode()).hexdigest()[:16]

    tier = _weighted_choice(rng, TIER_DISTRIBUTION)
    country = _weighted_choice(rng, COUNTRY_DISTRIBUTION)

    if country == "TR":
        city = _weighted_choice(rng, TR_CITIES)
    elif country in _FOREIGN_CITIES:
        city = rng.choice(_FOREIGN_CITIES[country])
    else:
        city = rng.choice(_FOREIGN_CITIES["OTHER"])

    device_type = _weighted_choice(rng, DEVICE_DISTRIBUTION)
    drm_type = DRM_BY_DEVICE[device_type]

    email_hash = hashlib.sha256(f"user_{index}@ssport.mock".encode()).hexdigest()

    return Subscriber(
        user_id=user_id,
        device_id=device_id,
        tier=tier,
        country=country,
        city=city,
        device_type=device_type,
        drm_type=drm_type,
        email_hash=email_hash,
    )


class SubscriberPool:
    """Lazy-loaded pool of 485K subscribers.

    Subscribers are generated on first access and cached.
    Uses seed(42) for deterministic output.

    Usage:
        pool = SubscriberPool()
        sub = pool[0]                         # single subscriber
        batch = pool.sample(1000)             # random sample
        ios_users = pool.filter_by_device("ios")
    """

    def __init__(self, size: int = TOTAL_SUBSCRIBERS, seed: int = 42) -> None:
        self._size = size
        self._seed = seed
        self._pool: list[Subscriber] | None = None
        self._rng = random.Random(seed)

    def _ensure_loaded(self) -> list[Subscriber]:
        if self._pool is None:
            rng = random.Random(self._seed)
            self._pool = [_generate_subscriber(rng, i) for i in range(self._size)]
        return self._pool

    def __len__(self) -> int:
        return self._size

    def __getitem__(self, index: int) -> Subscriber:
        return self._ensure_loaded()[index]

    def sample(self, n: int, seed: int | None = None) -> list[Subscriber]:
        """Return n random subscribers from the pool."""
        pool = self._ensure_loaded()
        rng = random.Random(seed) if seed is not None else self._rng
        return rng.sample(pool, min(n, len(pool)))

    def filter_by_tier(self, tier: str) -> list[Subscriber]:
        """Return all subscribers of a given tier."""
        return [s for s in self._ensure_loaded() if s.tier == tier]

    def filter_by_device(self, device_type: str) -> list[Subscriber]:
        """Return all subscribers using a specific device type."""
        return [s for s in self._ensure_loaded() if s.device_type == device_type]

    def filter_by_drm(self, drm_type: str) -> list[Subscriber]:
        """Return all subscribers using a specific DRM type."""
        return [s for s in self._ensure_loaded() if s.drm_type == drm_type]

    def filter_by_country(self, country: str) -> list[Subscriber]:
        """Return all subscribers from a specific country."""
        return [s for s in self._ensure_loaded() if s.country == country]

    @property
    def stats(self) -> dict:
        """Return distribution statistics for the pool."""
        pool = self._ensure_loaded()
        tiers: dict[str, int] = {}
        countries: dict[str, int] = {}
        devices: dict[str, int] = {}
        for s in pool:
            tiers[s.tier] = tiers.get(s.tier, 0) + 1
            countries[s.country] = countries.get(s.country, 0) + 1
            devices[s.device_type] = devices.get(s.device_type, 0) + 1
        return {"total": len(pool), "tiers": tiers, "countries": countries, "devices": devices}
