"""Categorization rule engine and user-override learning."""

import logging

from django.conf import settings
from django.db import transaction
from django.db.models import Q

from services.domain.categorization import (
    RuleMatchInput,
    build_evidence,
    resolve_category,
)
from services.domain.exceptions import DomainPermissionDenied, DomainValidationError
from statements.models import Category, CategoryRule, Statement, Transaction

logger = logging.getLogger(__name__)


class CategorizationService:
    """Apply explainable rules and learn from user category overrides."""

    def list_categories(self, user_id: int) -> list[Category]:
        """Return system categories plus user-defined categories."""
        return list(
            Category.objects.filter(Q(user__isnull=True) | Q(user_id=user_id))
            .order_by("name")
        )

    def categorize_for_statement(self, user_id: int, statement_id: int) -> int:
        """
        Categorize all transactions on a statement.

        Returns the number of transactions updated.
        """
        txn_ids = list(
            Transaction.objects.filter(
                user_id=user_id,
                statement_id=statement_id,
            ).values_list("id", flat=True)
        )
        updated = self.categorize_transactions(user_id, transaction_ids=txn_ids)

        from services.internal.gemini_categorization import GeminiCategorizationService

        gemini_result = GeminiCategorizationService().enrich_uncategorized(
            user_id=user_id,
            statement_id=statement_id,
            action="transaction_categorize_parse",
        )
        return updated + gemini_result.updated

    def categorize_transactions(
        self,
        user_id: int,
        *,
        statement_id: int | None = None,
        transaction_ids: list[int] | None = None,
    ) -> int:
        """
        Batch-categorize transactions using ordered rules.

        Returns the number of transactions updated.
        """
        rules = self._load_active_rules(user_id)
        uncategorized = self._get_uncategorized_category()

        queryset = Transaction.objects.filter(user_id=user_id)
        if statement_id is not None:
            queryset = queryset.filter(statement_id=statement_id)
        if transaction_ids is not None:
            queryset = queryset.filter(id__in=transaction_ids)

        transactions = list(queryset.only(
            "id",
            "normalized_merchant",
            "raw_description",
            "category_id",
            "matched_rule_id",
            "categorization_evidence",
        ))

        merchant_rewrites = self._apply_merchant_rewrites(transactions)

        to_update: list[Transaction] = []
        for txn in transactions:
            match_input = RuleMatchInput(
                normalized_merchant=txn.normalized_merchant,
                raw_description=txn.raw_description,
            )
            category_id, match_result = resolve_category(rules, match_input)
            if category_id is None:
                category_id = uncategorized.id
                evidence = {"reason": "no_rule_matched", "fallback": "uncategorized"}
                matched_rule_id = None
            else:
                evidence = build_evidence(match_result)
                matched_rule_id = match_result.rule_id
                from services.domain.upi_remark import extract_upi_remark

                remark = extract_upi_remark(txn.raw_description)
                if remark:
                    evidence = {**evidence, "upi_remark": remark}

            if (
                txn.category_id != category_id
                or txn.matched_rule_id != matched_rule_id
                or txn.categorization_evidence != evidence
            ):
                txn.category_id = category_id
                txn.matched_rule_id = matched_rule_id
                txn.categorization_evidence = evidence
                to_update.append(txn)

        if to_update:
            Transaction.objects.bulk_update(
                to_update,
                ["category_id", "matched_rule_id", "categorization_evidence"],
                batch_size=500,
            )

        if merchant_rewrites:
            Transaction.objects.bulk_update(
                merchant_rewrites,
                ["normalized_merchant"],
                batch_size=500,
            )

        logger.info(
            "Categorized transactions user_id=%s updated=%s total=%s",
            user_id,
            len(to_update),
            len(transactions),
        )
        return len(to_update)

    def apply_remarks_and_recategorize(
        self,
        user_id: int,
        *,
        statement_id: int | None = None,
    ) -> int:
        """
        Re-apply UPI remark extraction and rule-based categorization (no Gemini).

        Returns the number of transactions whose category changed.
        """
        if statement_id is not None:
            return self.categorize_transactions(user_id, statement_id=statement_id)

        updated_total = 0
        statement_ids = Statement.objects.filter(
            user_id=user_id,
            status=Statement.Status.PARSED,
        ).values_list("id", flat=True)
        for sid in statement_ids:
            updated_total += self.categorize_transactions(
                user_id,
                statement_id=sid,
            )
        return updated_total

    def _apply_merchant_rewrites(self, transactions: list[Transaction]) -> list[Transaction]:
        """Rewrite normalized_merchant from UPI notes and bank narration patterns."""
        from services.domain.narration_patterns import enrich_merchant_from_narration
        from services.domain.upi_remark import resolve_normalized_merchant

        rewrites: list[Transaction] = []
        for txn in transactions:
            resolved = resolve_normalized_merchant(txn.raw_description)
            enriched = enrich_merchant_from_narration(txn.raw_description, resolved)
            if enriched and enriched != txn.normalized_merchant:
                txn.normalized_merchant = enriched
                rewrites.append(txn)
        return rewrites

    @transaction.atomic
    def override_category(
        self,
        user_id: int,
        transaction_id: int,
        category_id: int,
    ) -> Transaction:
        """
        Apply a manual category override and learn a user rule.

        Creates or updates a merchant_contains rule for the transaction's
        normalized merchant, then re-applies categorization to matching txns.

        Raises DomainPermissionDenied, DomainValidationError.
        """
        txn = (
            Transaction.objects.filter(id=transaction_id, user_id=user_id)
            .select_related("category")
            .first()
        )
        if txn is None:
            raise DomainPermissionDenied("Transaction not found or access denied.")

        category = Category.objects.filter(
            Q(user__isnull=True) | Q(user_id=user_id),
            id=category_id,
        ).first()
        if category is None:
            raise DomainValidationError("Category not found or not accessible.")

        pattern = txn.normalized_merchant.strip()
        if not pattern:
            pattern = txn.raw_description[:128].strip()
        if not pattern:
            raise DomainValidationError(
                "Cannot learn a rule: transaction has no merchant or description."
            )

        rule = CategoryRule.objects.filter(
            user_id=user_id,
            rule_type=CategoryRule.RuleType.MERCHANT_CONTAINS,
            pattern__iexact=pattern,
        ).first()
        if rule is None:
            rule = CategoryRule.objects.create(
                user_id=user_id,
                category=category,
                pattern=pattern,
                rule_type=CategoryRule.RuleType.MERCHANT_CONTAINS,
                priority=settings.USER_CATEGORY_RULE_PRIORITY,
                is_active=True,
            )
        elif rule.category_id != category.id or not rule.is_active:
            rule.category = category
            rule.is_active = True
            rule.save(update_fields=["category", "is_active", "updated_at"])

        evidence = {
            "rule_id": rule.id,
            "rule_pattern": rule.pattern,
            "rule_type": rule.rule_type,
            "matched_field": "normalized_merchant",
            "matched_text": txn.normalized_merchant or txn.raw_description,
            "source": "user_override",
        }
        txn.category = category
        txn.matched_rule = rule
        txn.categorization_evidence = evidence
        txn.save(
            update_fields=[
                "category",
                "matched_rule",
                "categorization_evidence",
            ],
        )
        txn = (
            Transaction.objects.filter(id=txn.id)
            .select_related("category", "matched_rule", "account", "statement")
            .first()
        )

        matching_ids = list(
            Transaction.objects.filter(
                user_id=user_id,
                normalized_merchant__iexact=pattern,
            )
            .exclude(id=txn.id)
            .values_list("id", flat=True)
        )
        if matching_ids:
            self.categorize_transactions(user_id, transaction_ids=matching_ids)

        logger.info(
            "Category override txn_id=%s user_id=%s category=%s rule_id=%s",
            transaction_id,
            user_id,
            category.slug,
            rule.id,
        )
        return txn

    def _load_active_rules(self, user_id: int) -> list[tuple[int, str, str, int]]:
        """Load active rules as (id, type, pattern, category_id) tuples."""
        queryset = CategoryRule.objects.filter(
            Q(user_id=user_id) | Q(user__isnull=True),
            is_active=True,
        ).order_by("priority", "id")

        return [
            (rule.id, rule.rule_type, rule.pattern, rule.category_id)
            for rule in queryset.only("id", "rule_type", "pattern", "category_id")
        ]

    def _get_uncategorized_category(self) -> Category:
        """Return the system Uncategorized category."""
        category = Category.objects.filter(
            user__isnull=True,
            slug="uncategorized",
        ).first()
        if category is None:
            raise DomainValidationError(
                "System category 'uncategorized' is missing. Run migrations."
            )
        return category
