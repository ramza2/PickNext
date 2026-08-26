import { useEffect, useRef, useState } from "react";
import { Download, Upload } from "lucide-react";
import {
  downloadDatabaseBackup,
  executeDatabaseRestore,
  getDatabaseMaintenanceStatus,
  inspectDatabaseRestore,
  type DatabaseMaintenanceStatus,
  type RestoreInspectResponse,
} from "../../api/databaseMaintenance";
import { ApiError } from "../../api/client";

function formatCount(value: number | undefined): string {
  if (value == null) return "—";
  return value.toLocaleString("ko-KR");
}

export function DatabaseMaintenanceSection({
  showToast,
  onRestoreCompleted,
}: {
  showToast: (message: string) => void;
  onRestoreCompleted: () => void;
}) {
  const [status, setStatus] = useState<DatabaseMaintenanceStatus | null>(null);
  const [loadingStatus, setLoadingStatus] = useState(true);
  const [backupPending, setBackupPending] = useState(false);
  const [inspectPending, setInspectPending] = useState(false);
  const [executePending, setExecutePending] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [inspect, setInspect] = useState<RestoreInspectResponse | null>(null);
  const [showConfirm, setShowConfirm] = useState(false);
  const [confirmation, setConfirmation] = useState("");
  const [password, setPassword] = useState("");
  const fileRef = useRef<HTMLInputElement>(null);

  useEffect(() => {
    const controller = new AbortController();
    void (async () => {
      setLoadingStatus(true);
      try {
        const next = await getDatabaseMaintenanceStatus(controller.signal);
        if (!controller.signal.aborted) setStatus(next);
      } catch {
        if (!controller.signal.aborted) {
          setStatus({
            enabled: false,
            authorized: false,
            backup_available: false,
            restore_available: false,
          });
        }
      } finally {
        if (!controller.signal.aborted) setLoadingStatus(false);
      }
    })();
    return () => controller.abort();
  }, []);

  useEffect(() => {
    if (!showConfirm || !executePending) return;
    const onKeyDown = (event: KeyboardEvent) => {
      if (event.key === "Escape") {
        event.preventDefault();
        event.stopPropagation();
      }
    };
    window.addEventListener("keydown", onKeyDown, true);
    return () => window.removeEventListener("keydown", onKeyDown, true);
  }, [showConfirm, executePending]);

  const authorized = Boolean(status?.authorized);
  const backupOk = Boolean(status?.backup_available);
  const restoreOk = Boolean(status?.restore_available);

  const handleBackup = async () => {
    if (backupPending || !authorized || !backupOk) return;
    setBackupPending(true);
    setError(null);
    try {
      await downloadDatabaseBackup();
      showToast("데이터베이스 백업을 다운로드했습니다.");
    } catch (err) {
      const message =
        err instanceof ApiError
          ? err.message
          : "백업을 만들지 못했습니다.";
      setError(message);
      showToast(message);
    } finally {
      setBackupPending(false);
    }
  };

  const handleFileSelected = async (file: File | null) => {
    if (!file || inspectPending || !authorized || !restoreOk) return;
    setInspectPending(true);
    setError(null);
    setInspect(null);
    setShowConfirm(false);
    try {
      const result = await inspectDatabaseRestore(file);
      setInspect(result);
    } catch (err) {
      const message =
        err instanceof ApiError
          ? err.message
          : "백업 파일을 검사하지 못했습니다.";
      setError(message);
    } finally {
      setInspectPending(false);
      if (fileRef.current) fileRef.current.value = "";
    }
  };

  const handleExecute = async () => {
    if (!inspect || executePending) return;
    if (confirmation !== "복원" || !password) return;
    setExecutePending(true);
    setError(null);
    try {
      await executeDatabaseRestore({
        restore_token: inspect.restore_token,
        confirmation,
        current_password: password,
      });
      setShowConfirm(false);
      setPassword("");
      setConfirmation("");
      setInspect(null);
      onRestoreCompleted();
    } catch (err) {
      const message =
        err instanceof ApiError
          ? err.message
          : "복원에 실패했습니다.";
      setError(message);
      showToast(message);
    } finally {
      setExecutePending(false);
    }
  };

  if (loadingStatus) {
    return (
      <div className="bg-card border border-border rounded-2xl p-5 text-sm text-muted-foreground">
        데이터 관리 상태를 확인하는 중…
      </div>
    );
  }

  if (!status?.enabled || !authorized) {
    return (
      <div className="bg-card border border-border rounded-2xl p-5 space-y-2">
        <h2 className="text-sm font-semibold text-foreground">데이터 관리</h2>
        <p className="text-sm text-muted-foreground">
          데이터베이스 백업·복원은 운영 관리자만 사용할 수 있습니다.
        </p>
      </div>
    );
  }

  return (
    <div className="space-y-4">
      <div className="bg-card border border-border rounded-2xl p-5 space-y-3">
        <h2 className="text-sm font-semibold text-foreground">데이터베이스 백업</h2>
        <p className="text-sm text-muted-foreground leading-relaxed">
          PickNext 전체 데이터를 백업합니다. 계정 및 콘텐츠 정보가 포함됩니다.
          로그인 세션·인증 코드 데이터는 제외됩니다. 백업 파일을 안전하게 보관하세요.
        </p>
        <button
          type="button"
          disabled={backupPending || !backupOk}
          onClick={() => void handleBackup()}
          className="inline-flex items-center gap-1.5 bg-primary text-white px-4 py-2.5 rounded-xl text-sm font-medium hover:bg-blue-700 disabled:opacity-50"
        >
          <Download size={14} />
          {backupPending ? "백업 생성 중..." : "백업 다운로드"}
        </button>
      </div>

      <div className="bg-card border border-border rounded-2xl p-5 space-y-3">
        <h2 className="text-sm font-semibold text-foreground">데이터베이스 복원</h2>
        <p className="text-sm text-muted-foreground leading-relaxed">
          PickNext 백업 파일로 복원합니다. 현재 데이터는 백업 내용으로 교체됩니다.
          복원 전에 안전 백업이 자동 생성되며, 완료 후 다시 로그인해야 합니다.
        </p>
        <input
          ref={fileRef}
          type="file"
          accept=".zip,application/zip"
          className="hidden"
          onChange={(event) => {
            const file = event.target.files?.[0] ?? null;
            void handleFileSelected(file);
          }}
        />
        <button
          type="button"
          disabled={inspectPending || executePending || !restoreOk}
          onClick={() => fileRef.current?.click()}
          className="inline-flex items-center gap-1.5 border border-border px-4 py-2.5 rounded-xl text-sm font-medium hover:bg-muted disabled:opacity-50"
        >
          <Upload size={14} />
          {inspectPending ? "검사 중..." : "백업 파일 선택"}
        </button>

        {inspect && (
          <div className="rounded-xl border border-border bg-muted/30 p-4 space-y-2 text-sm">
            <div>백업 생성: {inspect.backup.created_at ?? "—"}</div>
            <div>
              PostgreSQL: {inspect.backup.postgres_major ?? "—"} / Schema:{" "}
              {inspect.backup.alembic_revision ?? "—"}
            </div>
            <div>
              Users {formatCount(inspect.backup.counts?.users)} · Categories{" "}
              {formatCount(inspect.backup.counts?.categories)} · Collections{" "}
              {formatCount(inspect.backup.counts?.collections)} · Items{" "}
              {formatCount(inspect.backup.counts?.items)}
            </div>
            {inspect.compatible ? (
              <p className="text-emerald-700 text-xs">현재 PickNext와 호환됩니다.</p>
            ) : (
              <p className="text-red-600 text-xs">
                현재 PickNext와 호환되지 않는 백업입니다. 백업 Schema:{" "}
                {inspect.backup.alembic_revision ?? "—"} / 현재 Schema:{" "}
                {inspect.current.alembic_revision ?? "—"}
              </p>
            )}
            <button
              type="button"
              disabled={!inspect.compatible || executePending || !inspect.restore_token}
              onClick={() => {
                setConfirmation("");
                setPassword("");
                setShowConfirm(true);
              }}
              className="mt-2 inline-flex items-center bg-primary text-white px-4 py-2 rounded-xl text-sm font-medium disabled:opacity-50"
            >
              복원 계속
            </button>
          </div>
        )}
      </div>

      {error && (
        <p className="text-sm text-red-600" role="alert">
          {error}
        </p>
      )}

      {showConfirm && inspect && (
        <div
          className="fixed inset-0 z-50 bg-black/50 flex items-center justify-center p-4"
          role="dialog"
          aria-modal="true"
          aria-labelledby="restore-confirm-title"
        >
          <div className="bg-card rounded-2xl w-full max-w-md p-6 shadow-2xl space-y-4">
            <h3 id="restore-confirm-title" className="text-base font-bold text-foreground">
              데이터베이스 복원 확인
            </h3>
            <p className="text-sm text-muted-foreground leading-relaxed">
              현재 데이터베이스가 백업 파일의 데이터로 교체됩니다. 복원 전에 현재
              데이터베이스의 안전 백업을 자동 생성합니다. 복원 완료 후 모든 사용자는
              다시 로그인해야 합니다.
            </p>
            <div>
              <label className="block text-sm font-medium mb-1" htmlFor="restore-confirm-text">
                계속하려면 &quot;복원&quot;을 입력하세요
              </label>
              <input
                id="restore-confirm-text"
                value={confirmation}
                disabled={executePending}
                onChange={(event) => setConfirmation(event.target.value)}
                className="w-full px-3 py-2.5 border border-border rounded-xl text-sm"
              />
            </div>
            <div>
              <label className="block text-sm font-medium mb-1" htmlFor="restore-password">
                현재 비밀번호
              </label>
              <input
                id="restore-password"
                type="password"
                autoComplete="current-password"
                value={password}
                disabled={executePending}
                onChange={(event) => setPassword(event.target.value)}
                className="w-full px-3 py-2.5 border border-border rounded-xl text-sm"
              />
            </div>
            {executePending && (
              <p className="text-sm text-muted-foreground">
                데이터베이스를 복원하고 있습니다. 완료될 때까지 잠시 기다려 주세요.
              </p>
            )}
            <div className="flex gap-3">
              <button
                type="button"
                disabled={executePending}
                onClick={() => setShowConfirm(false)}
                className="flex-1 border border-border py-2.5 rounded-xl text-sm"
              >
                취소
              </button>
              <button
                type="button"
                disabled={
                  executePending
                  || confirmation !== "복원"
                  || password.length === 0
                }
                onClick={() => void handleExecute()}
                className="flex-1 bg-primary text-white py-2.5 rounded-xl text-sm font-medium disabled:opacity-50"
              >
                {executePending ? "복원 중..." : "복원 시작"}
              </button>
            </div>
          </div>
        </div>
      )}
    </div>
  );
}
