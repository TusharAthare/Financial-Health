import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { useEffect, useMemo, useState } from "react";
import { useSearchParams } from "react-router-dom";

import { PaginationControls } from "@/components/PaginationControls";
import { formatNarration } from "@/lib/format-narration";
import { formatPeriodLabel } from "@/lib/format";
import { parseMonthInput } from "@/lib/month-period";
import {
  aiCategorizeTransactions,
  recategorizeTransactions,
  fetchCategories,
  fetchStatements,
  fetchTransactions,
  updateTransactionCategory,
} from "@/lib/statements-api";
import type { Category, Transaction, TransactionListStats } from "@/types/api";

const DEFAULT_PAGE_SIZE = 50;

function formatAmount(value: string): string {
  const num = Number(value);
  const formatted = new Intl.NumberFormat("en-IN", {
    style: "currency",
    currency: "INR",
    maximumFractionDigits: 2,
  }).format(Math.abs(num));
  return num < 0 ? `-${formatted}` : formatted;
}

function formatDate(value: string): string {
  return new Date(value).toLocaleDateString("en-IN", {
    day: "2-digit",
    month: "short",
    year: "numeric",
  });
}

const AMOUNT_CELL_CLASS =
  "w-[7.5rem] min-w-[7.5rem] whitespace-nowrap px-4 py-3 text-right tabular-nums";
const BALANCE_CELL_CLASS =
  "w-[9rem] min-w-[9rem] whitespace-nowrap px-4 py-3 text-right tabular-nums";
const CATEGORY_CELL_CLASS = "w-[11rem] min-w-[11rem] px-4 py-3 align-top";

function formatInrPrecise(value: string | number): string {
  const num = typeof value === "string" ? Number(value) : value;
  return new Intl.NumberFormat("en-IN", {
    style: "currency",
    currency: "INR",
    maximumFractionDigits: 2,
  }).format(num);
}

function TransactionStatsBar({ stats }: { stats: TransactionListStats }) {
  const net = Number(stats.net_total);
  const netTone = net >= 0 ? "text-emerald-600" : "text-red-600";

  return (
    <div className="grid gap-3 sm:grid-cols-2 lg:grid-cols-4">
      <div className="rounded-lg border border-emerald-200 bg-emerald-50 p-4">
        <p className="text-xs font-medium uppercase tracking-wide text-emerald-700">
          Credited
        </p>
        <p className="mt-1 text-xl font-bold text-emerald-800">
          {formatInrPrecise(stats.credited_total)}
        </p>
        <p className="mt-1 text-xs text-emerald-700">
          {stats.credited_count} transaction{stats.credited_count === 1 ? "" : "s"}
        </p>
      </div>
      <div className="rounded-lg border border-red-200 bg-red-50 p-4">
        <p className="text-xs font-medium uppercase tracking-wide text-red-700">
          Debited
        </p>
        <p className="mt-1 text-xl font-bold text-red-800">
          {formatInrPrecise(stats.debited_total)}
        </p>
        <p className="mt-1 text-xs text-red-700">
          {stats.debited_count} transaction{stats.debited_count === 1 ? "" : "s"}
        </p>
      </div>
      <div className="rounded-lg border border-slate-200 bg-slate-50 p-4">
        <p className="text-xs font-medium uppercase tracking-wide text-slate-600">
          Net
        </p>
        <p className={`mt-1 text-xl font-bold ${netTone}`}>
          {formatInrPrecise(stats.net_total)}
        </p>
        <p className="mt-1 text-xs text-slate-600">
          {stats.transaction_count} total in filter
        </p>
      </div>
      <div className="rounded-lg border border-violet-200 bg-violet-50 p-4">
        <p className="text-xs font-medium uppercase tracking-wide text-violet-700">
          Avg debit
        </p>
        <p className="mt-1 text-xl font-bold text-violet-900">
          {stats.debited_count > 0
            ? formatInrPrecise(Number(stats.debited_total) / stats.debited_count)
            : "—"}
        </p>
        <p className="mt-1 text-xs text-violet-700">Per outgoing transaction</p>
      </div>
    </div>
  );
}

function NarrationCell({ raw }: { raw: string }) {
  const { full, lines } = formatNarration(raw);

  return (
    <div className="w-full min-w-0 break-words" title={full}>
      {lines.map((line, index) => (
        <div
          key={`${index}-${line}`}
          className={
            index === 0
              ? "font-medium leading-snug text-slate-800"
              : "text-xs leading-snug text-slate-500"
          }
        >
          {line}
        </div>
      ))}
    </div>
  );
}

function formatEvidence(txn: Transaction): string {
  const evidence = txn.categorization_evidence;
  if (!evidence || Object.keys(evidence).length === 0) {
    return "No categorization evidence.";
  }
  if (evidence.source === "gemini") {
    return `AI categorized via Gemini (${evidence.category_slug ?? "category"}) using merchant "${evidence.merchant_key ?? evidence.rule_pattern}".`;
  }
  if (evidence.reason === "no_rule_matched") {
    return "No matching rule — defaulted to Uncategorized.";
  }
  if (evidence.source === "user_override") {
    return `Learned from your override: "${evidence.rule_pattern}" → ${txn.category?.name ?? "category"}.`;
  }
  if (evidence.upi_remark) {
    return `Matched UPI note "${evidence.upi_remark}" → ${txn.category?.name ?? "category"}.`;
  }
  const parts = [
    `Rule #${evidence.rule_id}`,
    evidence.rule_type?.replace("_", " "),
    `"${evidence.rule_pattern}"`,
    `matched in ${evidence.matched_field}`,
  ].filter(Boolean);
  return parts.join(" · ");
}

function CategoryCell({
  txn,
  categories,
  onUpdate,
  isUpdating,
}: {
  txn: Transaction;
  categories: Category[];
  onUpdate: (categoryId: number) => void;
  isUpdating: boolean;
}) {
  const [expanded, setExpanded] = useState(false);
  const isUncategorized = !txn.category || txn.category.slug === "uncategorized";

  return (
    <td className={CATEGORY_CELL_CLASS}>
      <div className="flex flex-col gap-1">
        <select
          value={txn.category?.id ?? ""}
          disabled={isUpdating}
          onChange={(e) => onUpdate(Number(e.target.value))}
          className="w-full rounded border border-slate-300 px-2 py-1 text-sm text-slate-700"
          aria-label={`Category for ${txn.normalized_merchant || txn.raw_description}`}
        >
          {isUncategorized && <option value="">Uncategorized</option>}
          {categories.map((cat) => (
            <option key={cat.id} value={cat.id}>
              {cat.name}
            </option>
          ))}
        </select>
        <button
          type="button"
          onClick={() => setExpanded((prev) => !prev)}
          className="self-start text-xs text-brand-600 hover:underline"
        >
          {expanded ? "Hide why" : "Why?"}
        </button>
        {expanded && (
          <p className="text-xs leading-snug text-slate-500">{formatEvidence(txn)}</p>
        )}
      </div>
    </td>
  );
}

export function TransactionsPage() {
  const queryClient = useQueryClient();
  const [searchParams, setSearchParams] = useSearchParams();
  const statementFilter = searchParams.get("statement") ?? "";
  const fromFilter = searchParams.get("from") ?? "";
  const toFilter = searchParams.get("to") ?? "";
  const categoryFilter = searchParams.get("category") ?? "";
  const directionFilter = searchParams.get("direction") ?? "";
  const searchFilter = searchParams.get("search") ?? "";
  const uncategorizedFilter = searchParams.get("uncategorized") === "true";
  const [searchDraft, setSearchDraft] = useState(searchFilter);
  const [page, setPage] = useState(1);
  const [pageSize, setPageSize] = useState(DEFAULT_PAGE_SIZE);

  const updateFilters = (updates: Record<string, string | null>) => {
    const next = new URLSearchParams(searchParams);
    for (const [key, value] of Object.entries(updates)) {
      if (value) {
        next.set(key, value);
      } else {
        next.delete(key);
      }
    }
    setSearchParams(next);
  };

  useEffect(() => {
    setSearchDraft(searchFilter);
  }, [searchFilter]);

  useEffect(() => {
    const timer = window.setTimeout(() => {
      const trimmed = searchDraft.trim();
      const current = searchParams.get("search") ?? "";
      if (trimmed === current) {
        return;
      }
      const next = new URLSearchParams(searchParams);
      if (trimmed) {
        next.set("search", trimmed);
      } else {
        next.delete("search");
      }
      setSearchParams(next);
    }, 400);
    return () => window.clearTimeout(timer);
  }, [searchDraft, searchParams, setSearchParams]);

  useEffect(() => {
    setPage(1);
  }, [
    statementFilter,
    fromFilter,
    toFilter,
    categoryFilter,
    directionFilter,
    searchFilter,
    uncategorizedFilter,
    pageSize,
  ]);

  const queryParams = useMemo(
    () => ({
      statement: statementFilter ? Number(statementFilter) : undefined,
      category: categoryFilter ? Number(categoryFilter) : undefined,
      from: fromFilter || undefined,
      to: toFilter || undefined,
      direction:
        directionFilter === "credit" || directionFilter === "debit"
          ? (directionFilter as "credit" | "debit")
          : undefined,
      search: searchFilter || undefined,
      uncategorized: uncategorizedFilter || undefined,
      page,
      page_size: pageSize,
    }),
    [
      statementFilter,
      categoryFilter,
      fromFilter,
      toFilter,
      directionFilter,
      searchFilter,
      uncategorizedFilter,
      page,
      pageSize,
    ],
  );

  const { data, isLoading, isError, error } = useQuery({
    queryKey: ["transactions", queryParams],
    queryFn: () => fetchTransactions(queryParams),
  });

  const { data: categories = [] } = useQuery({
    queryKey: ["categories"],
    queryFn: fetchCategories,
  });

  const { data: statementsPage } = useQuery({
    queryKey: ["statements", { page_size: 100 }],
    queryFn: () => fetchStatements({ page_size: 100 }),
  });

  const parsedStatements = useMemo(
    () =>
      (statementsPage?.results ?? []).filter((statement) => statement.status === "parsed"),
    [statementsPage],
  );

  const hasActiveFilters =
    Boolean(statementFilter) ||
    Boolean(fromFilter || toFilter) ||
    Boolean(categoryFilter) ||
    Boolean(directionFilter) ||
    Boolean(searchFilter) ||
    uncategorizedFilter;

  const uncategorizedCategoryId = categories.find(
    (c) => c.slug === "uncategorized",
  )?.id;

  const hasUncategorizedOnPage = useMemo(
    () =>
      (data?.results ?? []).some(
        (txn) =>
          !txn.category ||
          txn.category.slug === "uncategorized" ||
          txn.category.id === uncategorizedCategoryId,
      ),
    [data?.results, uncategorizedCategoryId],
  );

  const overrideMutation = useMutation({
    mutationFn: ({
      transactionId,
      categoryId,
    }: {
      transactionId: number;
      categoryId: number;
    }) => updateTransactionCategory(transactionId, categoryId),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ["transactions"] });
      queryClient.invalidateQueries({ queryKey: ["report"] });
    },
  });

  const recategorizeMutation = useMutation({
    mutationFn: () =>
      recategorizeTransactions({
        statement_id: statementFilter ? Number(statementFilter) : undefined,
      }),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ["transactions"] });
      queryClient.invalidateQueries({ queryKey: ["report"] });
      queryClient.invalidateQueries({ queryKey: ["insights"] });
      queryClient.invalidateQueries({ queryKey: ["report-summary"] });
    },
  });

  const aiCategorizeMutation = useMutation({
    mutationFn: () =>
      aiCategorizeTransactions({
        statement_id: statementFilter ? Number(statementFilter) : undefined,
      }),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ["transactions"] });
      queryClient.invalidateQueries({ queryKey: ["report"] });
      queryClient.invalidateQueries({ queryKey: ["insights"] });
    },
  });

  const aiResult = aiCategorizeMutation.data;
  const aiMessageTone =
    aiResult?.status === "ok" || aiResult?.status === "partial"
      ? "success"
      : aiResult?.status === "rate_limited"
        ? "warning"
        : "error";

  return (
    <div className="min-w-0 space-y-6">
      <div className="flex flex-wrap items-start justify-between gap-4">
        <div>
          <h1 className="text-2xl font-bold text-slate-900">Transactions</h1>
          <p className="mt-1 text-slate-600">
            Normalized transactions with explainable categories. Change a category
            to teach the app your preferences.
          </p>
        </div>
        <div className="flex flex-wrap gap-2">
          <button
            type="button"
            disabled={recategorizeMutation.isPending}
            onClick={() => recategorizeMutation.mutate()}
            className="rounded-md border border-violet-300 bg-white px-4 py-2 text-sm font-medium text-violet-700 hover:bg-violet-50 disabled:opacity-50"
          >
            {recategorizeMutation.isPending
              ? "Applying UPI notes..."
              : "Apply UPI notes"}
          </button>
          <button
            type="button"
            disabled={aiCategorizeMutation.isPending}
            onClick={() => aiCategorizeMutation.mutate()}
            className="rounded-md bg-violet-600 px-4 py-2 text-sm font-medium text-white hover:bg-violet-700 disabled:opacity-50"
          >
            {aiCategorizeMutation.isPending
              ? "AI categorizing..."
              : "AI categorize uncategorized"}
          </button>
        </div>
      </div>

      {recategorizeMutation.isSuccess && (
        <p className="text-sm text-green-700">
          {recategorizeMutation.data.message}
        </p>
      )}
      {recategorizeMutation.isError && (
        <p className="text-sm text-red-600">
          {(recategorizeMutation.error as Error).message}
        </p>
      )}

      {aiResult && (
        <p
          className={`text-sm ${
            aiMessageTone === "success"
              ? "text-green-700"
              : aiMessageTone === "warning"
                ? "text-amber-700"
                : "text-red-700"
          }`}
        >
          {aiResult.message}
          {aiResult.merchants_remaining > 0 && aiMessageTone === "success" && (
            <span> Click the button again to process the next batch.</span>
          )}
        </p>
      )}
      {aiCategorizeMutation.isError && (
        <p className="text-sm text-red-600">
          {(aiCategorizeMutation.error as Error).message}
        </p>
      )}

      <section className="rounded-xl border border-slate-200 bg-white p-4 shadow-sm">
        <div className="mb-3 flex flex-wrap items-center justify-between gap-2">
          <h2 className="text-sm font-semibold text-slate-900">Filters</h2>
          {hasActiveFilters && (
            <button
              type="button"
              onClick={() => {
                setSearchDraft("");
                setSearchParams({});
              }}
              className="text-xs font-medium text-brand-600 hover:underline"
            >
              Clear all filters
            </button>
          )}
        </div>
        <div className="grid gap-4 sm:grid-cols-2 lg:grid-cols-3">
          <div>
            <label htmlFor="month-filter" className="block text-sm font-medium text-slate-700">
              Month
            </label>
            <input
              id="month-filter"
              type="month"
              value={fromFilter && toFilter ? fromFilter.slice(0, 7) : ""}
              onChange={(e) => {
                const bounds = parseMonthInput(e.target.value);
                updateFilters({
                  from: bounds?.from ?? null,
                  to: bounds?.to ?? null,
                });
              }}
              className="mt-1 w-full rounded-md border border-slate-300 px-3 py-2 text-sm"
            />
          </div>
          <div>
            <label htmlFor="statement-filter" className="block text-sm font-medium text-slate-700">
              Statement
            </label>
            <select
              id="statement-filter"
              value={statementFilter}
              onChange={(e) =>
                updateFilters({ statement: e.target.value || null })
              }
              className="mt-1 w-full rounded-md border border-slate-300 px-3 py-2 text-sm"
            >
              <option value="">All statements</option>
              {parsedStatements.map((statement) => (
                <option key={statement.id} value={statement.id}>
                  #{statement.id} —{" "}
                  {formatPeriodLabel(
                    statement.period_start,
                    statement.period_end,
                    statement.original_filename,
                  )}
                </option>
              ))}
            </select>
          </div>
          <div>
            <label htmlFor="category-filter" className="block text-sm font-medium text-slate-700">
              Category
            </label>
            <select
              id="category-filter"
              value={categoryFilter}
              onChange={(e) =>
                updateFilters({ category: e.target.value || null })
              }
              className="mt-1 w-full rounded-md border border-slate-300 px-3 py-2 text-sm"
            >
              <option value="">All categories</option>
              {categories.map((cat) => (
                <option key={cat.id} value={cat.id}>
                  {cat.name}
                </option>
              ))}
            </select>
          </div>
          <div>
            <label htmlFor="direction-filter" className="block text-sm font-medium text-slate-700">
              Type
            </label>
            <select
              id="direction-filter"
              value={directionFilter}
              onChange={(e) =>
                updateFilters({ direction: e.target.value || null })
              }
              className="mt-1 w-full rounded-md border border-slate-300 px-3 py-2 text-sm"
            >
              <option value="">Credits & debits</option>
              <option value="credit">Credits only</option>
              <option value="debit">Debits only</option>
            </select>
          </div>
          <div className="sm:col-span-2 lg:col-span-2">
            <label htmlFor="search-filter" className="block text-sm font-medium text-slate-700">
              Search merchant or description
            </label>
            <input
              id="search-filter"
              type="search"
              placeholder="e.g. autopay, swiggy, UPI"
              value={searchDraft}
              onChange={(e) => setSearchDraft(e.target.value)}
              className="mt-1 w-full rounded-md border border-slate-300 px-3 py-2 text-sm"
            />
          </div>
          <div className="flex items-end">
            <label className="flex cursor-pointer items-center gap-2 text-sm text-slate-700">
              <input
                type="checkbox"
                checked={uncategorizedFilter}
                onChange={(e) =>
                  updateFilters({
                    uncategorized: e.target.checked ? "true" : null,
                  })
                }
                className="rounded border-slate-300"
              />
              Uncategorized only
            </label>
          </div>
        </div>
        {hasUncategorizedOnPage && (
          <p className="mt-2 text-xs text-amber-700">
            This page has uncategorized items — use AI categorize to resolve them
            in batches (one API call per group of merchants).
          </p>
        )}
      </section>

      {data?.stats && (
        <TransactionStatsBar stats={data.stats} />
      )}

      {overrideMutation.isError && (
        <p className="text-sm text-red-600">
          {(overrideMutation.error as Error).message}
        </p>
      )}

      {isLoading && <p className="text-sm text-slate-500">Loading transactions...</p>}

      {isError && (
        <p className="text-sm text-red-600">{(error as Error).message}</p>
      )}

      {!isLoading && data?.results.length === 0 && (
        <p className="text-sm text-slate-500">
          No transactions yet. Upload a statement to get started.
        </p>
      )}

      {!isLoading && data && data.results.length > 0 && (
        <div className="w-full max-w-full overflow-x-auto rounded-xl border border-slate-200 bg-white shadow-sm">
          <table className="w-full min-w-[62rem] table-fixed divide-y divide-slate-200 text-sm">
            <colgroup>
              <col className="w-[7rem]" />
              <col className="w-[9rem]" />
              <col />
              <col className="w-[7.5rem]" />
              <col className="w-[9rem]" />
              <col className="w-[11rem]" />
            </colgroup>
            <thead className="bg-slate-50">
              <tr>
                <th className="whitespace-nowrap px-4 py-3 text-left font-medium text-slate-600">
                  Date
                </th>
                <th className="px-4 py-3 text-left font-medium text-slate-600">
                  Merchant
                </th>
                <th className="px-4 py-3 text-left font-medium text-slate-600">
                  Description
                </th>
                <th className="whitespace-nowrap px-4 py-3 text-right font-medium text-slate-600">
                  Amount
                </th>
                <th className="whitespace-nowrap px-4 py-3 text-right font-medium text-slate-600">
                  Balance
                </th>
                <th className="whitespace-nowrap px-4 py-3 text-left font-medium text-slate-600">
                  Category
                </th>
              </tr>
            </thead>
            <tbody className="divide-y divide-slate-100">
              {data.results.map((txn) => (
                <tr key={txn.id} className="hover:bg-slate-50">
                  <td className="whitespace-nowrap px-4 py-3 text-slate-900">
                    {formatDate(txn.transaction_date)}
                  </td>
                  <td className="px-4 py-3 text-slate-900">
                    <div
                      className="max-w-[8rem] break-words text-sm leading-snug"
                      title={txn.normalized_merchant || undefined}
                    >
                      {txn.normalized_merchant || "—"}
                    </div>
                    {txn.is_recurring && (
                      <span className="mt-1 inline-block rounded bg-violet-100 px-1.5 py-0.5 text-xs text-violet-700">
                        Recurring
                      </span>
                    )}
                  </td>
                  <td className="px-4 py-3 text-slate-600">
                    <NarrationCell raw={txn.raw_description} />
                  </td>
                  <td
                    className={`${AMOUNT_CELL_CLASS} font-medium ${
                      Number(txn.amount) < 0 ? "text-red-700" : "text-green-700"
                    }`}
                  >
                    {formatAmount(txn.amount)}
                  </td>
                  <td className={`${BALANCE_CELL_CLASS} text-slate-600`}>
                    {txn.balance ? formatAmount(txn.balance) : "—"}
                  </td>
                  <CategoryCell
                    txn={txn}
                    categories={categories}
                    isUpdating={
                      overrideMutation.isPending &&
                      overrideMutation.variables?.transactionId === txn.id
                    }
                    onUpdate={(categoryId) =>
                      overrideMutation.mutate({
                        transactionId: txn.id,
                        categoryId,
                      })
                    }
                  />
                </tr>
              ))}
            </tbody>
          </table>
          <PaginationControls
            page={data}
            currentPage={page}
            pageSize={pageSize}
            onPageChange={setPage}
            onPageSizeChange={setPageSize}
          />
        </div>
      )}
    </div>
  );
}
