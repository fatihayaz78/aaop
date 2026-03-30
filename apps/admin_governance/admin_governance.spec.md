# admin_governance.spec.md — Admin & Governance
> Kapsam: M12 Tenant Self-Service + M17 Compliance Dashboard | Sprint: S08-D | Kritiklik: P1

## 1. KULLANICI
Platform Yöneticisi, Compliance Sorumlusu — Tenant yönetimi, modül konfig, audit, uyumluluk

## 2. TABS
| Tab | Açıklama |
|---|---|
| Tenants | Tenant listesi, oluştur/düzenle |
| Module Config | Tenant bazlı modül açma/kapama |
| API Keys | LLM ve external API key yönetimi |
| Audit Log | Tüm platform aksiyonları audit trail |
| Compliance | Uyumluluk raporu ve ihlaller |
| Usage Stats | Token kullanımı, karar istatistikleri |

## 3. AGENT MİMARİSİ
```python
class TenantAgent(BaseAgent):
    app_name = "admin_governance"
    # claude-haiku-4-5-20251001 (yönetimsel işlemler)
    # Sadece platform admin rolü erişebilir

class ComplianceAgent(BaseAgent):
    app_name = "admin_governance"
    # claude-sonnet-4-20250514
    # agent_decisions tablosunu tarar
    # HIGH risk tool approval pattern analizi
    # Haftalık compliance raporu (APScheduler)
```

## 4. TOOLS
| Tool | Risk | Tetikleyici |
|---|---|---|
| list_tenants | LOW | auto |
| get_module_configs | LOW | auto |
| get_audit_log | LOW | auto |
| get_usage_stats | LOW | auto |
| generate_compliance_report | LOW | auto |
| create_tenant | MEDIUM | auto+notify |
| update_module_config | MEDIUM | auto+notify |
| rotate_api_key | HIGH | approval_required |
| delete_tenant | HIGH | approval_required |
| export_audit_log | HIGH | approval_required |

## 5. API
```
prefix: /admin
ref:    API_CONTRACTS.md → Bölüm 10
```

## 6. CROSS-APP
```
DuckDB OKUMA: shared_analytics.agent_decisions (compliance)
              shared_analytics.alerts_sent (istatistik)
              (tüm shared_analytics — admin yetkisi)
```

## 7. LOKAL VERİ
SQLite tabloları: tenants, users, module_configs, audit_log → DATA_FLOW.md → Bölüm 3

### API Key Güvenliği
```
SQLite'ta AES-256 ile şifreli sakla
Key = JWT_SECRET_KEY'den türetilir
Response'da asla tam key dönme → masked: sk-ant-...XXXX
```

## 8. GÜVENLİK
```
Admin endpoint'leri: sadece 'admin' JWT claim
Tenant izolasyonu: kullanıcı sadece kendi tenant'ını görür
Her aksiyon (başarılı + başarısız) audit_log'a yazılır
```

## 9. TEST
```bash
pytest apps/admin_governance/tests/ -v --cov=apps/admin_governance --cov-fail-under=80
```
Senaryolar: Tenant CRUD | Module config toggle | Compliance tarama | Audit trail doğrulama

## Sprint Completion — S08 (2026-03-21)

### Files Created
- `apps/admin_governance/__init__.py`, `config.py`, `schemas.py`, `prompts.py`, `tools.py`, `agent.py`
- `apps/admin_governance/tests/` — conftest, test_agent (10), test_tools (14), test_schemas (10), test_config (2)
- `backend/routers/admin_governance.py` — /admin prefix

### Hard Constraints Verified
- ✅ TenantAgent AND ComplianceAgent both implemented
- ✅ delete_tenant → approval_required=True
- ✅ rotate_api_key → approval_required=True
- ✅ export_audit_log → approval_required=True
- ✅ API keys stored encrypted (SHA256 derived from JWT secret)
- ✅ Response never returns full API key — masked only (sk-ant-...XXXX)
- ✅ Every action (success + fail) written to audit_log
- ✅ Admin endpoints: 'admin' JWT role claim required (TenantAgent checks role)

### Deviations
- None. All spec constraints met.

---
## Sprint Completion — S21
- Date: Mart 2026
- seed.py: 3 tenants + module configs + 50 audit entries + 200 token usage rows
- 7 endpoints (dashboard, tenants, modules, audit, compliance, usage)
- Frontend: 6 tabs
- Tests: 54 passed, 0 failures
- Status: ✅ Complete

---
## Sprint Progress — S-DI-01 + S-DI-04 (2026-03-28)
### Data Sources Tab + logs.duckdb Entegrasyonu
- Admin & Governance'a "Data Sources" tab eklendi (shared/ingest/ ile)
- GET /admin/dashboard: data_source_stats (tüm logs.duckdb tabloları row count)
- DuckDB OKUMA: logs.duckdb aaop_company schema (tüm tablolar, metadata only)

---
## Sprint Completion — S-AGENT-04

- Date: 2026-03-29
- Tests: 10 passed (agent), 148 passed (platform), 0 failure
- TenantAgent: BaseAgent 4-adım döngüsü aktif (admin role check)
- ComplianceAgent: BaseAgent 4-adım döngüsü aktif (violation detection)
- Deviations: None

---
## Sprint Progress — S-MT-01..04 (Mart–Nisan 2026)

### S-MT-01: Multi-Tenant Core Data Model
- SQLite: `tenants` tablosu (id, name, sector, status)
- SQLite: `services` tablosu (id, tenant_id, name, duckdb_schema)
- SQLite: `users` tablosu genişletildi (role, service_ids, active_service_id)
- DuckDB: `sport_stream` schema oluşturuldu

### S-MT-02: Auth Layer
- Eski test tenant kayıtları temizlendi
- JWT payload genişletildi (service_ids, active_service_id, role)
- 3 yeni endpoint: /auth/login (update), /auth/switch-service, /auth/tenants
- 5 demo kullanıcı seed edildi

### S-MT-03: Demo Data
- 3 yeni DuckDB schema: tv_plus (1.37M), music_stream (392K), fly_ent (252K)

### S-MT-04: Service Switcher UI
- AuthContext.tsx: service state yönetimi
- ServiceSwitcher.tsx: role-based dropdown (3 farklı görünüm)
- /admin-governance/tenants sayfası (super_admin only)
- GET /api/admin/platform/tenants endpoint'i

### Kullanıcı Rolleri

| Rol | Kapsam | Yetki |
|---|---|---|
| super_admin | Platform | Tüm tenant + service |
| tenant_admin | Tenant | Kendi tenant'ının tüm service'leri |
| service_user | Service | Sadece atanmış service(ler) |

- Tests: 148 passed, 0 failure
