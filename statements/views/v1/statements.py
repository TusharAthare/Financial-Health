"""Statement and transaction API views."""

from datetime import datetime

from rest_framework import status
from rest_framework.pagination import PageNumberPagination
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from rest_framework.views import APIView

from api.permissions import IsOwner
from api.throttling import UploadRateThrottle
from services.internal.categorization import CategorizationService
from services.internal.statement import StatementService
from services.internal.transaction import TransactionService
from statements.models import Statement
from statements.serializers.statements import (
    CategorySerializer,
    StatementSerializer,
    StatementUploadSerializer,
    TransactionCategoryUpdateSerializer,
    TransactionSerializer,
)
from statements.tasks import parse_statement_task


class StatementPagination(PageNumberPagination):
    """Default pagination for statement lists."""

    page_size = 20
    page_size_query_param = "page_size"
    max_page_size = 100


class TransactionPagination(PageNumberPagination):
    """Pagination for transaction lists with filter-level stats."""

    page_size = 50
    page_size_query_param = "page_size"
    max_page_size = 200
    stats: dict | None = None

    def get_paginated_response(self, data) -> Response:
        """Return paginated rows plus credit/debit stats for the full filter."""
        payload = {
            "count": self.page.paginator.count,
            "next": self.get_next_link(),
            "previous": self.get_previous_link(),
            "results": data,
        }
        if self.stats is not None:
            payload["stats"] = self.stats
        return Response(payload)


class StatementListCreateView(APIView):
    """List statements and upload new CSV/PDF files."""

    permission_classes = [IsAuthenticated]
    pagination_class = StatementPagination

    def get_throttles(self):
        """Apply upload rate limit only to POST requests."""
        if self.request.method == "POST":
            return [UploadRateThrottle()]
        return []

    def get(self, request) -> Response:
        """Return paginated statements for the authenticated user."""
        statements = StatementService().list_statements(user_id=request.user.id)
        paginator = StatementPagination()
        page = paginator.paginate_queryset(statements, request)
        serializer = StatementSerializer(page, many=True)
        return paginator.get_paginated_response(serializer.data)

    def post(self, request) -> Response:
        """Upload a statement and enqueue parsing."""
        serializer = StatementUploadSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)

        pdf_password = serializer.validated_data.get("pdf_password") or None
        if pdf_password == "":
            pdf_password = None

        statement = StatementService().upload_statement(
            user_id=request.user.id,
            account_id=serializer.validated_data["account_id"],
            uploaded_file=serializer.validated_data["file"],
        )

        if statement.status == Statement.Status.UPLOADED:
            parse_statement_task.delay(statement.id, pdf_password=pdf_password)
            return Response(
                StatementSerializer(statement).data,
                status=status.HTTP_202_ACCEPTED,
            )

        return Response(
            StatementSerializer(statement).data,
            status=status.HTTP_200_OK,
        )


class StatementDetailView(APIView):
    """Retrieve a single statement (parse status)."""

    permission_classes = [IsAuthenticated, IsOwner]

    def get(self, request, pk: int) -> Response:
        """Return statement status and metadata."""
        statement = StatementService().get_statement(
            user_id=request.user.id,
            statement_id=pk,
        )
        if statement is None:
            return Response(
                {"error": {"code": "not_found", "message": "Statement not found."}},
                status=status.HTTP_404_NOT_FOUND,
            )
        self.check_object_permissions(request, statement)
        return Response(StatementSerializer(statement).data)


class TransactionListView(APIView):
    """List transactions with optional filters."""

    permission_classes = [IsAuthenticated]

    def get(self, request) -> Response:
        """Return paginated, filtered transactions."""
        statement_id = request.query_params.get("statement")
        category_id = request.query_params.get("category")
        date_from = _parse_date_param(request.query_params.get("from"))
        date_to = _parse_date_param(request.query_params.get("to"))
        direction = request.query_params.get("direction")
        search = request.query_params.get("search")
        uncategorized_only = (
            request.query_params.get("uncategorized", "").lower() in ("1", "true", "yes")
        )

        if direction and direction not in ("credit", "debit"):
            return Response(
                {
                    "error": {
                        "code": "validation_error",
                        "message": "direction must be credit or debit.",
                    },
                },
                status=status.HTTP_400_BAD_REQUEST,
            )

        service = TransactionService()
        queryset = service.list_transactions(
            user_id=request.user.id,
            statement_id=int(statement_id) if statement_id else None,
            category_id=int(category_id) if category_id else None,
            date_from=date_from,
            date_to=date_to,
            direction=direction,
            search=search,
            uncategorized_only=uncategorized_only,
        )

        paginator = TransactionPagination()
        paginator.stats = service.summarize_transactions(queryset)
        page = paginator.paginate_queryset(queryset, request)
        serializer = TransactionSerializer(page, many=True)
        return paginator.get_paginated_response(serializer.data)


class CategoryListView(APIView):
    """List system and user-defined categories."""

    permission_classes = [IsAuthenticated]

    def get(self, request) -> Response:
        """Return categories available for the authenticated user."""
        categories = CategorizationService().list_categories(user_id=request.user.id)
        serializer = CategorySerializer(categories, many=True)
        return Response(serializer.data)


class TransactionDetailView(APIView):
    """Update a single transaction (category override)."""

    permission_classes = [IsAuthenticated]

    def patch(self, request, pk: int) -> Response:
        """Apply a manual category override and learn a user rule."""
        serializer = TransactionCategoryUpdateSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)

        txn = CategorizationService().override_category(
            user_id=request.user.id,
            transaction_id=pk,
            category_id=serializer.validated_data["category_id"],
        )
        return Response(TransactionSerializer(txn).data)


class AiCategorizeView(APIView):
    """Run Gemini categorization on remaining uncategorized transactions."""

    permission_classes = [IsAuthenticated]

    def post(self, request) -> Response:
        """Batch-categorize uncategorized merchants via Gemini."""
        from services.internal.gemini_categorization import GeminiCategorizationService

        service = GeminiCategorizationService()
        if not service.is_enabled():
            return Response(
                {
                    "error": {
                        "code": "gemini_disabled",
                        "message": "Gemini categorization is not configured.",
                    },
                },
                status=status.HTTP_503_SERVICE_UNAVAILABLE,
            )

        statement_param = request.data.get("statement_id") or request.query_params.get(
            "statement",
        )
        statement_id = int(statement_param) if statement_param else None

        result = service.enrich_uncategorized(
            user_id=request.user.id,
            statement_id=statement_id,
            action="transaction_categorize_manual",
        )

        if result.updated > 0:
            from services.internal.report import ReportService

            report_service = ReportService()
            rebuild_ids = (
                (statement_id,)
                if statement_id is not None
                else result.affected_statement_ids
            )
            for sid in rebuild_ids:
                report_service.build_for_statement(
                    user_id=request.user.id,
                    statement_id=sid,
                )

        return Response(
            {
                "updated": result.updated,
                "status": result.status,
                "message": result.message,
                "merchants_total": result.merchants_total,
                "merchants_processed": result.merchants_processed,
                "merchants_remaining": result.merchants_remaining,
                "batches_run": result.batches_run,
            },
        )


class RecategorizeView(APIView):
    """Re-apply UPI remark extraction and rule-based categorization."""

    permission_classes = [IsAuthenticated]

    def post(self, request) -> Response:
        """Apply UPI notes and re-run categorization rules (no Gemini)."""
        statement_param = request.data.get("statement_id") or request.query_params.get(
            "statement",
        )
        statement_id = int(statement_param) if statement_param else None

        updated = CategorizationService().apply_remarks_and_recategorize(
            user_id=request.user.id,
            statement_id=statement_id,
        )

        if updated > 0:
            from services.internal.report import ReportService

            report_service = ReportService()
            if statement_id is not None:
                report_service.build_for_statement(
                    user_id=request.user.id,
                    statement_id=statement_id,
                )
            else:
                for sid in Statement.objects.filter(
                    user_id=request.user.id,
                    status=Statement.Status.PARSED,
                ).values_list("id", flat=True):
                    report_service.build_for_statement(
                        user_id=request.user.id,
                        statement_id=sid,
                    )

        return Response(
            {
                "updated": updated,
                "message": (
                    f"Re-categorized {updated} transactions using UPI notes and rules."
                    if updated
                    else "No category changes were needed."
                ),
            },
        )


def _parse_date_param(value: str | None):
    """Parse YYYY-MM-DD query param; return None when absent."""
    if not value:
        return None
    try:
        return datetime.strptime(value, "%Y-%m-%d").date()
    except ValueError:
        return None
