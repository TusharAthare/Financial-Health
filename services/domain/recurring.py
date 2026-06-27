"""Pure recurring/autopay/EMI detection heuristics."""

from dataclasses import dataclass
from datetime import date, timedelta
from decimal import Decimal
from statistics import mean, pstdev
from typing import Any


EMI_KEYWORDS = frozenset(
    {
        "emi",
        "loan",
        "nach",
        "mortgage",
        "hdfc ltd",
        "bajaj finance",
        "home loan",
        "personal loan",
        "auto debit",
        "autopay",
        "mandate",
    }
)

SUBSCRIPTION_KEYWORDS = frozenset(
    {
        "netflix",
        "spotify",
        "amazon prime",
        "hotstar",
        "youtube",
        "subscription",
        "membership",
    }
)

CADENCE_TARGETS = {
    "weekly": 7,
    "biweekly": 14,
    "monthly": 30,
    "quarterly": 90,
}


@dataclass(frozen=True)
class TransactionSnapshot:
    """Minimal transaction data for recurring detection."""

    id: int
    transaction_date: date
    amount: Decimal
    normalized_merchant: str
    raw_description: str


@dataclass(frozen=True)
class DetectedPattern:
    """Output of recurring detection for one merchant group."""

    normalized_merchant: str
    pattern_type: str
    cadence: str
    expected_amount: Decimal
    amount_variance_pct: float
    next_expected_date: date | None
    evidence: dict[str, Any]
    transaction_ids: list[int]


def _day_gaps(dates: list[date]) -> list[int]:
    """Return consecutive day gaps for sorted dates."""
    sorted_dates = sorted(dates)
    return [
        (sorted_dates[i + 1] - sorted_dates[i]).days
        for i in range(len(sorted_dates) - 1)
    ]


def _detect_cadence(gaps: list[int], tolerance_days: int) -> str | None:
    """Pick the cadence whose target is closest to median gap."""
    if not gaps:
        return None
    median_gap = sorted(gaps)[len(gaps) // 2]
    best_cadence = None
    best_distance = tolerance_days + 1
    for cadence, target in CADENCE_TARGETS.items():
        distance = abs(median_gap - target)
        if distance <= tolerance_days and distance < best_distance:
            best_cadence = cadence
            best_distance = distance
    return best_cadence


def _amount_variance_pct(amounts: list[Decimal]) -> float:
    """Return percent std-dev relative to mean absolute amount."""
    abs_amounts = [abs(float(a)) for a in amounts]
    if len(abs_amounts) < 2:
        return 0.0
    avg = mean(abs_amounts)
    if avg == 0:
        return 0.0
    return (pstdev(abs_amounts) / avg) * 100.0


def _has_keyword(text: str, keywords: frozenset[str]) -> bool:
    """Return True when any keyword appears in text."""
    lower = text.lower()
    return any(keyword in lower for keyword in keywords)


def _classify_pattern_type(
    merchant: str,
    descriptions: list[str],
    cadence: str,
    avg_amount: Decimal,
) -> str:
    """Classify recurring debit as EMI, loan, subscription, or autopay."""
    combined = " ".join([merchant, *descriptions]).lower()
    if _has_keyword(combined, EMI_KEYWORDS):
        return "emi" if "loan" not in combined else "loan"
    if _has_keyword(combined, SUBSCRIPTION_KEYWORDS):
        return "subscription"
    if cadence == "monthly" and abs(avg_amount) >= 1000:
        return "autopay"
    return "subscription"


def detect_recurring_group(
    merchant: str,
    transactions: list[TransactionSnapshot],
    *,
    min_occurrences: int,
    gap_tolerance_days: int,
    max_amount_variance_pct: float,
) -> DetectedPattern | None:
    """
    Detect a recurring pattern within one merchant group.

    Requires stable cadence and amount variance below threshold.
    """
    if len(transactions) < min_occurrences:
        return None

    debits = [t for t in transactions if t.amount < 0]
    if len(debits) < min_occurrences:
        return None

    dates = [t.transaction_date for t in debits]
    gaps = _day_gaps(dates)
    cadence = _detect_cadence(gaps, gap_tolerance_days)
    if cadence is None:
        return None

    amounts = [t.amount for t in debits]
    variance_pct = _amount_variance_pct(amounts)
    if variance_pct > max_amount_variance_pct:
        return None

    avg_amount = Decimal(str(round(mean([float(a) for a in amounts]), 2)))
    descriptions = [t.raw_description for t in debits]
    pattern_type = _classify_pattern_type(merchant, descriptions, cadence, avg_amount)

    sorted_debits = sorted(debits, key=lambda t: t.transaction_date)
    last_date = sorted_debits[-1].transaction_date
    target_days = CADENCE_TARGETS[cadence]
    next_expected = last_date + timedelta(days=target_days)

    txn_ids = [t.id for t in sorted_debits]
    evidence: dict[str, Any] = {
        "transaction_ids": txn_ids,
        "occurrences": len(debits),
        "avg_gap_days": round(mean(gaps), 1) if gaps else 0,
        "cadence_detected": cadence,
        "amount_mean": str(avg_amount),
        "amount_std_pct": round(variance_pct, 2),
        "classification_signals": _build_signals(
            merchant,
            descriptions,
            cadence,
            variance_pct,
            pattern_type,
        ),
    }

    return DetectedPattern(
        normalized_merchant=merchant,
        pattern_type=pattern_type,
        cadence=cadence,
        expected_amount=avg_amount,
        amount_variance_pct=variance_pct,
        next_expected_date=next_expected,
        evidence=evidence,
        transaction_ids=txn_ids,
    )


def _build_signals(
    merchant: str,
    descriptions: list[str],
    cadence: str,
    variance_pct: float,
    pattern_type: str,
) -> list[str]:
    """Build human-readable classification signals for evidence."""
    combined = " ".join([merchant, *descriptions]).lower()
    signals = [f"{cadence}_cadence", f"amount_variance_{variance_pct:.1f}pct"]
    if _has_keyword(combined, EMI_KEYWORDS):
        signals.append("emi_keyword")
    if _has_keyword(combined, SUBSCRIPTION_KEYWORDS):
        signals.append("subscription_keyword")
    signals.append(f"classified_as_{pattern_type}")
    return signals
