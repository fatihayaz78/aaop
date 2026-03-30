# DuckDB Data Audit Report v2
Generated: 2026-03-30 07:32:17 UTC

## Schema Summary

| Schema | Tables | Total Rows | Min Date | Max Date | Distinct Days |
|---|---|---|---|---|---|
| sport_stream | 13 | 45,650,663 | 2026-03-04 | 2026-03-31 | 18 |
| tv_plus | 5 | 1,372,000 | 2026-03-03 | 2026-03-30 | 28 |
| music_stream | 5 | 392,000 | 2026-03-03 | 2026-03-30 | 28 |
| fly_ent | 5 | 252,000 | 2026-03-03 | 2026-03-30 | 28 |
| aaop_company | 13 | 45,650,663 | 2026-03-04 | 2026-03-31 | 18 |

## Notes
- sport_stream = aaop_company copy (S-MT-01)
- tv_plus/music_stream/fly_ent seeded by seed_demo_tenants.py (S-MT-03)
- aaop_company preserved for backward compatibility