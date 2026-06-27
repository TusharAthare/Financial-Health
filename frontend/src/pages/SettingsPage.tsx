import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { useState } from "react";
import { useNavigate } from "react-router-dom";

import { deleteMyData, fetchAuditLog } from "@/lib/core-api";

const DELETE_PHRASE = "DELETE_MY_DATA";

export function SettingsPage() {
  const navigate = useNavigate();
  const queryClient = useQueryClient();
  const [confirmation, setConfirmation] = useState("");
  const [showDeleteConfirm, setShowDeleteConfirm] = useState(false);

  const { data: auditLog = [], isLoading: auditLoading } = useQuery({
    queryKey: ["audit-log"],
    queryFn: () => fetchAuditLog(30),
  });

  const deleteMutation = useMutation({
    mutationFn: deleteMyData,
    onSuccess: () => {
      queryClient.clear();
      navigate("/dashboard");
    },
  });

  const canDelete = confirmation === DELETE_PHRASE;

  return (
    <div className="space-y-8">
      <div>
        <h1 className="text-2xl font-bold text-slate-900">Settings</h1>
        <p className="mt-1 text-slate-600">
          Privacy controls, audit history, and data deletion.
        </p>
      </div>

      <section className="rounded-xl border border-slate-200 bg-white p-6 shadow-sm">
        <h2 className="text-lg font-semibold text-slate-900">Audit log</h2>
        <p className="mt-1 text-sm text-slate-500">
          Recent uploads, exports, and deletions on your account.
        </p>

        {auditLoading && (
          <p className="mt-4 text-sm text-slate-500">Loading audit log...</p>
        )}

        {!auditLoading && auditLog.length === 0 && (
          <p className="mt-4 text-sm text-slate-500">No audit events yet.</p>
        )}

        {auditLog.length > 0 && (
          <ul className="mt-4 divide-y divide-slate-100">
            {auditLog.map((entry) => (
              <li key={entry.id} className="py-3 text-sm">
                <div className="flex flex-wrap items-center justify-between gap-2">
                  <span className="font-medium capitalize text-slate-900">
                    {entry.action.replace(/_/g, " ")}
                  </span>
                  <time className="text-slate-500">
                    {new Date(entry.created_at).toLocaleString("en-IN")}
                  </time>
                </div>
                {entry.target_type && (
                  <p className="mt-1 text-slate-500">
                    {entry.target_type}
                    {entry.target_id ? ` #${entry.target_id}` : ""}
                  </p>
                )}
              </li>
            ))}
          </ul>
        )}
      </section>

      <section className="rounded-xl border border-red-200 bg-red-50 p-6">
        <h2 className="text-lg font-semibold text-red-900">Delete my data</h2>
        <p className="mt-2 text-sm text-red-800">
          Permanently remove all statements, transactions, reports, recurring patterns,
          and custom categories. Your login account remains, but all financial data
          will be erased. This cannot be undone.
        </p>

        {!showDeleteConfirm ? (
          <button
            type="button"
            onClick={() => setShowDeleteConfirm(true)}
            className="mt-4 rounded-md bg-red-600 px-4 py-2 text-sm font-medium text-white hover:bg-red-700"
          >
            Delete all my data
          </button>
        ) : (
          <div className="mt-4 space-y-3">
            <label htmlFor="delete-confirm" className="block text-sm text-red-900">
              Type <strong>{DELETE_PHRASE}</strong> to confirm
            </label>
            <input
              id="delete-confirm"
              type="text"
              value={confirmation}
              onChange={(event) => setConfirmation(event.target.value)}
              className="w-full max-w-md rounded-md border border-red-300 px-3 py-2 text-sm"
              placeholder={DELETE_PHRASE}
            />
            <div className="flex gap-3">
              <button
                type="button"
                disabled={!canDelete || deleteMutation.isPending}
                onClick={() => deleteMutation.mutate()}
                className="rounded-md bg-red-600 px-4 py-2 text-sm font-medium text-white hover:bg-red-700 disabled:opacity-50"
              >
                {deleteMutation.isPending ? "Deleting..." : "Confirm deletion"}
              </button>
              <button
                type="button"
                onClick={() => {
                  setShowDeleteConfirm(false);
                  setConfirmation("");
                }}
                className="rounded-md border border-slate-300 px-4 py-2 text-sm text-slate-700 hover:bg-white"
              >
                Cancel
              </button>
            </div>
            {deleteMutation.isError && (
              <p className="text-sm text-red-700">
                {(deleteMutation.error as Error).message}
              </p>
            )}
          </div>
        )}
      </section>
    </div>
  );
}
