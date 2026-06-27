import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { useCallback, useMemo, useState } from "react";
import { Link } from "react-router-dom";

import { ApiClientError } from "@/lib/api-client";
import { createAccount, fetchAccounts } from "@/lib/auth-api";
import {
  pollStatementUntilDone,
  uploadStatement,
} from "@/lib/statements-api";
import type { Statement } from "@/types/api";

const ACCEPTED_EXTENSIONS = [".pdf", ".xls", ".xlsx", ".csv"] as const;
const ACCEPTED_MIME_TYPES =
  "application/pdf,.pdf,application/vnd.ms-excel,.xls,application/vnd.openxmlformats-officedocument.spreadsheetml.sheet,.xlsx,text/csv,.csv";

function isPdfFile(file: File): boolean {
  return file.name.toLowerCase().endsWith(".pdf");
}

function isAcceptedFile(file: File): boolean {
  const lower = file.name.toLowerCase();
  return ACCEPTED_EXTENSIONS.some((ext) => lower.endsWith(ext));
}

function StatusBadge({ status }: { status: Statement["status"] }) {
  const styles: Record<Statement["status"], string> = {
    uploaded: "bg-slate-100 text-slate-700",
    parsing: "bg-amber-100 text-amber-800",
    parsed: "bg-green-100 text-green-800",
    failed: "bg-red-100 text-red-800",
  };

  return (
    <span className={`rounded-full px-2.5 py-0.5 text-xs font-medium ${styles[status]}`}>
      {status}
    </span>
  );
}

export function UploadPage() {
  const queryClient = useQueryClient();
  const [accountId, setAccountId] = useState<number | "">("");
  const [file, setFile] = useState<File | null>(null);
  const [pdfPassword, setPdfPassword] = useState("");
  const [activeStatement, setActiveStatement] = useState<Statement | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [isPolling, setIsPolling] = useState(false);

  const [newBank, setNewBank] = useState("");
  const [newMasked, setNewMasked] = useState("");

  const showPdfPassword = useMemo(
    () => file !== null && isPdfFile(file),
    [file],
  );

  const { data: accounts, isLoading: accountsLoading } = useQuery({
    queryKey: ["accounts"],
    queryFn: fetchAccounts,
  });

  const createAccountMutation = useMutation({
    mutationFn: createAccount,
    onSuccess: (account) => {
      queryClient.invalidateQueries({ queryKey: ["accounts"] });
      setAccountId(account.id);
      setNewBank("");
      setNewMasked("");
    },
  });

  const handleFileChange = useCallback(
    (nextFile: File | null) => {
      if (nextFile && !isAcceptedFile(nextFile)) {
        setError("Please choose a PDF, XLS, XLSX, or CSV bank statement.");
        setFile(null);
        return;
      }
      setError(null);
      setFile(nextFile);
      if (!nextFile || !isPdfFile(nextFile)) {
        setPdfPassword("");
      }
    },
    [],
  );

  const handleUpload = useCallback(async () => {
    if (!file || accountId === "") {
      setError("Select an account and a statement file (PDF, XLS, XLSX, or CSV).");
      return;
    }

    setError(null);
    setIsPolling(true);
    setActiveStatement(null);

    try {
      const statement = await uploadStatement(accountId, file, {
        pdfPassword: showPdfPassword ? pdfPassword : undefined,
      });
      setActiveStatement(statement);

      if (statement.status === "parsed" || statement.status === "failed") {
        queryClient.invalidateQueries({ queryKey: ["transactions"] });
        queryClient.invalidateQueries({ queryKey: ["statements"] });
        return;
      }

      const finalStatement = await pollStatementUntilDone(
        statement.id,
        setActiveStatement,
      );
      setActiveStatement(finalStatement);
      queryClient.invalidateQueries({ queryKey: ["transactions"] });
      queryClient.invalidateQueries({ queryKey: ["statements"] });
    } catch (err) {
      const message =
        err instanceof ApiClientError
          ? err.message
          : err instanceof Error
            ? err.message
            : "Upload failed.";
      setError(message);
    } finally {
      setIsPolling(false);
    }
  }, [accountId, file, pdfPassword, queryClient, showPdfPassword]);

  return (
    <div className="space-y-6">
      <div>
        <h1 className="text-2xl font-bold text-slate-900">Upload statement</h1>
        <p className="mt-1 text-slate-600">
          Upload a bank statement as PDF, XLS, XLSX, or CSV. Parsing runs in the
          background.
        </p>
        <p className="mt-1 text-sm text-slate-500">
          Supported PDF banks: HDFC, ICICI. Excel and CSV use standard
          Date / Description / Debit / Credit columns.
        </p>
      </div>

      {accountsLoading && (
        <p className="text-sm text-slate-500">Loading accounts...</p>
      )}

      {!accountsLoading && accounts?.length === 0 && (
        <section className="rounded-xl border border-slate-200 bg-white p-6 shadow-sm">
          <h2 className="text-lg font-semibold text-slate-900">Add a bank account</h2>
          <p className="mt-1 text-sm text-slate-600">
            You need at least one account before uploading statements.
          </p>
          <div className="mt-4 grid gap-4 sm:grid-cols-2">
            <input
              type="text"
              placeholder="Bank name"
              value={newBank}
              onChange={(e) => setNewBank(e.target.value)}
              className="rounded-md border border-slate-300 px-3 py-2 text-sm"
            />
            <input
              type="text"
              placeholder="Masked number (e.g. XXXX1234)"
              value={newMasked}
              onChange={(e) => setNewMasked(e.target.value)}
              className="rounded-md border border-slate-300 px-3 py-2 text-sm"
            />
          </div>
          <button
            type="button"
            disabled={createAccountMutation.isPending}
            onClick={() =>
              createAccountMutation.mutate({
                bank_name: newBank,
                masked_number: newMasked,
              })
            }
            className="mt-4 rounded-md bg-brand-600 px-4 py-2 text-sm font-medium text-white hover:bg-brand-700 disabled:opacity-50"
          >
            {createAccountMutation.isPending ? "Creating..." : "Create account"}
          </button>
          {createAccountMutation.isError && (
            <p className="mt-2 text-sm text-red-600">
              {(createAccountMutation.error as Error).message}
            </p>
          )}
        </section>
      )}

      {!accountsLoading && accounts && accounts.length > 0 && (
        <section className="rounded-xl border border-slate-200 bg-white p-6 shadow-sm">
          <div className="grid gap-4 sm:grid-cols-2">
            <div>
              <label htmlFor="account" className="block text-sm font-medium text-slate-700">
                Bank account
              </label>
              <select
                id="account"
                value={accountId}
                onChange={(e) =>
                  setAccountId(e.target.value ? Number(e.target.value) : "")
                }
                className="mt-1 w-full rounded-md border border-slate-300 px-3 py-2 text-sm"
              >
                <option value="">Select account</option>
                {accounts.map((account) => (
                  <option key={account.id} value={account.id}>
                    {account.bank_name} ({account.masked_number})
                  </option>
                ))}
              </select>
            </div>

            <div>
              <label
                htmlFor="statement-file"
                className="block text-sm font-medium text-slate-700"
              >
                Statement file
              </label>
              <input
                id="statement-file"
                type="file"
                accept={ACCEPTED_MIME_TYPES}
                onChange={(e) => handleFileChange(e.target.files?.[0] ?? null)}
                className="mt-1 w-full text-sm text-slate-600 file:mr-3 file:rounded-md file:border-0 file:bg-brand-50 file:px-3 file:py-1.5 file:text-sm file:font-medium file:text-brand-700 hover:file:bg-brand-100"
              />
              <p className="mt-1 text-xs text-slate-500">PDF, XLS, XLSX, or CSV</p>
            </div>
          </div>

          {showPdfPassword && (
            <div className="mt-4">
              <label
                htmlFor="pdf-password"
                className="block text-sm font-medium text-slate-700"
              >
                PDF password (optional)
              </label>
              <input
                id="pdf-password"
                type="password"
                autoComplete="off"
                placeholder="Only if your bank PDF is password-protected"
                value={pdfPassword}
                onChange={(e) => setPdfPassword(e.target.value)}
                className="mt-1 w-full max-w-md rounded-md border border-slate-300 px-3 py-2 text-sm"
              />
            </div>
          )}

          <button
            type="button"
            disabled={isPolling || !file || accountId === ""}
            onClick={() => void handleUpload()}
            className="mt-6 rounded-md bg-brand-600 px-4 py-2 text-sm font-medium text-white hover:bg-brand-700 disabled:opacity-50"
          >
            {isPolling ? "Processing..." : "Upload & parse"}
          </button>

          {error && (
            <p className="mt-4 rounded-md bg-red-50 px-3 py-2 text-sm text-red-700">
              {error}
            </p>
          )}
        </section>
      )}

      {activeStatement && (
        <section className="rounded-xl border border-slate-200 bg-white p-6 shadow-sm">
          <div className="flex items-center justify-between">
            <h2 className="text-lg font-semibold text-slate-900">Parse status</h2>
            <StatusBadge status={activeStatement.status} />
          </div>
          <dl className="mt-4 grid gap-2 text-sm sm:grid-cols-2">
            <div>
              <dt className="text-slate-500">File</dt>
              <dd className="font-medium text-slate-900">
                {activeStatement.original_filename}
              </dd>
            </div>
            <div>
              <dt className="text-slate-500">Format</dt>
              <dd className="font-medium uppercase text-slate-900">
                {activeStatement.file_format}
              </dd>
            </div>
            <div>
              <dt className="text-slate-500">Transactions imported</dt>
              <dd className="font-medium text-slate-900">
                {activeStatement.transaction_count}
              </dd>
            </div>
          </dl>

          {activeStatement.status === "failed" && activeStatement.error_message && (
            <p className="mt-4 rounded-md bg-red-50 px-3 py-2 text-sm text-red-700">
              {activeStatement.error_message}
            </p>
          )}

          {activeStatement.status === "parsed" && (
            <Link
              to={`/transactions?statement=${activeStatement.id}`}
              className="mt-4 inline-block text-sm font-medium text-brand-700 hover:text-brand-800"
            >
              View imported transactions →
            </Link>
          )}
        </section>
      )}
    </div>
  );
}
