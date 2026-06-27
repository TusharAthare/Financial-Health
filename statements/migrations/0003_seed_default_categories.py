"""Seed default system categories."""

from django.db import migrations

DEFAULT_CATEGORIES = [
    ("uncategorized", "Uncategorized"),
    ("income", "Income"),
    ("food-dining", "Food & Dining"),
    ("shopping", "Shopping"),
    ("transport", "Transport"),
    ("utilities", "Utilities"),
    ("entertainment", "Entertainment"),
    ("health", "Health"),
    ("education", "Education"),
    ("emi-loan", "EMI & Loans"),
    ("transfer", "Transfer"),
]


def seed_categories(apps, schema_editor) -> None:
    """Insert system-wide default categories."""
    Category = apps.get_model("statements", "Category")
    for slug, name in DEFAULT_CATEGORIES:
        Category.objects.get_or_create(
            user=None,
            slug=slug,
            defaults={"name": name},
        )


def remove_categories(apps, schema_editor) -> None:
    """Remove seeded system categories."""
    Category = apps.get_model("statements", "Category")
    slugs = [slug for slug, _ in DEFAULT_CATEGORIES]
    Category.objects.filter(user__isnull=True, slug__in=slugs).delete()


class Migration(migrations.Migration):
    dependencies = [
        ("statements", "0002_category_statement_transaction_and_more"),
    ]

    operations = [
        migrations.RunPython(seed_categories, remove_categories),
    ]
