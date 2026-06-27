"""Seed keyword rules for common UPI payment notes (food & related)."""

from django.db import migrations

# (category_slug, pattern, priority) — keyword rules match remark + description
UPI_REMARK_KEYWORDS = [
    # Food & dining — common home UPI notes
    ("food-dining", "panner", 55),
    ("food-dining", "paneer", 55),
    ("food-dining", "milk", 55),
    ("food-dining", "doodh", 55),
    ("food-dining", "grocery", 55),
    ("food-dining", "kirana", 55),
    ("food-dining", "sabzi", 55),
    ("food-dining", "vegetable", 55),
    ("food-dining", "veggies", 55),
    ("food-dining", "fruit", 55),
    ("food-dining", "lunch", 55),
    ("food-dining", "dinner", 55),
    ("food-dining", "breakfast", 55),
    ("food-dining", "chai", 55),
    ("food-dining", "tea", 55),
    ("food-dining", "coffee", 55),
    ("food-dining", "snacks", 55),
    ("food-dining", "biryani", 55),
    ("food-dining", "food", 55),
    ("food-dining", "restaurant", 55),
    ("food-dining", "canteen", 55),
    ("food-dining", "mess", 55),
    ("food-dining", "bread", 55),
    ("food-dining", "eggs", 55),
    ("food-dining", "rice", 55),
    ("food-dining", "dal", 55),
    ("food-dining", "chicken", 55),
    ("food-dining", "fish", 55),
    ("food-dining", "meat", 55),
    ("food-dining", "mithai", 55),
    ("food-dining", "sweets", 55),
    # Transport — common fuel notes
    ("transport", "petrol", 56),
    ("transport", "diesel", 56),
    ("transport", "fuel", 56),
    # Health — medicine notes
    ("health", "medicine", 56),
    ("health", "pharmacy", 56),
    ("health", "chemist", 56),
]


def seed_upi_remark_keywords(apps, schema_editor) -> None:
    """Insert keyword rules for UPI user notes."""
    Category = apps.get_model("statements", "Category")
    CategoryRule = apps.get_model("statements", "CategoryRule")

    categories_by_slug = {
        cat.slug: cat
        for cat in Category.objects.filter(user__isnull=True)
    }

    for slug, pattern, priority in UPI_REMARK_KEYWORDS:
        category = categories_by_slug.get(slug)
        if category is None:
            continue
        CategoryRule.objects.get_or_create(
            user=None,
            pattern=pattern,
            rule_type="keyword",
            defaults={
                "category": category,
                "priority": priority,
                "is_active": True,
            },
        )


def remove_upi_remark_keywords(apps, schema_editor) -> None:
    """Remove UPI remark keyword rules."""
    CategoryRule = apps.get_model("statements", "CategoryRule")
    patterns = [pattern for _, pattern, _ in UPI_REMARK_KEYWORDS]
    CategoryRule.objects.filter(
        user__isnull=True,
        rule_type="keyword",
        pattern__in=patterns,
    ).delete()


class Migration(migrations.Migration):
    dependencies = [
        ("statements", "0006_alter_statement_file_format"),
    ]

    operations = [
        migrations.RunPython(seed_upi_remark_keywords, remove_upi_remark_keywords),
    ]
