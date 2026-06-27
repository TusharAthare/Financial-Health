"""Seed default system categorization rules."""

from django.db import migrations

# (category_slug, rule_type, pattern, priority)
SYSTEM_RULES = [
    # Income
    ("income", "keyword", "salary", 50),
    ("income", "keyword", "neft cr", 51),
    ("income", "keyword", "imps cr", 52),
    # Food & Dining
    ("food-dining", "merchant_contains", "swiggy", 60),
    ("food-dining", "merchant_contains", "zomato", 61),
    ("food-dining", "merchant_contains", "dominos", 62),
    ("food-dining", "merchant_contains", "mcdonald", 63),
    ("food-dining", "merchant_contains", "starbucks", 64),
    # Shopping
    ("shopping", "merchant_contains", "amazon", 70),
    ("shopping", "merchant_contains", "flipkart", 71),
    ("shopping", "merchant_contains", "myntra", 72),
    ("shopping", "merchant_contains", "meesho", 73),
    # Transport
    ("transport", "merchant_contains", "uber", 80),
    ("transport", "merchant_contains", "ola", 81),
    ("transport", "merchant_contains", "rapido", 82),
    ("transport", "merchant_contains", "irctc", 83),
    ("transport", "merchant_contains", "indigo", 84),
    # Utilities
    ("utilities", "merchant_contains", "jio", 90),
    ("utilities", "merchant_contains", "airtel", 91),
    ("utilities", "merchant_contains", "bsnl", 92),
    ("utilities", "merchant_contains", "bescom", 93),
    ("utilities", "merchant_contains", "electricity", 94),
    # Entertainment
    ("entertainment", "merchant_contains", "netflix", 100),
    ("entertainment", "merchant_contains", "spotify", 101),
    ("entertainment", "merchant_contains", "hotstar", 102),
    ("entertainment", "merchant_contains", "bookmyshow", 103),
    # Health
    ("health", "merchant_contains", "apollo", 110),
    ("health", "merchant_contains", "pharmeasy", 111),
    ("health", "merchant_contains", "1mg", 112),
    # Education
    ("education", "merchant_contains", "udemy", 120),
    ("education", "merchant_contains", "coursera", 121),
    # EMI & Loans
    ("emi-loan", "keyword", "emi", 40),
    ("emi-loan", "keyword", "loan", 41),
    ("emi-loan", "keyword", "nach", 42),
    ("emi-loan", "merchant_contains", "bajaj finance", 43),
    ("emi-loan", "merchant_contains", "hdfc ltd", 44),
    # Transfer
    ("transfer", "keyword", "upi transfer", 130),
    ("transfer", "keyword", "neft dr", 131),
    ("transfer", "keyword", "imps dr", 132),
]


def seed_system_rules(apps, schema_editor) -> None:
    """Insert system-wide categorization rules."""
    Category = apps.get_model("statements", "Category")
    CategoryRule = apps.get_model("statements", "CategoryRule")

    categories_by_slug = {
        cat.slug: cat
        for cat in Category.objects.filter(user__isnull=True)
    }

    for slug, rule_type, pattern, priority in SYSTEM_RULES:
        category = categories_by_slug.get(slug)
        if category is None:
            continue
        CategoryRule.objects.get_or_create(
            user=None,
            pattern=pattern,
            rule_type=rule_type,
            defaults={
                "category": category,
                "priority": priority,
                "is_active": True,
            },
        )


def remove_system_rules(apps, schema_editor) -> None:
    """Remove seeded system categorization rules."""
    CategoryRule = apps.get_model("statements", "CategoryRule")
    patterns = [pattern for _, _, pattern, _ in SYSTEM_RULES]
    CategoryRule.objects.filter(user__isnull=True, pattern__in=patterns).delete()


class Migration(migrations.Migration):
    dependencies = [
        ("statements", "0004_transaction_categorization_evidence_and_more"),
    ]

    operations = [
        migrations.RunPython(seed_system_rules, remove_system_rules),
    ]
