# knowledge_base.spec.md — Knowledge Base
> Kapsam: M15 Knowledge Base | Sprint: S08-B | Kritiklik: P2
> Not: Arama odaklı UX — dashboard yok, diğer app'lerin RAG kaynağı

## 1. KULLANICI
NOC Operatör, Mühendis — Self-serve runbook arama, geçmiş incident analizi

## 2. TABS (Arama Odaklı)
| Tab | Açıklama |
|---|---|
| Search | Semantik arama (ana ekran) |
| Incidents | Geçmiş incident dökümanları |
| Runbooks | Operasyonel runbook'lar |
| Ingest | Döküman yükleme ve index |

## 3. AGENT MİMARİSİ
```python
class KnowledgeBaseAgent(BaseAgent):
    app_name = "knowledge_base"
    # claude-haiku-4-5-20251001 (hızlı Q&A)
    # ChromaDB collections:
    #   'incidents'  ← ops_center'ın incident kayıtları
    #   'runbooks'   ← manuel yüklenen prosedürler
    #   'platform'   ← kod ve konfigürasyon dökümanları
    # INPUT: incident_created → otomatik index
    # INPUT: rca_completed    → RCA dökümanını index'e ekle
```

## 4. TOOLS
| Tool | Risk | Tetikleyici |
|---|---|---|
| semantic_search | LOW | auto |
| ingest_document | LOW | auto |
| get_related_incidents | LOW | auto |
| get_runbook | LOW | auto |
| delete_document | HIGH | approval_required |

## 5. API
```
prefix: /knowledge
ref:    API_CONTRACTS.md → Bölüm 11
```

## 6. CROSS-APP
```
INPUT (subscribe):
  incident_created ← ops_center → index'e ekle
  rca_completed    ← ops_center → RCA dökümanını ekle
```

## 7. LOKAL VERİ
```
ChromaDB (data/chromadb/):
  collection 'incidents' → incident özetleri + RCA sonuçları
  collection 'runbooks'  → operasyonel prosedürler
  collection 'platform'  → codebase + konfigürasyon

Chunking:        500 token, 50 token overlap
Embedding model: all-MiniLM-L6-v2 (sentence-transformers)
```

## 8. TEST
```bash
pytest apps/knowledge_base/tests/ -v --cov=apps/knowledge_base --cov-fail-under=80
```
Senaryolar: Semantic search ("CDN error rate" → benzer incident) | Auto ingest (incident_created → ChromaDB) | RCA ingest

## Sprint Completion — S08 (2026-03-21)

### Files Created
- `apps/knowledge_base/__init__.py`, `config.py`, `schemas.py`, `prompts.py`, `tools.py`, `agent.py`
- `apps/knowledge_base/tests/` — conftest, test_agent (6), test_tools (11), test_schemas (4), test_config (2)
- `backend/routers/knowledge_base.py` — /knowledge prefix

### Cross-App Wiring
- EventBus subscribes: `incident_created` → auto-index to 'incidents' collection
- EventBus subscribes: `rca_completed` → auto-index RCA to 'incidents' collection

### Hard Constraints Verified
- ✅ ChromaDB collections: 'incidents', 'runbooks', 'platform'
- ✅ Auto-index on EventBus: incident_created → index, rca_completed → index
- ✅ delete_document → approval_required=True
- ✅ Chunking: 500 token, 50 token overlap
- ✅ Embedding: all-MiniLM-L6-v2 (configured in KnowledgeBaseConfig)

### Deviations
- None. All spec constraints met.

---
## Sprint Completion — S22
- Date: Mart 2026
- seed.py: 23 documents (10 incidents, 8 runbooks, 5 platform)
- 5 endpoints (dashboard, search, documents CRUD, delete approval)
- Frontend: 4 tabs
- Tests: 36 passed, 0 failures
- Status: ✅ Complete

### S-KB-09 — 2026-03-28
- frontend/public/kb/ altındaki 11 modül HTML dosyasından NAVIGATION sidebar, FAQ accordion ve Quick Links bölümleri kaldırıldı
- Navigasyon Next.js page.tsx içindeki tab bar üzerinden sağlanıyor
- HTML dosyalar sadece içerik gösteriyor, kendi navigasyon barı yok
