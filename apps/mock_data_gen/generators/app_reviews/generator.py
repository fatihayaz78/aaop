"""App Reviews generator — store ratings with calendar-driven spikes.

Output: app_reviews/YYYY/MM/{YYYY-MM-DD}.json
"""

from __future__ import annotations

import uuid
from datetime import date, datetime, timedelta, timezone

import structlog

from apps.mock_data_gen.generators.base_generator import BaseGenerator
from apps.mock_data_gen.generators.calendar_events import get_anomaly_for_date

logger = structlog.get_logger(__name__)

# Rating distributions by context
RATINGS_NORMAL = {5: 0.45, 4: 0.25, 3: 0.12, 2: 0.08, 1: 0.10}
RATINGS_CDN_OUTAGE = {1: 0.65, 2: 0.15, 3: 0.10, 4: 0.05, 5: 0.05}
RATINGS_ELCLASICO = {1: 0.45, 2: 0.20, 3: 0.15, 4: 0.10, 5: 0.10}
RATINGS_FAIRPLAY = {1: 0.80, 2: 0.12, 3: 0.05, 4: 0.02, 5: 0.01}
RATINGS_HOLIDAY = {5: 0.55, 4: 0.28, 3: 0.10, 2: 0.04, 1: 0.03}

# Turkish review templates by category and sentiment
REVIEW_BODIES: dict[str, list[tuple[str, str, str]]] = {
    # (body, sentiment, category)
    "positive": [
        ("Harika uygulama, akıcı izliyorum", "positive", "content"),
        ("La Liga maçlarını çok iyi yayınlıyor, kaliteli görüntü", "positive", "content"),
        ("Arayüz çok güzel, kullanımı kolay", "positive", "ui"),
        ("Maç bildirimleri harika çalışıyor, hiç kaçırmıyorum", "positive", "other"),
        ("Canlı yayın kalitesi mükemmel, donma yok", "positive", "content"),
        ("Premium abonelik her kuruşuna değer", "positive", "payment"),
        ("EuroLeague maçlarını izlemek için en iyi uygulama", "positive", "content"),
        ("Çok memnunum, tavsiye ederim", "positive", "other"),
    ],
    "negative_buffering": [
        ("Maç izlerken sürekli takılıyor, berbat", "negative", "buffering"),
        ("Canlı yayında donma sorunu var, izlenmiyor", "negative", "buffering"),
        ("Buffer sorunu çözülmedi, her maçta aynı", "negative", "buffering"),
        ("İnternet hızım iyi olmasına rağmen sürekli buffer yapıyor", "negative", "buffering"),
        ("Maçın en kritik anında donuyor, sinir bozucu", "negative", "buffering"),
    ],
    "negative_buffering_elclasico": [
        ("El Clasico'da çok kötüydü, sürekli dondu", "negative", "buffering"),
        ("Büyük maçlarda rezalet performans, El Clasico izlenemedi", "negative", "buffering"),
        ("El Clasico için premium aldım ama izleyemedim, para iadesi istiyorum", "negative", "buffering"),
    ],
    "negative_drm": [
        ("iPhone'da açılmıyor, DRM hatası veriyor", "negative", "drm"),
        ("FairPlay hatası, iOS'ta yayın başlamıyor", "negative", "drm"),
        ("Apple TV'de lisans hatası, hiçbir içerik oynatılmıyor", "negative", "drm"),
        ("DRM sorunu devam ediyor, ne zaman düzelecek?", "negative", "drm"),
    ],
    "negative_login": [
        ("Sürekli oturumu kapatıyor, çok sinir bozucu", "negative", "login"),
        ("Her seferinde tekrar giriş yapmam gerekiyor", "negative", "login"),
        ("Token süresi çok kısa, sürekli yeniden login", "negative", "login"),
    ],
    "negative_crash": [
        ("Uygulama sürekli çöküyor, kullanılamaz durumda", "negative", "crash"),
        ("Maç ortasında kapanıyor, düzeltin artık", "negative", "crash"),
    ],
    "negative_payment": [
        ("Ödeme aldınız ama yayın yok, dolandırıcılık", "negative", "payment"),
        ("İptal etmeme rağmen ücret kesildi", "negative", "payment"),
    ],
    "neutral": [
        ("Fena değil ama geliştirilebilir", "neutral", "other"),
        ("Ortalama bir uygulama, bazı sorunlar var", "neutral", "other"),
        ("Bazen iyi bazen kötü, tutarlı değil", "neutral", "buffering"),
    ],
    "negative_cdn_outage": [
        ("Yayın tamamen çöktü, saatlerce izleyemedik", "negative", "buffering"),
        ("CDN sorunu yüzünden maçı kaçırdım, rezalet", "negative", "buffering"),
        ("Sunucu çökmesi kabul edilemez, para iadesi!", "negative", "crash"),
        ("Tam maç saatinde sistem çöktü, utanç verici", "negative", "buffering"),
        ("503 hatası alıyorum, ne zaman düzelecek?", "negative", "crash"),
    ],
}

REVIEW_TITLES: dict[str, list[str]] = {
    "positive": ["Harika!", "Mükemmel uygulama", "Çok memnunum", "Tavsiye ederim", "5 yıldız hak ediyor"],
    "negative": ["Berbat", "Çok kötü", "Düzeltin artık", "Para iadesi istiyorum", "Kullanılmaz"],
    "neutral": ["İdare eder", "Fena değil", "Geliştirilebilir"],
}

ANDROID_MODELS = ["Samsung Galaxy S24", "Samsung Galaxy A54", "Xiaomi 13", "Google Pixel 8", "OnePlus 12"]
IOS_MODELS = ["iPhone 15 Pro", "iPhone 14", "iPhone 13", "iPad Air", "iPad Pro"]
ANDROID_VERSIONS = ["Android 13", "Android 14"]
IOS_VERSIONS = ["iOS 17.2", "iOS 17.1", "iOS 16.7"]
APP_VERSIONS = ["4.2.1", "4.2.0", "4.1.9"]

DEV_RESPONSES = [
    "Merhaba, geri bildiriminiz için teşekkürler. Ekibimiz sorunu inceliyor.",
    "Yaşadığınız sorun için özür dileriz. Güncellemede düzeltilecektir.",
    "Değerli geri bildiriminiz için teşekkürler. Deneyiminizi iyileştirmek için çalışıyoruz.",
]


class AppReviewsGenerator(BaseGenerator):
    """Generates app store reviews with calendar-driven spikes."""

    @property
    def source_name(self) -> str:
        return "app_reviews"

    def _pick_weighted_int(self, options: dict[int, float]) -> int:
        keys = list(options.keys())
        weights = list(options.values())
        return self.rng.choices(keys, weights=weights, k=1)[0]

    def _get_context(self, target_date: date) -> tuple[str | None, dict[int, float], int, int]:
        """Return (event_trigger, rating_dist, volume_lo, volume_hi)."""
        anomaly = get_anomaly_for_date(target_date)
        multiplier = self.get_multiplier(target_date)

        if anomaly == "cdn_outage":
            return "cdn_outage", RATINGS_CDN_OUTAGE, 250, 300
        if anomaly == "peak_event":
            return "elclasico", RATINGS_ELCLASICO, 400, 500
        if anomaly == "fairplay_cert_expired":
            return "fairplay_issue", RATINGS_FAIRPLAY, 160, 200
        if anomaly == "holiday":
            return "normal", RATINGS_HOLIDAY, 8, 12
        if multiplier >= 2.0:
            return "normal", RATINGS_NORMAL, 60, 100
        return "normal", RATINGS_NORMAL, 15, 30

    def _pick_review_content(self, rating: int, event: str | None,
                             platform: str) -> tuple[str, str | None, str, str, list[str]]:
        """Return (body, title, sentiment, category, topics)."""
        if rating >= 4:
            tmpl = self.rng.choice(REVIEW_BODIES["positive"])
            title = self.rng.choice(REVIEW_TITLES["positive"]) if self.rng.random() < 0.6 else None
            return tmpl[0], title, tmpl[1], tmpl[2], [tmpl[2], "live_sport"]

        if rating == 3:
            tmpl = self.rng.choice(REVIEW_BODIES["neutral"])
            title = self.rng.choice(REVIEW_TITLES["neutral"]) if self.rng.random() < 0.4 else None
            return tmpl[0], title, tmpl[1], tmpl[2], [tmpl[2]]

        # Negative (1-2 stars)
        title = self.rng.choice(REVIEW_TITLES["negative"]) if self.rng.random() < 0.7 else None

        if event == "cdn_outage":
            tmpl = self.rng.choice(REVIEW_BODIES["negative_cdn_outage"])
            return tmpl[0], title, tmpl[1], tmpl[2], [tmpl[2], "cdn", "outage"]

        if event == "fairplay_issue" and platform == "ios":
            tmpl = self.rng.choice(REVIEW_BODIES["negative_drm"])
            return tmpl[0], title, tmpl[1], tmpl[2], [tmpl[2], "ios", "fairplay"]

        if event == "elclasico":
            tmpl = self.rng.choice(REVIEW_BODIES["negative_buffering_elclasico"])
            return tmpl[0], title, tmpl[1], tmpl[2], [tmpl[2], "elclasico", "live_sport"]

        # Generic negative
        pool = (
            REVIEW_BODIES["negative_buffering"]
            + REVIEW_BODIES["negative_login"]
            + REVIEW_BODIES["negative_crash"]
            + REVIEW_BODIES["negative_payment"]
        )
        tmpl = self.rng.choice(pool)
        return tmpl[0], title, tmpl[1], tmpl[2], [tmpl[2]]

    def generate_day(self, target_date: date) -> int:
        """Generate app reviews for a single day."""
        event, rating_dist, vol_lo, vol_hi = self._get_context(target_date)
        num_reviews = self.rng.randint(vol_lo, vol_hi)
        records: list[dict] = []

        for _ in range(num_reviews):
            platform = self.rng.choices(["android", "ios"], weights=[0.60, 0.40], k=1)[0]

            # FairPlay day: ios reviews use fairplay ratings
            if event == "fairplay_issue" and platform == "ios":
                rating = self._pick_weighted_int(RATINGS_FAIRPLAY)
            else:
                rating = self._pick_weighted_int(rating_dist)

            body, title, sentiment, category, topics = self._pick_review_content(
                rating, event, platform,
            )

            # FairPlay: ios → drm category dominant
            if event == "fairplay_issue" and platform == "ios" and rating <= 2:
                category = "drm"
                topics = ["drm", "ios", "fairplay"]

            if platform == "android":
                model = self.rng.choice(ANDROID_MODELS)
                os_ver = self.rng.choice(ANDROID_VERSIONS)
            else:
                model = self.rng.choice(IOS_MODELS)
                os_ver = self.rng.choice(IOS_VERSIONS)

            sec = self.rng.randint(0, 86399)
            ts = datetime(
                target_date.year, target_date.month, target_date.day,
                sec // 3600, (sec % 3600) // 60, sec % 60, tzinfo=timezone.utc,
            )

            # Developer response for negative reviews
            dev_response = False
            dev_text = None
            dev_at = None
            response_rate = 0.35 if event in ("cdn_outage", "fairplay_issue") else 0.15
            if rating <= 2 and self.rng.random() < response_rate:
                dev_response = True
                dev_text = self.rng.choice(DEV_RESPONSES)
                dev_at = (ts + timedelta(hours=self.rng.randint(2, 48))).replace(tzinfo=None).isoformat() + "Z"

            country = self.rng.choices(["TR", "DE", "GB"], weights=[0.94, 0.03, 0.03], k=1)[0]
            lang = "tr" if country == "TR" else "en"

            records.append({
                "review_id": f"REV-{uuid.UUID(int=self.rng.getrandbits(128)).hex[:12]}",
                "platform": platform,
                "timestamp": ts.replace(tzinfo=None).isoformat() + "Z",
                "app_version": self.rng.choice(APP_VERSIONS),
                "device_model": model,
                "os_version": os_ver,
                "country": country,
                "language": lang,
                "rating": rating,
                "title": title,
                "body": body,
                "sentiment": sentiment,
                "category": category,
                "topics": topics,
                "language_detected": lang,
                "developer_response": dev_response,
                "developer_response_text": dev_text,
                "developer_response_at": dev_at,
                "triggered_by_event": event,
            })

        records.sort(key=lambda r: r["timestamp"])

        self.write_json(
            records,
            target_date.strftime("%Y"),
            target_date.strftime("%m"),
            filename=f"{target_date.isoformat()}.json",
        )

        logger.info("reviews_day_complete", date=target_date.isoformat(), reviews=len(records))
        return len(records)


if __name__ == "__main__":
    AppReviewsGenerator().generate_all()
