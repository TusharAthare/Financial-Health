export interface User {
  id: number;
  email: string;
  first_name: string;
  last_name: string;
  full_name: string;
  created_at: string;
}

export interface AuthTokens {
  access: string;
  refresh: string;
}

export interface RegisterPayload {
  email: string;
  password: string;
  first_name?: string;
  last_name?: string;
}

export interface LoginPayload {
  email: string;
  password: string;
}

export interface Account {
  id: number;
  bank_name: string;
  masked_number: string;
  currency: string;
  created_at: string;
  updated_at: string;
}

export type StatementStatus = "uploaded" | "parsing" | "parsed" | "failed";

export interface Statement {
  id: number;
  account_id: number;
  account_bank_name: string;
  period_start: string | null;
  period_end: string | null;
  original_filename: string;
  file_format: string;
  status: StatementStatus;
  checksum: string;
  error_message: string;
  transaction_count: number;
  created_at: string;
  updated_at: string;
}

export interface Category {
  id: number;
  name: string;
  slug: string;
}

export interface CategoryRuleSummary {
  id: number;
  pattern: string;
  rule_type: string;
  priority: number;
}

export interface CategorizationEvidence {
  rule_id?: number;
  rule_pattern?: string;
  rule_type?: string;
  matched_field?: string;
  matched_text?: string;
  source?: string;
  reason?: string;
  fallback?: string;
  model?: string;
  merchant_key?: string;
  category_slug?: string;
  upi_remark?: string;
}

export interface Transaction {
  id: number;
  account_id: number;
  statement_id: number;
  transaction_date: string;
  amount: string;
  raw_description: string;
  normalized_merchant: string;
  balance: string | null;
  category: Category | null;
  matched_rule: CategoryRuleSummary | null;
  categorization_evidence: CategorizationEvidence;
  is_recurring: boolean;
  created_at: string;
}

export type RecurringPatternType = "subscription" | "autopay" | "emi" | "loan";
export type RecurringCadence = "weekly" | "biweekly" | "monthly" | "quarterly";

export interface RecurringPatternEvidence {
  transaction_ids?: number[];
  occurrences?: number;
  avg_gap_days?: number;
  cadence_detected?: string;
  amount_mean?: string;
  amount_std_pct?: number;
  classification_signals?: string[];
}

export interface RecurringPattern {
  id: number;
  normalized_merchant: string;
  pattern_type: RecurringPatternType;
  cadence: RecurringCadence;
  expected_amount: string;
  amount_variance_pct: number;
  next_expected_date: string | null;
  evidence: RecurringPatternEvidence;
  is_active: boolean;
  created_at: string;
  updated_at: string;
}

export interface PaginatedResponse<T> {
  count: number;
  next: string | null;
  previous: string | null;
  results: T[];
}

export interface TransactionListStats {
  transaction_count: number;
  credited_count: number;
  debited_count: number;
  credited_total: string;
  debited_total: string;
  net_total: string;
}

export interface TransactionPaginatedResponse extends PaginatedResponse<Transaction> {
  stats?: TransactionListStats;
}

export interface ApiError {
  error: {
    code: string;
    message: string;
    details?: Record<string, string[]>;
  };
}

export interface CategoryTotal {
  category_id: number | null;
  category_name: string;
  category_slug: string;
  total: string;
  transaction_count: number;
}

export interface ReportAggregates {
  income: string;
  expense: string;
  net_cash_flow: string;
  savings_rate: number | null;
  transaction_count: number;
  category_totals: CategoryTotal[];
  emi_total: string;
  subscription_total: string;
  recurring_debit_total: string;
}

export interface Report {
  id: number;
  statement_id: number;
  account_bank_name: string;
  original_filename: string;
  period_start: string | null;
  period_end: string | null;
  aggregates: ReportAggregates;
  created_at: string;
  updated_at: string;
}

export interface ReportSummaryItem {
  statement_id: number;
  period_start: string | null;
  period_end: string | null;
  original_filename: string;
  income: string;
  expense: string;
  net_cash_flow: string;
  savings_rate: number | null;
  emi_total: string;
  subscription_total: string;
  emi_burden_pct: number | null;
  category_drift: CategoryDriftItem[];
}

export interface CategoryDriftItem {
  category_slug: string;
  category_name: string;
  current_total: string;
  prior_total: string;
  change_pct: number | null;
}

export type ExportJobStatus = "pending" | "processing" | "completed" | "failed";

export interface ExportJob {
  id: number;
  statement_id: number;
  export_format: "csv" | "pdf";
  status: ExportJobStatus;
  error_message: string;
  created_at: string;
  updated_at: string;
}

export interface AuditLogEntry {
  id: number;
  action: string;
  target_type: string;
  target_id: string;
  metadata: Record<string, unknown>;
  created_at: string;
}

export interface DeleteDataResponse {
  message: string;
  deleted: {
    statements_deleted: number;
    accounts_deleted: number;
    recurring_patterns_deleted: number;
    category_rules_deleted: number;
    custom_categories_deleted: number;
    export_jobs_deleted: number;
  };
}

export type InsightType = "leak" | "saving" | "suggestion";

export interface InsightEvidence {
  rule?: string;
  savings_rate?: number;
  threshold_pct?: number;
  income?: string;
  expense?: string;
  net_cash_flow?: string;
  emi_total?: string;
  emi_pct_of_income?: number;
  merchants?: string[];
  subscription_total?: string;
  current_expense?: string;
  prior_expense?: string;
  increase_pct?: number;
  decrease_pct?: number;
  category_slug?: string;
  category_name?: string;
  current_total?: string;
  prior_total?: string;
  [key: string]: unknown;
}

export interface Insight {
  id: number;
  statement_id: number;
  insight_type: InsightType;
  priority: number;
  title: string;
  message: string;
  evidence: InsightEvidence;
  period_start: string | null;
  period_end: string | null;
  created_at: string;
}
