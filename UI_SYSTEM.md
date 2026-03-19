# UI_SYSTEM.md — AAOP Design System
> Claude Code bu dosyayı UI sprint'lerinde okur.
> Next.js 14 + Tailwind + shadcn/ui + Recharts
> Versiyon: 2.0 | Mart 2026

---

## 1. TASARIM İLKELERİ

```
Dark-mode FIRST    → tüm renkler dark mode için tasarlanır, light mode secondary
OTT-native         → NOC ekranı estetiği, veri yoğun, kompakt
Captain logAR      → marka kimliği: deniz mavi + kırmızı aksan
```

---

## 2. RENK PALETİ (CSS Custom Properties)

```css
/* globals.css — :root dark */
--background:        #0d1117;   /* Deep space */
--background-card:   #161b22;   /* Card surfaces */
--background-hover:  #21262d;   /* Hover state */
--border:            #30363d;   /* Borders */
--text-primary:      #e6edf3;   /* Primary text */
--text-secondary:    #8b949e;   /* Secondary text */
--text-muted:        #484f58;   /* Muted / placeholder */

/* Brand */
--brand-primary:     #1f6feb;   /* Captain logAR mavi */
--brand-accent:      #e94560;   /* Kırmızı aksan */
--brand-glow:        rgba(31, 111, 235, 0.15); /* Glow effect */

/* Severity / Risk */
--risk-low:          #238636;   /* Yeşil — LOW / güvenli */
--risk-low-bg:       rgba(35, 134, 54, 0.15);
--risk-medium:       #d29922;   /* Sarı — MEDIUM / dikkat */
--risk-medium-bg:    rgba(210, 153, 34, 0.15);
--risk-high:         #da3633;   /* Kırmızı — HIGH / kritik */
--risk-high-bg:      rgba(218, 54, 51, 0.15);

/* Status */
--status-active:     #238636;
--status-warning:    #d29922;
--status-error:      #da3633;
--status-inactive:   #484f58;
```

---

## 3. TYPOGRAFİ

```css
/* layout.tsx font import */
--font-sans: 'Inter', system-ui, sans-serif;
--font-mono: 'JetBrains Mono', 'Fira Code', monospace;

/* Ölçek */
--text-xs:   0.75rem;   /* 12px — meta bilgi, badge */
--text-sm:   0.875rem;  /* 14px — tablo satırı, etiket */
--text-base: 1rem;      /* 16px — body */
--text-lg:   1.125rem;  /* 18px — section başlık */
--text-xl:   1.25rem;   /* 20px — card başlık */
--text-2xl:  1.5rem;    /* 24px — sayfa başlık */
--text-3xl:  1.875rem;  /* 30px — dashboard stat */
```

---

## 4. LAYOUT YAPISI

```
┌─────────────────────────────────────────────────────────┐
│  HEADER (64px) — Logo + Tenant selector + User menu      │
├────────────────┬────────────────────────────────────────┤
│                │  BREADCRUMB (40px)                      │
│  SIDEBAR       ├────────────────────────────────────────┤
│  240px         │  PAGE CONTENT (flex, scroll)            │
│  (collapsible  │                                         │
│   → 64px icon) │                                         │
│                ├────────────────────────────────────────┤
│  11 app        │  AI CHAT PANEL (collapsible, 380px)     │
│  grouped by    │  Sağ alt köşe — her sayfada var         │
│  priority      │                                         │
└────────────────┴────────────────────────────────────────┘
```

### Sidebar Grupları

```
P0 — Kritik
  📡 Ops Center
  🔍 Log Analyzer
  🔔 Alert Center

P1 — İş
  👁️ Viewer Experience
  ⚡ Live Intelligence
  📈 Growth & Retention
  ⚙️ Capacity & Cost
  🛡️ Admin & Governance

P2 — Gelecek
  🧪 AI Lab
  📚 Knowledge Base
  🤖 DevOps Assistant
```

---

## 5. COMPONENT KURALLARI

### Risk Badge
```tsx
// components/ui/risk-badge.tsx
type RiskLevel = 'LOW' | 'MEDIUM' | 'HIGH'

// LOW    → yeşil bg + yeşil text + "● AUTO"
// MEDIUM → sarı bg + sarı text + "● AUTO+NOTIFY"
// HIGH   → kırmızı bg + kırmızı text + "● ONAY GEREKLİ"
```

### Metric Card
```tsx
// components/ui/metric-card.tsx
// Props: title, value, delta, trend ('up'|'down'|'flat'), unit
// Delta pozitif → yeşil | negatif → kırmızı | flat → gri
```

### Agent Chat Panel
```tsx
// components/agent-chat/index.tsx
// Her sayfanın sağ alt köşesinde sabit
// Collapse: sağa kayar, icon kalır
// Her app kendi system prompt'unu inject eder
// WebSocket (Socket.IO) ile streaming response
// Model göstergesi: Haiku/Sonnet/Opus chip
```

### Log Table
```tsx
// components/ui/log-table.tsx
// Virtualized (react-virtual) — büyük log setleri için
// Kolon: timestamp | level | service | tenant | message
// Filtreler: level, tenant, time range
// Export: CSV butonu
```

### Recharts Wrapper Kuralları
```tsx
// components/charts/ altındaki tüm grafikler:
// - ResponsiveContainer → her zaman
// - dark theme colors → CSS var kullan
// - Tooltip: CustomTooltip component ile
// - Animation: false (performans için)
```

---

## 6. NEXT.JS KURALLARI

```
App Router        → src/app/ altında tüm sayfalar
Server Components → varsayılan (async/await veri çekme)
Client Components → "use client" sadece interaktif bileşenler
                    (charts, websocket, form, agent-chat)
Route groups      → (apps) grubu: sidebar layout paylaşır
Loading states    → her route'ta loading.tsx
Error handling    → her route'ta error.tsx
TypeScript        → strict: true, noImplicitAny: true
```

### API Çağrı Paterni
```typescript
// lib/api.ts
const BASE_URL = process.env.NEXT_PUBLIC_API_URL ?? 'http://localhost:8000'

export async function apiGet<T>(path: string, tenantId: string): Promise<T> {
  const res = await fetch(`${BASE_URL}${path}`, {
    headers: {
      'Authorization': `Bearer ${getToken()}`,
      'X-Tenant-ID': tenantId,
    },
    next: { revalidate: 30 }, // ISR: 30 saniye cache
  })
  if (!res.ok) throw new Error(await res.text())
  return res.json()
}
```

---

## 7. shadcn/ui KULLANIM KURALLARI

```
Kurulum: npx shadcn@latest init (dark mode, zinc base)
Import:  @/components/ui/{component}
Özelleştirme: components/ui/ altında extend et — kütüphane dosyasını değiştirme
Kullanılan: Button, Card, Badge, Dialog, Sheet, Tabs, Table,
            Input, Select, Textarea, Separator, Skeleton, Toast
```

---

## 8. CAPTAIN LOGAR LOGO KURALLARI

```
Dosya:   public/captain-logar.png
Login:   220px genişlik, ortada
Sidebar: 180px (expanded) | 40px (collapsed — sadece ikon)
Header:  32px yükseklik
Favicon: 32x32 crop
Beyaz arka plan gerekmez — logo transparan PNG
```
