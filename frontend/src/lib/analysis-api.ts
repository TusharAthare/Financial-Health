import { apiFetch, getAccessToken, getRefreshToken, setTokens } from "@/lib/api-client";
import type { ExportJob, Insight, RecurringPattern, Report, ReportSummaryItem } from "@/types/api";

export async function fetchRecurringPatterns(): Promise<RecurringPattern[]> {
  return apiFetch<RecurringPattern[]>("/api/analysis/recurring/");
}

export async function fetchReport(statementId: number): Promise<Report> {
  return apiFetch<Report>(`/api/analysis/reports/${statementId}/`);
}

export async function fetchReportSummary(): Promise<ReportSummaryItem[]> {
  return apiFetch<ReportSummaryItem[]>("/api/analysis/reports/summary/");
}

export interface MonthlyMonthOption {
  year: number;
  month: number;
  label: string;
  transaction_count: number;
  period_start: string;
  period_end: string;
}

export interface MonthlyGeneratedInsight {
  insight_type: Insight["insight_type"];
  priority: number;
  title: string;
  message: string;
  evidence: Insight["evidence"];
}

export interface MonthlySummary {
  year: number;
  month: number;
  label: string;
  period_start: string;
  period_end: string;
  aggregates: Report["aggregates"];
  insights: MonthlyGeneratedInsight[];
}

export async function fetchAvailableMonths(): Promise<MonthlyMonthOption[]> {
  return apiFetch<MonthlyMonthOption[]>("/api/analysis/reports/months/");
}

export async function fetchMonthlySummary(
  year: number,
  month: number,
): Promise<MonthlySummary> {
  const search = new URLSearchParams({
    year: String(year),
    month: String(month),
  });
  return apiFetch<MonthlySummary>(`/api/analysis/reports/monthly/?${search}`);
}

export async function fetchInsights(statementId?: number): Promise<Insight[]> {
  const path = statementId
    ? `/api/analysis/insights/?statement=${statementId}`
    : "/api/analysis/insights/";
  return apiFetch<Insight[]>(path);
}

export async function createReportExport(
  statementId: number,
  format: "csv" | "pdf",
): Promise<ExportJob> {
  return apiFetch<ExportJob>(`/api/analysis/reports/${statementId}/export/`, {
    method: "POST",
    body: JSON.stringify({ format }),
  });
}

export async function fetchExportJob(jobId: number): Promise<ExportJob> {
  return apiFetch<ExportJob>(`/api/analysis/exports/${jobId}/`);
}

export async function downloadExportJob(jobId: number): Promise<void> {
  const headers: HeadersInit = {};
  const token = getAccessToken();
  if (token) {
    headers.Authorization = `Bearer ${token}`;
  }

  let response = await fetch(`/api/analysis/exports/${jobId}/download/`, {
    headers,
  });

  if (response.status === 401 && getRefreshToken()) {
    const refresh = getRefreshToken()!;
    const refreshResponse = await fetch("/api/refresh-token/", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ refresh }),
    });
    if (refreshResponse.ok) {
      const data = (await refreshResponse.json()) as { access: string; refresh?: string };
      setTokens(data.access, data.refresh ?? refresh);
      headers.Authorization = `Bearer ${data.access}`;
      response = await fetch(`/api/analysis/exports/${jobId}/download/`, { headers });
    }
  }

  if (!response.ok) {
    const body = await response.json();
    throw new Error(body?.error?.message ?? "Export download failed.");
  }

  const blob = await response.blob();
  const disposition = response.headers.get("Content-Disposition") ?? "";
  const match = disposition.match(/filename="?([^"]+)"?/);
  const filename = match?.[1] ?? `export-${jobId}`;

  const url = URL.createObjectURL(blob);
  const anchor = document.createElement("a");
  anchor.href = url;
  anchor.download = filename;
  anchor.click();
  URL.revokeObjectURL(url);
}

export async function pollAndDownloadExport(
  jobId: number,
  maxAttempts = 20,
): Promise<void> {
  for (let attempt = 0; attempt < maxAttempts; attempt += 1) {
    const job = await fetchExportJob(jobId);
    if (job.status === "completed") {
      await downloadExportJob(jobId);
      return;
    }
    if (job.status === "failed") {
      throw new Error(job.error_message || "Export failed.");
    }
    await new Promise((resolve) => setTimeout(resolve, 500));
  }
  throw new Error("Export timed out. Try again later.");
}
