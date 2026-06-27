"""Statements API URL routes."""

from django.urls import path

from statements.views.v1.accounts import AccountDetailView, AccountListCreateView
from statements.views.v1.statements import (
    AiCategorizeView,
    CategoryListView,
    RecategorizeView,
    StatementDetailView,
    StatementListCreateView,
    TransactionDetailView,
    TransactionListView,
)

urlpatterns = [
    path("accounts/", AccountListCreateView.as_view(), name="account-list-create"),
    path("accounts/<int:pk>/", AccountDetailView.as_view(), name="account-detail"),
    path("categories/", CategoryListView.as_view(), name="category-list"),
    path("", StatementListCreateView.as_view(), name="statement-list-create"),
    path("<int:pk>/", StatementDetailView.as_view(), name="statement-detail"),
    path("transactions/", TransactionListView.as_view(), name="transaction-list"),
    path(
        "transactions/ai-categorize/",
        AiCategorizeView.as_view(),
        name="transaction-ai-categorize",
    ),
    path(
        "transactions/recategorize/",
        RecategorizeView.as_view(),
        name="transaction-recategorize",
    ),
    path(
        "transactions/<int:pk>/",
        TransactionDetailView.as_view(),
        name="transaction-detail",
    ),
]
