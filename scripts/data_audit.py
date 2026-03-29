"""DuckDB Data Audit — logs.duckdb tarih & kapsam denetimi.

READ-ONLY bağlanır, hiçbir yazma işlemi yapmaz.
Çıktı: stdout + docs/data_audit_report.md
"""

from __future__ import annotations

import sys
from datetime import datetime, timezone
from pathlib import Path

import duckdb

LOGS_DB_PATH = "./data/duckdb/logs.duckdb"
ANALYTICS_DB_PATH = "./data/duckdb/analytics.duckdb"
REPORT_PATH = "./docs/data_audit_report.md"


def run_audit() -> str:
    lines: list[str] = []

    def out(text: str = "") -> None:
        lines.append(text)
        print(text)

    now = datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M:%S UTC")
    out(f"# DuckDB Data Audit Report")
    out(f"Generated: {now}")
    out()

    # ── logs.duckdb ──────────────────────────────────────────
    out("## 1. logs.duckdb — Table Structure")
    out()

    conn = duckdb.connect(LOGS_DB_PATH, read_only=True)

    tables = conn.execute(
        "SELECT table_schema, table_name "
        "FROM information_schema.tables "
        "WHERE table_schema NOT IN ('information_schema', 'pg_catalog') "
        "ORDER BY table_schema, table_name"
    ).fetchall()

    out(f"Total tables: {len(tables)}")
    out()
    out("| Schema | Table |")
    out("|---|---|")
    for schema, table in tables:
        out(f"| {schema} | {table} |")
    out()

    # ── Coverage Summary (aaop_company only) ─────────────────
    out("## 2. Coverage Summary (aaop_company)")
    out()

    aaop_tables = [t for s, t in tables if s == "aaop_company"]

    coverage_rows = []
    for table in aaop_tables:
        full_name = f"aaop_company.{table}"
        try:
            row = conn.execute(f"""
                SELECT
                    '{table}' AS source,
                    COUNT(*)                                          AS row_count,
                    MIN(timestamp)::DATE                              AS min_date,
                    MAX(timestamp)::DATE                              AS max_date,
                    DATEDIFF('day', MIN(timestamp), MAX(timestamp))   AS day_span,
                    COUNT(DISTINCT timestamp::DATE)                   AS distinct_days
                FROM {full_name}
            """).fetchone()
            coverage_rows.append(row)
        except Exception as e:
            coverage_rows.append((table, 0, None, None, 0, 0))
            out(f"<!-- Error querying {full_name}: {e} -->")

    out("| Source | Rows | Min Date | Max Date | Day Span | Distinct Days | Avg Rows/Day |")
    out("|---|---|---|---|---|---|---|")

    total_rows = 0
    issues: list[str] = []

    for row in coverage_rows:
        source, count, min_d, max_d, span, distinct = row
        total_rows += count
        avg = round(count / span) if span and span > 0 else 0
        min_str = str(min_d) if min_d else "—"
        max_str = str(max_d) if max_d else "—"
        out(f"| {source} | {count:,} | {min_str} | {max_str} | {span or 0} | {distinct} | {avg:,} |")

        if count == 0:
            issues.append(f"**{source}**: Hiç veri yok")
        elif count < 1000:
            issues.append(f"**{source}**: Satır sayısı çok az ({count:,})")
        if span is not None and span < 14 and count > 0:
            issues.append(f"**{source}**: Tarih aralığı < 14 gün ({span} gün)")

    out()
    out(f"**Toplam satır:** {total_rows:,}")
    out()

    # ── Gap Analysis ─────────────────────────────────────────
    out("## 3. Gap Analysis (Eksik Günler)")
    out()

    total_gaps = 0
    for table in aaop_tables:
        full_name = f"aaop_company.{table}"
        try:
            # Get date range
            range_row = conn.execute(f"""
                SELECT MIN(timestamp)::DATE AS mn, MAX(timestamp)::DATE AS mx
                FROM {full_name}
            """).fetchone()

            if not range_row or not range_row[0]:
                continue

            mn, mx = range_row

            # Get all days with data
            daily = conn.execute(f"""
                SELECT timestamp::DATE AS day, COUNT(*) AS cnt
                FROM {full_name}
                GROUP BY timestamp::DATE
                ORDER BY day
            """).fetchall()

            days_with_data = {str(d) for d, _ in daily}

            # Generate all expected days
            import datetime as dt
            current = mn
            missing = []
            while current <= mx:
                if str(current) not in days_with_data:
                    missing.append(str(current))
                current += dt.timedelta(days=1)

            if missing:
                total_gaps += len(missing)
                out(f"### {table}")
                out(f"Missing days ({len(missing)}):")
                # Show first 10
                for d in missing[:10]:
                    out(f"- {d}")
                if len(missing) > 10:
                    out(f"- ... ve {len(missing) - 10} gün daha")
                out()
        except Exception as e:
            out(f"<!-- Gap analysis error for {table}: {e} -->")

    if total_gaps == 0:
        out("**No gaps detected** — tüm kaynaklarda sürekli veri mevcut.")
        out()

    # ── Per-source daily volume stats ────────────────────────
    out("## 4. Daily Volume Statistics (Son 7 Gün)")
    out()

    for table in aaop_tables[:5]:  # Top 5 for brevity
        full_name = f"aaop_company.{table}"
        try:
            recent = conn.execute(f"""
                SELECT timestamp::DATE AS day, COUNT(*) AS cnt
                FROM {full_name}
                WHERE timestamp >= (SELECT MAX(timestamp) - INTERVAL '7 days' FROM {full_name})
                GROUP BY timestamp::DATE
                ORDER BY day DESC
                LIMIT 7
            """).fetchall()

            if recent:
                out(f"**{table}:**")
                for day, cnt in recent:
                    out(f"  {day}: {cnt:,} rows")
                out()
        except Exception:
            pass

    conn.close()

    # ── analytics.duckdb ─────────────────────────────────────
    out("## 5. analytics.duckdb — Table Summary")
    out()

    try:
        aconn = duckdb.connect(ANALYTICS_DB_PATH, read_only=True)
        atables = aconn.execute(
            "SELECT table_schema, table_name "
            "FROM information_schema.tables "
            "WHERE table_schema NOT IN ('information_schema', 'pg_catalog') "
            "ORDER BY table_schema, table_name"
        ).fetchall()

        out("| Schema | Table | Rows |")
        out("|---|---|---|")
        for schema, table in atables:
            try:
                cnt = aconn.execute(f"SELECT COUNT(*) FROM {schema}.{table}").fetchone()[0]
                out(f"| {schema} | {table} | {cnt:,} |")
            except Exception:
                out(f"| {schema} | {table} | ERROR |")
        out()
        aconn.close()
    except Exception as e:
        out(f"analytics.duckdb bağlantı hatası: {e}")
        out()

    # ── Issues ───────────────────────────────────────────────
    out("## 6. Issues Found")
    out()

    if issues:
        for issue in issues:
            out(f"- {issue}")
    else:
        out("No issues found.")
    out()

    return "\n".join(lines)


if __name__ == "__main__":
    report = run_audit()

    # Write to file
    Path(REPORT_PATH).parent.mkdir(parents=True, exist_ok=True)
    Path(REPORT_PATH).write_text(report, encoding="utf-8")
    print(f"\n--- Report written to {REPORT_PATH} ---")
