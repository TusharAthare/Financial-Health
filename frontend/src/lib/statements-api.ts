import { apiFetch } from "@/lib/api-client";
import type {
  Category,
  PaginatedResponse,
  Statement,
  StatementStatus,
  Transaction,
  TransactionPaginatedResponse,
} from "@/types/api";

export async function fetchCategories(): Promise<Category[]> {
  return apiFetch<Category[]>("/api/statements/categories/");
}

export async function updateTransactionCategory(
  transactionId: number,
  categoryId: number,
): Promise<Transaction> {
  return apiFetch<Transaction>(`/api/statements/transactions/${transactionId}/`, {
    method: "PATCH",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ category_id: categoryId }),
  });
}

export async function fetchStatements(params?: {
  page?: number;
  page_size?: number;
}): Promise<PaginatedResponse<Statement>> {
  const search = new URLSearchParams();
  if (params?.page) search.set("page", String(params.page));
  if (params?.page_size) search.set("page_size", String(params.page_size));
  const query = search.toString();
  const path = query ? `/api/statements/?${query}` : "/api/statements/";
  return apiFetch<PaginatedResponse<Statement>>(path);
}

export async function fetchStatement(id: number): Promise<Statement> {
  return apiFetch<Statement>(`/api/statements/${id}/`);
}

export async function uploadStatement(
  accountId: number,
  file: File,
  options?: { pdfPassword?: string },
): Promise<Statement> {
  const formData = new FormData();
  formData.append("account_id", String(accountId));
  formData.append("file", file);
  if (options?.pdfPassword) {
    formData.append("pdf_password", options.pdfPassword);
  }

  return apiFetch<Statement>("/api/statements/", {
    method: "POST",
    body: formData,
  });
}

export async function fetchTransactions(params?: {
  statement?: number;
  category?: number;
  from?: string;
  to?: string;
  direction?: "credit" | "debit";
  search?: string;
  uncategorized?: boolean;
  page?: number;
  page_size?: number;
}): Promise<TransactionPaginatedResponse> {
  const search = new URLSearchParams();
  if (params?.statement) search.set("statement", String(params.statement));
  if (params?.category) search.set("category", String(params.category));
  if (params?.from) search.set("from", params.from);
  if (params?.to) search.set("to", params.to);
  if (params?.direction) search.set("direction", params.direction);
  if (params?.search) search.set("search", params.search);
  if (params?.uncategorized) search.set("uncategorized", "true");
  if (params?.page) search.set("page", String(params.page));
  if (params?.page_size) search.set("page_size", String(params.page_size));

  const query = search.toString();
  const path = query
    ? `/api/statements/transactions/?${query}`
    : "/api/statements/transactions/";

  return apiFetch<TransactionPaginatedResponse>(path);
}

export async function recategorizeTransactions(params?: {
  statement_id?: number;
}): Promise<{ updated: number; message: string }> {
  return apiFetch<{ updated: number; message: string }>(
    "/api/statements/transactions/recategorize/",
    {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(
        params?.statement_id ? { statement_id: params.statement_id } : {},
      ),
    },
  );
}

export async function aiCategorizeTransactions(params?: {
  statement_id?: number;
}): Promise<AiCategorizeResult> {
  return apiFetch<AiCategorizeResult>("/api/statements/transactions/ai-categorize/", {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(
      params?.statement_id ? { statement_id: params.statement_id } : {},
    ),
  });
}

export interface AiCategorizeResult {
  updated: number;
  status: string;
  message: string;
  merchants_total: number;
  merchants_processed: number;
  merchants_remaining: number;
  batches_run: number;
}

export function isStatementTerminal(status: StatementStatus): boolean {
  return status === "parsed" || status === "failed";
}

export async function pollStatementUntilDone(
  id: number,
  onUpdate?: (statement: Statement) => void,
  intervalMs = 1500,
  maxAttempts = 120,
): Promise<Statement> {
  for (let attempt = 0; attempt < maxAttempts; attempt += 1) {
    const statement = await fetchStatement(id);
    onUpdate?.(statement);
    if (isStatementTerminal(statement.status)) {
      return statement;
    }
    await new Promise((resolve) => setTimeout(resolve, intervalMs));
  }
  throw new Error("Timed out waiting for statement parsing.");
}
