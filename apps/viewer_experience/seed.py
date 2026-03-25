"""Seed mock data for Viewer Experience — QoE metrics + complaints."""

from __future__ import annotations

import json
import random
from datetime import datetime, timedelta, timezone
from uuid import uuid4

import structlog

from shared.clients.duckdb_client import DuckDBClient
from shared.clients.sqlite_client import SQLiteClient

logger = structlog.get_logger(__name__)

_TITLES = [
    "Galatasaray maçında sürekli takılma", "beIN Sports 2 ses gelmiyor",
    "4K içerik HD kalitede geliyor", "Şampiyonlar Ligi maçı dondu",
    "Altyazı senkron sorunu", "Mobil uygulama çöküyor", "Giriş yapılamıyor",
    "Canlı yayın 10 saniye gecikiyor", "Ses video uyuşmuyor", "Kalite otomatik düşüyor",
    "Maç ortasında yayın kesildi", "Smart TV uygulaması açılmıyor",
    "VOD içerik yüklenmiyor", "Reklam sonrası yayın donuyor",
    "Çoklu cihaz limiti hatası", "Chromecast bağlantı sorunu",
    "İngilizce yayın sesi geliyor", "Maç tekrarı bulunamıyor",
    "Favori takım bildirimi gelmiyor", "Ödeme sayfası hata veriyor",
]

_CATEGORIES = ["buffering", "playback_error", "audio_sync", "login_issue", "content_quality", "subtitle"]
_REGIONS = ["istanbul", "ankara", "izmir", "london", "dubai"]
_DEVICES = ["mobile", "desktop", "smarttv", "tablet"]
_CONTENT_TYPES = ["live", "vod"]


async def seed_viewer_experience_mock_data(
    sqlite: SQLiteClient,
    duck: DuckDBClient,
    tenant_id: str = "s_sport_plus",
) -> None:
    """Seed QoE metrics + complaints. Idempotent."""
    try:
        row = duck.fetch_one("SELECT COUNT(*) as cnt FROM shared_analytics.qoe_metrics WHERE tenant_id = ?", [tenant_id])
        if row and row.get("cnt", 0) >= 20:
            logger.info("viewer_seed_skipped", tenant_id=tenant_id, existing=row["cnt"])
            return
    except Exception:
        pass

    now = datetime.now(timezone.utc)

    # ── SQLite complaints table ──
    await sqlite.execute("""CREATE TABLE IF NOT EXISTS complaints (
        id TEXT PRIMARY KEY, tenant_id TEXT NOT NULL, title TEXT NOT NULL,
        category TEXT, content TEXT, sentiment TEXT DEFAULT 'pending',
        priority TEXT DEFAULT 'P3', status TEXT DEFAULT 'open',
        created_at TEXT DEFAULT (datetime('now'))
    )""")

    existing = await sqlite.fetch_one("SELECT COUNT(*) as cnt FROM complaints WHERE tenant_id = ?", (tenant_id,))
    if not existing or existing.get("cnt", 0) < 5:
        sentiments = ["negative"] * 14 + ["neutral"] * 4 + ["positive"] * 2
        priorities = ["P1"] * 5 + ["P2"] * 10 + ["P3"] * 5
        statuses = ["open"] * 12 + ["resolved"] * 8
        random.shuffle(sentiments)
        random.shuffle(priorities)
        random.shuffle(statuses)

        for i in range(20):
            await sqlite.execute(
                "INSERT OR IGNORE INTO complaints (id, tenant_id, title, category, content, sentiment, priority, status, created_at) VALUES (?,?,?,?,?,?,?,?,?)",
                (f"CMP-{uuid4().hex[:10]}", tenant_id, _TITLES[i % len(_TITLES)],
                 random.choice(_CATEGORIES), f"Detay: {_TITLES[i % len(_TITLES)]}",
                 sentiments[i], priorities[i], statuses[i],
                 (now - timedelta(hours=random.randint(1, 168))).isoformat()),
            )

    # ── DuckDB QoE metrics ──
    for _ in range(200):
        r = random.random()
        if r < 0.6:
            score = round(random.uniform(3.5, 5.0), 2)
        elif r < 0.9:
            score = round(random.uniform(2.5, 3.5), 2)
        else:
            score = round(random.uniform(1.0, 2.5), 2)

        device_weights = [0.35, 0.30, 0.25, 0.10]
        device = random.choices(_DEVICES, weights=device_weights, k=1)[0]
        content = random.choices(_CONTENT_TYPES, weights=[0.4, 0.6], k=1)[0]

        try:
            duck.execute(
                """INSERT INTO shared_analytics.qoe_metrics
                   (metric_id, tenant_id, session_id, device_type, region,
                    buffering_ratio, startup_time_ms, bitrate_avg, quality_score, event_ts)
                   VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
                [f"QOE-{uuid4().hex[:10]}", tenant_id, str(uuid4()), device,
                 random.choice(_REGIONS), round(random.uniform(0.0, 0.12), 4),
                 random.randint(800, 4500), random.randint(1000, 8000), score,
                 (now - timedelta(hours=random.randint(0, 168))).isoformat()],
            )
        except Exception:
            pass

    logger.info("viewer_seed_complete", tenant_id=tenant_id, qoe=200, complaints=20)
