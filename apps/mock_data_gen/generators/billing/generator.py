"""Billing log generator — monthly renewal spikes, calendar-driven cancellations.

Output: billing/YYYY/MM/DD/{YYYY-MM-DD}.jsonl.gz
"""

from __future__ import annotations

import hashlib
import uuid
from datetime import date, datetime, timezone

import structlog

from apps.mock_data_gen.generators.base_generator import BaseGenerator
from apps.mock_data_gen.generators.calendar_events import get_anomaly_for_date

logger = structlog.get_logger(__name__)

PRICE_MAP = {"premium": 299.0, "standard": 149.0, "free": 0.0}
CARD_BRANDS = {"Troy": 0.45, "Mastercard": 0.30, "Visa": 0.20, "Amex": 0.05}
GATEWAYS = {"iyzico": 0.60, "paytr": 0.30, "stripe": 0.10}
FAILURE_REASONS = {
    "insufficient_funds": 0.45, "card_expired": 0.25,
    "bank_reject": 0.20, "fraud_suspect": 0.07, "timeout": 0.03,
}
GATEWAY_CODES = {
    "success": "00", "insufficient_funds": "51",
    "card_expired": "54", "bank_reject": "05", "fraud_suspect": "05",
    "timeout": None,
}
CANCEL_REASONS = ["too_expensive", "competitor", "poor_quality", "not_using"]


class BillingGenerator(BaseGenerator):
    """Generates billing transaction logs."""

    @property
    def source_name(self) -> str:
        return "billing"

    def _pick_weighted(self, options: dict) -> str:
        keys = list(options.keys())
        weights = list(options.values())
        return self.rng.choices(keys, weights=weights, k=1)[0]

    def _make_txn(self, ts: datetime, event_type: str, sub, status: str,
                  failure_reason: str | None = None,
                  prev_tier: str | None = None, new_tier: str | None = None,
                  cancel_reason: str | None = None,
                  retry_count: int = 0, retry_of: str | None = None) -> dict:
        tier = new_tier or sub.tier
        amount = PRICE_MAP.get(tier, 0.0)
        if event_type == "refund":
            amount = -amount
        if event_type in ("cancellation", "trial_end"):
            amount = 0.0

        discount = None
        promo = None
        if event_type == "charge" and self.rng.random() < 0.10:
            discount = self.rng.choice([10, 15, 20, 25])
            promo = f"PROMO{self.rng.randint(100, 999)}"
            amount = round(amount * (1 - discount / 100), 2)

        brand = self._pick_weighted(CARD_BRANDS)
        gateway = self._pick_weighted(GATEWAYS)
        gw_code = GATEWAY_CODES.get(failure_reason, "00") if status != "success" else "00"

        proc_time = self.rng.randint(200, 800)
        if failure_reason == "timeout":
            proc_time = self.rng.randint(5000, 15000)

        sub_id = f"SUB-{hashlib.sha256(sub.user_id.encode()).hexdigest()[:8]}"

        return {
            "transaction_id": f"TXN-{uuid.UUID(int=self.rng.getrandbits(128)).hex[:12]}",
            "event_type": event_type,
            "timestamp": ts.replace(tzinfo=None).isoformat() + "Z",
            "subscriber_id": sub_id,
            "user_id_hash": hashlib.sha256(sub.user_id.encode()).hexdigest()[:32],
            "subscription_tier": sub.tier,
            "payment_cycle": self.rng.choices(["monthly", "annual"], weights=[0.75, 0.25], k=1)[0],
            "amount_tl": amount,
            "currency": "TRY",
            "discount_pct": discount,
            "promo_code": promo,
            "payment_method": "credit_card",
            "card_last4": f"{self.rng.randint(1000, 9999)}",
            "card_brand": brand,
            "payment_gateway": gateway,
            "status": status,
            "failure_reason": failure_reason,
            "gateway_response_code": gw_code,
            "retry_count": retry_count,
            "retry_of": retry_of,
            "processing_time_ms": proc_time,
            "previous_tier": prev_tier,
            "new_tier": new_tier,
            "effective_date": ts.replace(tzinfo=None).isoformat() + "Z" if prev_tier or cancel_reason else None,
            "cancellation_reason": cancel_reason,
        }

    def generate_day(self, target_date: date) -> int:
        """Generate billing transactions for a single day."""
        anomaly = get_anomaly_for_date(target_date)
        pool = self.subscriber_pool

        # Monthly renewal spike: days 1-5
        is_renewal_window = target_date.day <= 5
        base_volume = 85_000 if is_renewal_window else 2_000

        # Holiday: higher failure rate
        is_holiday = anomaly == "holiday"
        fail_rate = 0.08 if is_holiday else 0.035

        # Calendar effects
        is_cdn_outage_aftermath = (target_date == date(2026, 3, 1))
        is_elclasico_aftermath = (target_date == date(2026, 3, 5))

        records: list[dict] = []

        # Regular charges
        num_charges = min(base_volume, len(pool))
        for i in range(num_charges):
            sub = pool[self.rng.randint(0, len(pool) - 1)]
            if sub.tier == "free":
                continue

            sec = self.rng.randint(0, 86399)
            hour = sec // 3600
            minute = (sec % 3600) // 60
            second = sec % 60
            ts = datetime(
                target_date.year, target_date.month, target_date.day,
                hour, minute, second, tzinfo=timezone.utc,
            )

            if self.rng.random() < fail_rate:
                reason = self._pick_weighted(FAILURE_REASONS)
                records.append(self._make_txn(ts, "charge", sub, "failed", failure_reason=reason))
            else:
                records.append(self._make_txn(ts, "charge", sub, "success"))

        # Cancellations
        num_cancellations = 20  # base daily
        if is_cdn_outage_aftermath:
            num_cancellations += 120
        if is_elclasico_aftermath:
            num_cancellations += 80

        for _ in range(num_cancellations):
            sub = pool[self.rng.randint(0, len(pool) - 1)]
            sec = self.rng.randint(0, 86399)
            ts = datetime(
                target_date.year, target_date.month, target_date.day,
                sec // 3600, (sec % 3600) // 60, sec % 60, tzinfo=timezone.utc,
            )
            reason = "poor_quality" if is_cdn_outage_aftermath else self.rng.choice(CANCEL_REASONS)
            records.append(self._make_txn(
                ts, "cancellation", sub, "success",
                cancel_reason=reason, prev_tier=sub.tier, new_tier="free",
            ))

        # Downgrades after ElClasico
        if is_elclasico_aftermath:
            for _ in range(80):
                sub = pool[self.rng.randint(0, len(pool) - 1)]
                if sub.tier != "standard":
                    continue
                sec = self.rng.randint(0, 86399)
                ts = datetime(
                    target_date.year, target_date.month, target_date.day,
                    sec // 3600, (sec % 3600) // 60, sec % 60, tzinfo=timezone.utc,
                )
                records.append(self._make_txn(
                    ts, "downgrade", sub, "success",
                    prev_tier="standard", new_tier="free",
                ))

        # Sort and write
        records.sort(key=lambda r: r["timestamp"])
        self.write_jsonl_gz(
            records,
            target_date.strftime("%Y"),
            target_date.strftime("%m"),
            target_date.strftime("%d"),
            filename=f"{target_date.isoformat()}.jsonl.gz",
        )

        logger.info("billing_day_complete", date=target_date.isoformat(), records=len(records))
        return len(records)


if __name__ == "__main__":
    BillingGenerator().generate_all()
