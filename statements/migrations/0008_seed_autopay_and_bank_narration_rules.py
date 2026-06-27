"""Seed rules for AUTOPAY, credit card SI, and bank interest narrations."""

from django.db import migrations

# (category_slug, rule_type, pattern, priority)
BANK_NARRATION_RULES = [
    # EMI, autopay, credit card bill payments
    ("emi-loan", "keyword", "autopay", 35),
    ("emi-loan", "keyword", "auto debit", 36),
    ("emi-loan", "keyword", "si-tad", 37),
    ("emi-loan", "keyword", "e-mandate", 38),
    ("emi-loan", "keyword", "standing instruct", 39),
    ("emi-loan", "keyword", "credit card", 40),
    ("emi-loan", "regex", r"CC\d{4,}X+AUTOPAY", 34),
    ("emi-loan", "regex", r"AUTOPAYSI", 33),
    # Bank interest credits
    ("income", "keyword", "interestpaid", 45),
    ("income", "keyword", "interest paid", 46),
    ("income", "keyword", "int.pd", 47),
]


def seed_bank_narration_rules(apps, schema_editor) -> None:
    """Insert system rules for autopay and bank narrations."""
    Category = apps.get_model("statements", "Category")
    CategoryRule = apps.get_model("statements", "CategoryRule")

    categories_by_slug = {
        cat.slug: cat
        for cat in Category.objects.filter(user__isnull=True)
    }

    for slug, rule_type, pattern, priority in BANK_NARRATION_RULES:
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


def remove_bank_narration_rules(apps, schema_editor) -> None:
    """Remove seeded bank narration rules."""
    CategoryRule = apps.get_model("statements", "CategoryRule")
    patterns = [pattern for _, _, pattern, _ in BANK_NARRATION_RULES]
    CategoryRule.objects.filter(user__isnull=True, pattern__in=patterns).delete()


class Migration(migrations.Migration):
    dependencies = [
        ("statements", "0007_seed_upi_remark_food_keywords"),
    ]

    operations = [
        migrations.RunPython(seed_bank_narration_rules, remove_bank_narration_rules),
    ]
