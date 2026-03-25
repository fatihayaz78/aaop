"""Seed mock data for AI Lab."""
from __future__ import annotations
import random
from datetime import datetime, timedelta, timezone
from uuid import uuid4
import structlog
from shared.clients.duckdb_client import DuckDBClient

logger = structlog.get_logger(__name__)

def seed_ai_lab_mock_data(duck: DuckDBClient, tenant_id: str = "s_sport_plus") -> None:
    duck.execute("""CREATE TABLE IF NOT EXISTS shared_analytics.experiments (
        id VARCHAR, tenant_id VARCHAR, name VARCHAR, hypothesis VARCHAR,
        status VARCHAR, variant_a VARCHAR, variant_b VARCHAR,
        sample_size INTEGER, p_value DOUBLE, confidence_interval VARCHAR,
        winner VARCHAR, created_at VARCHAR, completed_at VARCHAR)""")
    duck.execute("""CREATE TABLE IF NOT EXISTS shared_analytics.model_registry (
        id VARCHAR, tenant_id VARCHAR, model_name VARCHAR, version VARCHAR,
        status VARCHAR, accuracy DOUBLE, latency_ms DOUBLE,
        deployed_at VARCHAR, created_at VARCHAR)""")
    try:
        row = duck.fetch_one("SELECT COUNT(*) as cnt FROM shared_analytics.experiments WHERE tenant_id = ?", [tenant_id])
        if row and row.get("cnt", 0) >= 5:
            return
    except Exception: pass

    now = datetime.now(timezone.utc)
    exps = [
        ("Haiku vs Sonnet for P3 Alerts", "Haiku provides equal accuracy at lower cost", "completed"),
        ("Threshold Sensitivity A/B", "Lower threshold reduces false negatives by 20%", "completed"),
        ("RAG Chunk Size Optimization", "512 tokens outperforms 256 for incident RAG", "completed"),
        ("Prompt Template Comparison", "Structured prompts improve RCA quality", "completed"),
        ("Dedup Window Duration Test", "900s window optimal for alert dedup", "completed"),
        ("Context Window Size Test", "Larger context improves correlation", "completed"),
        ("Multi-CDN Routing ML", "ML routing reduces latency by 15%", "running"),
        ("Anomaly Detection Sensitivity", "Z-score 2.0 vs 2.5 threshold", "running"),
        ("Bilingual Output Quality", "Turkish summaries match English detail quality", "draft"),
        ("Cost Optimization Pipeline", "Batch processing reduces token cost 40%", "draft"),
    ]
    for name, hyp, status in exps:
        pv = round(random.uniform(0.001, 0.04), 4) if status == "completed" else None
        winner = random.choice(["variant_a", "variant_b"]) if status == "completed" else None
        comp = (now - timedelta(days=random.randint(1, 14))).isoformat() if status == "completed" else None
        try:
            duck.execute("INSERT INTO shared_analytics.experiments VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?)",
                [f"EXP-{uuid4().hex[:8]}", tenant_id, name, hyp, status,
                 "Variant A config", "Variant B config", random.randint(100, 5000),
                 pv, "95%" if status == "completed" else None, winner,
                 (now - timedelta(days=random.randint(1, 30))).isoformat(), comp])
        except Exception: pass

    models = [
        ("claude-haiku-incident", "v2.1", "production", 0.89, 65),
        ("claude-sonnet-rca", "v3.0", "production", 0.94, 320),
        ("claude-opus-p0", "v1.2", "production", 0.97, 780),
        ("claude-haiku-dedup", "v2.0", "staging", 0.87, 55),
        ("claude-sonnet-qoe", "v2.3", "staging", 0.92, 280),
        ("claude-haiku-alert", "v3.1", "staging", 0.90, 70),
        ("claude-sonnet-rca", "v2.0", "deprecated", 0.85, 350),
        ("claude-haiku-incident", "v1.0", "deprecated", 0.82, 80),
    ]
    for mname, ver, status, acc, lat in models:
        try:
            duck.execute("INSERT INTO shared_analytics.model_registry VALUES (?,?,?,?,?,?,?,?,?)",
                [f"MOD-{uuid4().hex[:8]}", tenant_id, mname, ver, status, acc, lat,
                 (now - timedelta(days=random.randint(1, 60))).isoformat() if status != "deprecated" else None,
                 (now - timedelta(days=random.randint(1, 90))).isoformat()])
        except Exception: pass
    logger.info("ai_lab_seed_complete", tenant_id=tenant_id)
