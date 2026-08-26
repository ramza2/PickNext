import { ApiError, apiRequest, messageFromDetail } from "./client";

const API_BASE_URL = (
  import.meta.env.VITE_API_BASE_URL || "/api/v1"
).replace(/\/$/, "");

export interface DatabaseMaintenanceStatus {
  enabled: boolean;
  authorized: boolean;
  postgres_major?: number | null;
  alembic_revision?: string | null;
  backup_available: boolean;
  restore_available: boolean;
  max_upload_bytes?: number | null;
}

export interface RestoreInspectResponse {
  restore_token: string;
  expires_at: string;
  compatible: boolean;
  backup: {
    created_at?: string;
    postgres_major?: number;
    alembic_revision?: string;
    counts?: Record<string, number>;
  };
  current: {
    postgres_major?: number;
    alembic_revision?: string;
  };
  warnings: string[];
}

export interface RestoreExecuteResponse {
  status: string;
  require_relogin: boolean;
  safety_backup?: string | null;
  counts?: Record<string, number> | null;
}

export function getDatabaseMaintenanceStatus(
  signal?: AbortSignal,
): Promise<DatabaseMaintenanceStatus> {
  return apiRequest<DatabaseMaintenanceStatus>("/settings/database-maintenance", {
    signal,
  });
}

export async function downloadDatabaseBackup(signal?: AbortSignal): Promise<void> {
  const url = `${API_BASE_URL}/settings/database-backup`;
  let response: Response;
  try {
    response = await fetch(url, {
      method: "POST",
      credentials: "include",
      signal,
    });
  } catch (err) {
    throw new ApiError(0, "Network error", err);
  }
  if (!response.ok) {
    let detail: unknown;
    try {
      const body = await response.json();
      detail = body?.detail ?? body;
    } catch {
      detail = undefined;
    }
    throw new ApiError(
      response.status,
      messageFromDetail(detail, `Backup failed (${response.status})`),
      detail,
    );
  }
  const blob = await response.blob();
  const disposition = response.headers.get("Content-Disposition") || "";
  const match = /filename=\"?([^\";]+)\"?/i.exec(disposition);
  const filename = match?.[1] || "picknext-backup.zip";
  const objectUrl = URL.createObjectURL(blob);
  const anchor = document.createElement("a");
  anchor.href = objectUrl;
  anchor.download = filename;
  document.body.appendChild(anchor);
  anchor.click();
  anchor.remove();
  URL.revokeObjectURL(objectUrl);
}

export async function inspectDatabaseRestore(
  file: File,
  signal?: AbortSignal,
): Promise<RestoreInspectResponse> {
  const body = new FormData();
  body.append("file", file);
  const url = `${API_BASE_URL}/settings/database-restore/inspect`;
  let response: Response;
  try {
    response = await fetch(url, {
      method: "POST",
      credentials: "include",
      body,
      signal,
    });
  } catch (err) {
    throw new ApiError(0, "Network error", err);
  }
  if (!response.ok) {
    let detail: unknown;
    try {
      const parsed = await response.json();
      detail = parsed?.detail ?? parsed;
    } catch {
      detail = undefined;
    }
    throw new ApiError(
      response.status,
      messageFromDetail(detail, `Inspect failed (${response.status})`),
      detail,
    );
  }
  return (await response.json()) as RestoreInspectResponse;
}

export function executeDatabaseRestore(
  payload: {
    restore_token: string;
    confirmation: string;
    current_password: string;
  },
  signal?: AbortSignal,
): Promise<RestoreExecuteResponse> {
  return apiRequest<RestoreExecuteResponse>("/settings/database-restore/execute", {
    method: "POST",
    body: JSON.stringify(payload),
    signal,
  });
}
