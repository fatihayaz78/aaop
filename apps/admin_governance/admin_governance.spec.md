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
