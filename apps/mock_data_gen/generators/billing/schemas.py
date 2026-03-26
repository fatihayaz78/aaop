"""Billing log schema — 8 event types, payment tracking."""

from __future__ import annotations

from pydantic import BaseModel


class BillingLogEntry(BaseModel):
    """Billing transaction log entry."""

    # ── META ──
    transaction_id: str  # TXN-{12hex}
    event_type: str  # charge | refund | retry | chargeback | trial_end | upgrade | downgrade | cancellation
    timestamp: str  # ISO 8601

    # ── ABONE ──
    subscriber_id: str  # matches CRM subscriber_id
    user_id_hash: str  # SHA256
    subscription_tier: str
    payment_cycle: str  # monthly | annual

    # ── TUTAR ──
    amount_tl: float
    currency: str  # TRY
    discount_pct: float | None = None
    promo_code: str | None = None

    # ── ÖDEME ──
    payment_method: str
    card_last4: str | None = None
    card_brand: str | None = None  # Visa | Mastercard | Troy | Amex
    payment_gateway: str  # iyzico | stripe | paytr

    # ── SONUÇ ──
    status: str  # success | failed | pending | refunded | disputed
    failure_reason: str | None = None
    gateway_response_code: str | None = None  # 00 | 51 | 54 | 05
    retry_count: int = 0
    retry_of: str | None = None  # transaction_id of original
    processing_time_ms: int

    # ── ABONELİK DEĞİŞİKLİĞİ ──
    previous_tier: str | None = None
    new_tier: str | None = None
    effective_date: str | None = None
    cancellation_reason: str | None = None


FIELD_CATEGORIES: dict[str, str] = {
    "transaction_id": "meta", "event_type": "meta", "timestamp": "meta",
    "subscriber_id": "subscriber", "user_id_hash": "subscriber",
    "subscription_tier": "subscriber", "payment_cycle": "subscriber",
    "amount_tl": "amount", "currency": "amount",
    "discount_pct": "amount", "promo_code": "amount",
    "payment_method": "payment", "card_last4": "payment",
    "card_brand": "payment", "payment_gateway": "payment",
    "status": "result", "failure_reason": "result",
    "gateway_response_code": "result", "retry_count": "result",
    "retry_of": "result", "processing_time_ms": "result",
    "previous_tier": "subscription_change", "new_tier": "subscription_change",
    "effective_date": "subscription_change", "cancellation_reason": "subscription_change",
}

FIELD_DESCRIPTIONS: dict[str, str] = {
    "transaction_id": "Unique transaction ID (TXN-{12hex})",
    "event_type": "Transaction type (charge/refund/retry/chargeback/trial_end/upgrade/downgrade/cancellation)",
    "timestamp": "Transaction timestamp in ISO 8601",
    "subscriber_id": "Subscriber ID (matches CRM)",
    "user_id_hash": "User identifier (SHA256 hashed)",
    "subscription_tier": "Current subscription tier",
    "payment_cycle": "Billing cycle (monthly/annual)",
    "amount_tl": "Transaction amount in Turkish Lira",
    "currency": "Currency code (TRY)",
    "discount_pct": "Applied discount percentage",
    "promo_code": "Promotional code applied",
    "payment_method": "Payment method type",
    "card_last4": "Last 4 digits of payment card",
    "card_brand": "Card brand (Visa/Mastercard/Troy/Amex)",
    "payment_gateway": "Payment processor (iyzico/stripe/paytr)",
    "status": "Transaction status (success/failed/pending/refunded/disputed)",
    "failure_reason": "Reason for payment failure",
    "gateway_response_code": "Payment gateway response code",
    "retry_count": "Number of retry attempts",
    "retry_of": "Original transaction ID (for retries)",
    "processing_time_ms": "Payment processing time in milliseconds",
    "previous_tier": "Previous subscription tier (for changes)",
    "new_tier": "New subscription tier (for changes)",
    "effective_date": "When the subscription change takes effect",
    "cancellation_reason": "Reason for cancellation",
}
