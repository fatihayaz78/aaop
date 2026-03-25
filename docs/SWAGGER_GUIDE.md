# AAOP API — Swagger Guide

## Access
- Local Swagger UI: http://localhost:8000/docs
- ReDoc: http://localhost:8000/redoc
- OpenAPI JSON: http://localhost:8000/openapi.json
- Static spec: docs/openapi.json

## Authentication
All endpoints require JWT Bearer token.
Login: POST /auth/login → returns access_token
Header: Authorization: Bearer {access_token}
Tenant: X-Tenant-ID header (required on all app endpoints)

## Apps & Prefixes (106 endpoints total)
| App | Prefix | Endpoints | Module(s) |
|-----|--------|-----------|-----------|
| Ops Center | /ops | 8 | M01 + M06 |
| Log Analyzer | /log-analyzer | 41 | M07 |
| Alert Center | /alerts | 11 | M13 |
| Viewer Experience | /viewer | 7 | M02 + M09 |
| Live Intelligence | /live | 7 | M05 + M11 |
| Growth & Retention | /growth | 6 | M18 + M03 |
| Capacity & Cost | /capacity | 6 | M16 + M04 |
| Admin & Governance | /admin | 9 | M12 + M17 |
| AI Lab | /ai-lab | 7 | M10 + M14 |
| Knowledge Base | /knowledge | 6 | M15 |
| DevOps Assistant | /devops | 5 | M08 |

## WebSocket Endpoints
| App | WebSocket URL |
|-----|--------------|
| Ops Center | ws://localhost:8000/ws/ops/incidents |
| Alert Center | ws://localhost:8000/ws/alerts/stream |
| Viewer Experience | ws://localhost:8000/ws/viewer/qoe |

## Risk Levels
Tools are tagged LOW / MEDIUM / HIGH.
HIGH risk tools return {approval_required: true} — manual approval needed.

## Chat Endpoints (Captain logAR)
| App | Endpoint | Description |
|-----|----------|-------------|
| Log Analyzer | POST /log-analyzer/chat | CDN analysis context |
| Ops Center | POST /ops/chat | Incident context |
| DevOps Assistant | POST /devops/chat | Runbook RAG + danger detection |

## Health Check
GET /health → {status, version}
GET /health/detailed → {sqlite, duckdb, redis, chromadb, llm_gateway}
Each app: GET /{prefix}/health

## Platform Stats
- 11 apps, 54 frontend tabs
- 659 tests, 0 failures
- Python 3.12, FastAPI, Next.js 14
