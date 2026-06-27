"""Gemini-assisted categorization for rule-engine misses (batched, cached)."""

import logging
from dataclasses import dataclass

from django.conf import settings
from django.db import transaction

from services.domain.gemini_categorization import (
    MerchantBatchItem,
    build_categorization_prompt,
    direction_label,
    gemini_group_key,
    parse_categorization_response,
)
from services.third_party.gemini_client import GeminiClient, GeminiClientError
from statements.models import Category, CategoryRule, Transaction

logger = logging.getLogger(__name__)


@dataclass(frozen=True)
class GeminiEnrichResult:
    """Outcome of a Gemini categorization run."""

    updated: int
    merchants_total: int
    merchants_processed: int
    merchants_remaining: int
    batches_run: int
    affected_statement_ids: tuple[int, ...]
    status: str
    message: str


class GeminiCategorizationService:
    """
    Categorize uncategorized transactions via batched Gemini calls.

    Each unique merchant is sent at most once per user (learned rules prevent
    repeat API calls). One API request covers up to GEMINI_BATCH_SIZE merchants.
    """

    def is_enabled(self) -> bool:
        """Return True when Gemini categorization is active."""
        return settings.GEMINI_ENABLED and bool(settings.GEMINI_API_KEY.strip())

    def enrich_uncategorized(
        self,
        user_id: int,
        *,
        statement_id: int | None = None,
        transaction_ids: list[int] | None = None,
        action: str = "transaction_categorize_parse",
    ) -> GeminiEnrichResult:
        """
        Categorize remaining uncategorized transactions using Gemini.

        Processes at most GEMINI_MAX_BATCHES_PER_REQUEST API calls per invocation
        to avoid rate limits.
        """
        if not self.is_enabled():
            return GeminiEnrichResult(
                updated=0,
                merchants_total=0,
                merchants_processed=0,
                merchants_remaining=0,
                batches_run=0,
                affected_statement_ids=(),
                status="disabled",
                message="Gemini is not configured. Set GEMINI_API_KEY in .env.",
            )

        uncategorized = self._get_uncategorized_category()
        queryset = Transaction.objects.filter(
            user_id=user_id,
            category_id=uncategorized.id,
        )
        if statement_id is not None:
            queryset = queryset.filter(statement_id=statement_id)
        if transaction_ids is not None:
            queryset = queryset.filter(id__in=transaction_ids)

        transactions = list(
            queryset.only(
                "id",
                "normalized_merchant",
                "raw_description",
                "amount",
            )
        )
        if not transactions:
            return GeminiEnrichResult(
                updated=0,
                merchants_total=0,
                merchants_processed=0,
                merchants_remaining=0,
                batches_run=0,
                affected_statement_ids=(),
                status="no_work",
                message="No uncategorized transactions found.",
            )

        categories = self._list_categorizable_categories()
        if not categories:
            return GeminiEnrichResult(
                updated=0,
                merchants_total=0,
                merchants_processed=0,
                merchants_remaining=0,
                batches_run=0,
                affected_statement_ids=(),
                status="error",
                message="No categories available for Gemini.",
            )

        valid_slugs = frozenset(cat.slug for cat in categories)
        existing_patterns = self._existing_rule_patterns(user_id)
        merchant_groups, txn_ids_by_key = self._group_by_merchant(
            transactions,
            existing_patterns,
        )
        if not merchant_groups:
            return GeminiEnrichResult(
                updated=0,
                merchants_total=0,
                merchants_processed=0,
                merchants_remaining=0,
                batches_run=0,
                affected_statement_ids=(),
                status="no_work",
                message=(
                    "All uncategorized merchants already have learned rules. "
                    "Try changing a category manually to teach the app."
                ),
            )

        merchant_items = list(merchant_groups.values())
        merchants_total = len(merchant_items)
        batch_size = settings.GEMINI_BATCH_SIZE
        max_batches = settings.GEMINI_MAX_BATCHES_PER_REQUEST
        batches_to_run = min(
            max_batches,
            (merchants_total + batch_size - 1) // batch_size,
        )

        from services.internal.gemini_usage import GeminiUsageService

        usage_service = GeminiUsageService()
        client = GeminiClient()
        category_by_slug = {cat.slug: cat for cat in categories}
        total_updated = 0
        batches_run = 0
        merchants_processed = 0
        affected_statement_ids: set[int] = set()
        last_error: str | None = None
        last_error_code: str | None = None

        for batch_index in range(batches_to_run):
            offset = batch_index * batch_size
            batch = merchant_items[offset : offset + batch_size]
            try:
                updated, batch_statement_ids = self._process_batch(
                    user_id=user_id,
                    client=client,
                    batch=batch,
                    txn_ids_by_key=txn_ids_by_key,
                    categories=categories,
                    valid_slugs=valid_slugs,
                    category_by_slug=category_by_slug,
                    action=action,
                    statement_id=statement_id,
                    usage_service=usage_service,
                )
                total_updated += updated
                affected_statement_ids.update(batch_statement_ids)
                batches_run += 1
                merchants_processed = offset + len(batch)
            except GeminiClientError as exc:
                last_error = str(exc)
                last_error_code = exc.code
                usage_service.log_failure(
                    user_id=user_id,
                    action=action,
                    model=client.model_name,
                    error_code=exc.code,
                    error_message=str(exc),
                    statement_id=statement_id,
                    merchants_in_batch=len(batch),
                    context={
                        "merchant_keys": [item.key for item in batch],
                        "batch_index": batch_index,
                    },
                )
                logger.warning("Gemini batch failed: %s", exc)
                break

            if batch_index < batches_to_run - 1:
                pause = settings.GEMINI_BATCH_PAUSE_SECONDS
                if pause > 0:
                    import time

                    time.sleep(pause)

        merchants_remaining = merchants_total - merchants_processed

        if total_updated > 0:
            status = "ok" if merchants_remaining == 0 else "partial"
            message = (
                f"Categorized {total_updated} transactions "
                f"({merchants_processed} merchant groups)."
            )
            if merchants_remaining > 0:
                message += f" {merchants_remaining} merchant groups remain — click again."
        elif last_error_code == "rate_limited":
            status = "rate_limited"
            message = last_error or "Gemini rate limit exceeded."
        elif last_error:
            status = "error"
            message = last_error
        else:
            status = "no_match"
            message = (
                "Gemini ran but could not map merchants to categories. "
                "Try again or categorize manually."
            )

        if total_updated:
            logger.info(
                "Gemini categorization user_id=%s updated=%s merchants=%s/%s",
                user_id,
                total_updated,
                merchants_processed,
                merchants_total,
            )

        return GeminiEnrichResult(
            updated=total_updated,
            merchants_total=merchants_total,
            merchants_processed=merchants_processed,
            merchants_remaining=max(merchants_remaining, 0),
            batches_run=batches_run,
            affected_statement_ids=tuple(sorted(affected_statement_ids)),
            status=status,
            message=message,
        )

    @transaction.atomic
    def _process_batch(
        self,
        *,
        user_id: int,
        client: GeminiClient,
        batch: list[MerchantBatchItem],
        txn_ids_by_key: dict[str, list[int]],
        categories: list[Category],
        valid_slugs: frozenset[str],
        category_by_slug: dict[str, Category],
        action: str,
        statement_id: int | None,
        usage_service,
    ) -> tuple[int, set[int]]:
        """Run one Gemini call for a merchant batch and persist results."""
        expected_keys = frozenset(item.key for item in batch)
        prompt = build_categorization_prompt(
            batch,
            [(cat.slug, cat.name) for cat in categories],
        )

        generate_result = client.generate(prompt)
        mapping = parse_categorization_response(
            generate_result.text,
            valid_slugs=valid_slugs,
            expected_keys=expected_keys,
        )
        if not mapping:
            logger.warning(
                "Gemini returned no usable mappings for %s merchants",
                len(batch),
            )
            usage_service.log_success(
                user_id=user_id,
                action=action,
                result=generate_result,
                statement_id=statement_id,
                merchants_in_batch=len(batch),
                transactions_updated=0,
                context={
                    "merchant_keys": [item.key for item in batch],
                    "mapped_count": 0,
                },
            )
            return 0, set()

        uncategorized = self._get_uncategorized_category()
        to_update: list[Transaction] = []
        rules_cache: dict[str, CategoryRule] = {}
        batch_statement_ids: set[int] = set()

        for key, slug in mapping.items():
            category = category_by_slug.get(slug)
            if category is None:
                continue

            rule = rules_cache.get(key)
            if rule is None:
                item = next(i for i in batch if i.key == key)
                rule = self._get_or_create_learned_rule(
                    user_id=user_id,
                    pattern=item.normalized_merchant or item.sample_description[:512],
                    category=category,
                )
                rules_cache[key] = rule

            evidence = {
                "source": "gemini",
                "model": settings.GEMINI_MODEL,
                "merchant_key": key,
                "category_slug": slug,
                "rule_id": rule.id,
                "rule_pattern": rule.pattern,
            }

            txn_ids = txn_ids_by_key.get(key, [])
            for txn in Transaction.objects.filter(
                id__in=txn_ids,
                user_id=user_id,
                category_id=uncategorized.id,
            ).only(
                "id",
                "statement_id",
                "category_id",
                "matched_rule_id",
                "categorization_evidence",
            ):
                txn.category_id = category.id
                txn.matched_rule_id = rule.id
                txn.categorization_evidence = evidence
                to_update.append(txn)
                batch_statement_ids.add(txn.statement_id)

        if to_update:
            Transaction.objects.bulk_update(
                to_update,
                ["category_id", "matched_rule_id", "categorization_evidence"],
                batch_size=500,
            )

        usage_service.log_success(
            user_id=user_id,
            action=action,
            result=generate_result,
            statement_id=statement_id,
            merchants_in_batch=len(batch),
            transactions_updated=len(to_update),
            context={
                "merchant_keys": list(mapping.keys()),
                "mapped_count": len(mapping),
                "statement_ids": sorted(batch_statement_ids),
            },
        )
        return len(to_update), batch_statement_ids

    def _group_by_merchant(
        self,
        transactions: list[Transaction],
        existing_patterns: set[str],
    ) -> tuple[dict[str, MerchantBatchItem], dict[str, list[int]]]:
        """Group transactions by merchant key; skip already-learned merchants."""
        groups: dict[str, dict] = {}
        txn_ids_by_key: dict[str, list[int]] = {}

        for txn in transactions:
            key = gemini_group_key(txn.normalized_merchant, txn.raw_description)
            if not key or key in existing_patterns:
                continue

            if key not in groups:
                groups[key] = {
                    "key": key,
                    "normalized_merchant": txn.normalized_merchant.strip(),
                    "sample_description": txn.raw_description,
                    "direction": direction_label(txn.amount),
                }
                txn_ids_by_key[key] = []
            txn_ids_by_key[key].append(txn.id)

        items = {
            key: MerchantBatchItem(
                key=data["key"],
                normalized_merchant=data["normalized_merchant"],
                sample_description=data["sample_description"],
                direction=data["direction"],
            )
            for key, data in groups.items()
        }
        return items, txn_ids_by_key

    def _existing_rule_patterns(self, user_id: int) -> set[str]:
        """Return lowercased merchant patterns already covered by user rules."""
        patterns = CategoryRule.objects.filter(
            user_id=user_id,
            is_active=True,
            rule_type=CategoryRule.RuleType.MERCHANT_CONTAINS,
        ).values_list("pattern", flat=True)
        learned = {pattern.strip().lower() for pattern in patterns if pattern.strip()}
        expanded: set[str] = set(learned)
        for pattern in learned:
            expanded.add(gemini_group_key(pattern, pattern))
        return expanded

    def _get_or_create_learned_rule(
        self,
        *,
        user_id: int,
        pattern: str,
        category: Category,
    ) -> CategoryRule:
        """Create or refresh a user rule learned from Gemini."""
        pattern = pattern.strip()[:512]
        rule = CategoryRule.objects.filter(
            user_id=user_id,
            rule_type=CategoryRule.RuleType.MERCHANT_CONTAINS,
            pattern__iexact=pattern,
        ).first()
        if rule is None:
            return CategoryRule.objects.create(
                user_id=user_id,
                category=category,
                pattern=pattern,
                rule_type=CategoryRule.RuleType.MERCHANT_CONTAINS,
                priority=settings.GEMINI_RULE_PRIORITY,
                is_active=True,
            )
        if rule.category_id != category.id or not rule.is_active:
            rule.category = category
            rule.is_active = True
            rule.save(update_fields=["category", "is_active", "updated_at"])
        return rule

    def _list_categorizable_categories(self) -> list[Category]:
        """Return system categories usable for Gemini (excludes uncategorized)."""
        return list(
            Category.objects.filter(user__isnull=True)
            .exclude(slug="uncategorized")
            .order_by("name")
        )

    def _get_uncategorized_category(self) -> Category:
        """Return the system Uncategorized category."""
        category = Category.objects.filter(
            user__isnull=True,
            slug="uncategorized",
        ).first()
        if category is None:
            raise ValueError("System category 'uncategorized' is missing.")
        return category
