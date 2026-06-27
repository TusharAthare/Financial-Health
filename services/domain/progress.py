"""Pure helpers for cross-period progress comparisons."""

from decimal import Decimal
from typing import Any


def _to_decimal(value: str | Decimal | None) -> Decimal:
    """Parse a stored aggregate value as Decimal."""
    if value is None:
        return Decimal("0")
    if isinstance(value, Decimal):
        return value
    return Decimal(str(value))


def compute_emi_burden_pct(income: str | Decimal, emi_total: str | Decimal) -> float | None:
    """Return EMI total as a percentage of income, or None when income is zero."""
    income_val = _to_decimal(income)
    if income_val <= 0:
        return None
    emi_val = abs(_to_decimal(emi_total))
    return float((emi_val / income_val) * 100)


def compute_category_drift(
    current_totals: list[dict[str, Any]],
    prior_totals: list[dict[str, Any]] | None,
    *,
    top_n: int = 5,
) -> list[dict[str, Any]]:
    """
    Compare category spend between consecutive periods.

    Returns top categories by absolute change with prior/current totals and delta pct.
    """
    if not prior_totals:
        return []

    prior_map = {
        item.get("category_slug", ""): _to_decimal(item.get("total"))
        for item in prior_totals
    }
    drift: list[dict[str, Any]] = []

    for item in current_totals:
        slug = item.get("category_slug", "")
        current_total = _to_decimal(item.get("total"))
        prior_total = prior_map.get(slug, Decimal("0"))
        if current_total == 0 and prior_total == 0:
            continue

        change_pct: float | None = None
        if prior_total > 0:
            change_pct = float(((current_total - prior_total) / prior_total) * 100)
        elif current_total > 0:
            change_pct = 100.0

        drift.append(
            {
                "category_slug": slug,
                "category_name": item.get("category_name", slug),
                "current_total": str(current_total),
                "prior_total": str(prior_total),
                "change_pct": change_pct,
            }
        )

    drift.sort(
        key=lambda row: abs(_to_decimal(row["current_total"]) - _to_decimal(row["prior_total"])),
        reverse=True,
    )
    return drift[:top_n]
