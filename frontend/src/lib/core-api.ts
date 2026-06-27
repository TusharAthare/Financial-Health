import { apiFetch } from "@/lib/api-client";
import type { AuditLogEntry, DeleteDataResponse } from "@/types/api";

export async function fetchAuditLog(limit = 50): Promise<AuditLogEntry[]> {
  return apiFetch<AuditLogEntry[]>(`/api/core/audit/?limit=${limit}`);
}

export async function deleteMyData(): Promise<DeleteDataResponse> {
  return apiFetch<DeleteDataResponse>("/api/core/me/data/", {
    method: "DELETE",
    body: JSON.stringify({ confirmation: "DELETE_MY_DATA" }),
  });
}
