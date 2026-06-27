"""Pure insight generation rules with evidence."""

from dataclasses import dataclass
from decimal import Decimal
from typing import Any


@dataclass(frozen=True)
class GeneratedInsight:
    """Insight payload before persistence."""

    insight_type: str
    priority: int
    title: str
    message: str
    evidence: dict[str, Any]


def _pct(value: Decimal, base: Decimal) -> float | None:
    """Return percentage of value relative to base."""
    if base <= 0:
        return None
    return float((value / base) * 100)


def generate_insights(
    *,
    aggregates: dict[str, Any],
    prior_aggregates: dict[str, Any] | None,
    low_savings_threshold_pct: float,
    high_emi_threshold_pct: float,
    rising_spend_threshold_pct: float,
    good_savings_threshold_pct: float,
    duplicate_subscription_types: list[str],
) -> list[GeneratedInsight]:
    """
    Build prioritized leak/saving insights from current and prior period data.

    Lower priority number = higher importance.
    """
    insights: list[GeneratedInsight] = []

    income = Decimal(aggregates.get("income", "0"))
    expense = Decimal(aggregates.get("expense", "0"))
    emi_total = Decimal(aggregates.get("emi_total", "0"))
    subscription_total = Decimal(aggregates.get("subscription_total", "0"))
    savings_rate = aggregates.get("savings_rate")
    category_totals = aggregates.get("category_totals") or []

    if savings_rate is not None and savings_rate < low_savings_threshold_pct:
        insights.append(
            GeneratedInsight(
                insight_type="leak",
                priority=10,
                title="Low savings rate",
                message=(
                    f"You saved {savings_rate:.1f}% of income this period "
                    f"(below {low_savings_threshold_pct:.0f}% target)."
                ),
                evidence={
                    "rule": "low_savings_rate",
                    "savings_rate": savings_rate,
                    "threshold_pct": low_savings_threshold_pct,
                    "income": str(income),
                    "expense": str(expense),
                    "net_cash_flow": aggregates.get("net_cash_flow"),
                },
            )
        )

    emi_pct = _pct(emi_total, income)
    if emi_pct is not None and emi_pct >= high_emi_threshold_pct:
        insights.append(
            GeneratedInsight(
                insight_type="leak",
                priority=20,
                title="High EMI burden",
                message=(
                    f"EMI and loan payments are {emi_pct:.1f}% of income "
                    f"(above {high_emi_threshold_pct:.0f}% guideline)."
                ),
                evidence={
                    "rule": "high_emi_burden",
                    "emi_total": str(emi_total),
                    "emi_pct_of_income": emi_pct,
                    "threshold_pct": high_emi_threshold_pct,
                    "income": str(income),
                },
            )
        )

    if len(duplicate_subscription_types) >= 2:
        insights.append(
            GeneratedInsight(
                insight_type="leak",
                priority=30,
                title="Multiple active subscriptions",
                message=(
                    f"{len(duplicate_subscription_types)} recurring subscription"
                    f"{'s' if len(duplicate_subscription_types) != 1 else ''} "
                    "detected — review for overlap."
                ),
                evidence={
                    "rule": "duplicate_subscriptions",
                    "merchants": duplicate_subscription_types,
                    "subscription_total": str(subscription_total),
                },
            )
        )

    uncategorized_total = Decimal("0")
    uncategorized_count = 0
    for category in category_totals:
        if category.get("category_slug") == "uncategorized":
            uncategorized_total = Decimal(category.get("total", "0"))
            uncategorized_count = int(category.get("transaction_count", 0))
            break

    if uncategorized_total > 0 and expense > 0:
        uncategorized_pct = float((uncategorized_total / expense) * 100)
        if uncategorized_pct >= 5 or uncategorized_total >= Decimal("1000"):
            insights.append(
                GeneratedInsight(
                    insight_type="leak",
                    priority=25,
                    title="Uncategorized spending hides leaks",
                    message=(
                        f"₹{uncategorized_total:,.0f} across {uncategorized_count} "
                        "transactions is still uncategorized. Categorize them to see "
                        "where you can cut back."
                    ),
                    evidence={
                        "rule": "high_uncategorized_spend",
                        "uncategorized_total": str(uncategorized_total),
                        "uncategorized_count": uncategorized_count,
                        "uncategorized_pct_of_expense": uncategorized_pct,
                    },
                ),
            )

    discretionary_slugs = ("shopping", "entertainment", "food-dining")
    discretionary_total = sum(
        Decimal(category.get("total", "0"))
        for category in category_totals
        if category.get("category_slug") in discretionary_slugs
    )
    discretionary_pct = _pct(discretionary_total, expense)
    if discretionary_pct is not None and discretionary_pct >= 30:
        insights.append(
            GeneratedInsight(
                insight_type="suggestion",
                priority=35,
                title="Discretionary spend is high",
                message=(
                    f"Food, shopping, and entertainment are {discretionary_pct:.0f}% "
                    "of spending — review these categories for easy savings."
                ),
                evidence={
                    "rule": "high_discretionary_spend",
                    "discretionary_total": str(discretionary_total),
                    "discretionary_pct_of_expense": discretionary_pct,
                    "categories": list(discretionary_slugs),
                },
            ),
        )

    if prior_aggregates:
        prior_expense = Decimal(prior_aggregates.get("expense", "0"))
        if prior_expense > 0 and expense > prior_expense:
            increase_pct = float(((expense - prior_expense) / prior_expense) * 100)
            if increase_pct >= rising_spend_threshold_pct:
                insights.append(
                    GeneratedInsight(
                        insight_type="leak",
                        priority=40,
                        title="Spending increased vs prior period",
                        message=(
                            f"Total spending rose {increase_pct:.1f}% compared to "
                            "your previous statement."
                        ),
                        evidence={
                            "rule": "rising_total_spend",
                            "current_expense": str(expense),
                            "prior_expense": str(prior_expense),
                            "increase_pct": increase_pct,
                            "threshold_pct": rising_spend_threshold_pct,
                        },
                    )
                )

        prior_categories = {
            item["category_slug"]: Decimal(item["total"])
            for item in (prior_aggregates.get("category_totals") or [])
        }
        for category in category_totals:
            slug = category["category_slug"]
            current_total = Decimal(category["total"])
            prior_total = prior_categories.get(slug)
            if prior_total is None or prior_total <= 0:
                continue
            increase_pct = float(((current_total - prior_total) / prior_total) * 100)
            if increase_pct >= rising_spend_threshold_pct:
                insights.append(
                    GeneratedInsight(
                        insight_type="leak",
                        priority=50,
                        title=f"Rising {category['category_name']} spend",
                        message=(
                            f"{category['category_name']} spending increased "
                            f"{increase_pct:.1f}% vs the prior period."
                        ),
                        evidence={
                            "rule": "rising_category_spend",
                            "category_slug": slug,
                            "category_name": category["category_name"],
                            "current_total": str(current_total),
                            "prior_total": str(prior_total),
                            "increase_pct": increase_pct,
                            "threshold_pct": rising_spend_threshold_pct,
                        },
                    )
                )

    if savings_rate is not None and savings_rate >= good_savings_threshold_pct:
        insights.append(
            GeneratedInsight(
                insight_type="saving",
                priority=100,
                title="Healthy savings rate",
                message=(
                    f"You saved {savings_rate:.1f}% of income — above the "
                    f"{good_savings_threshold_pct:.0f}% goal."
                ),
                evidence={
                    "rule": "healthy_savings_rate",
                    "savings_rate": savings_rate,
                    "threshold_pct": good_savings_threshold_pct,
                    "net_cash_flow": aggregates.get("net_cash_flow"),
                },
            )
        )

    if prior_aggregates:
        prior_expense = Decimal(prior_aggregates.get("expense", "0"))
        if prior_expense > 0 and expense < prior_expense:
            decrease_pct = float(((prior_expense - expense) / prior_expense) * 100)
            if decrease_pct >= rising_spend_threshold_pct:
                insights.append(
                    GeneratedInsight(
                        insight_type="saving",
                        priority=110,
                        title="Spending decreased vs prior period",
                        message=(
                            f"Total spending fell {decrease_pct:.1f}% compared to "
                            "your previous statement."
                        ),
                        evidence={
                            "rule": "reduced_total_spend",
                            "current_expense": str(expense),
                            "prior_expense": str(prior_expense),
                            "decrease_pct": decrease_pct,
                        },
                    )
                )

    insights.sort(key=lambda item: item.priority)
    return insights
