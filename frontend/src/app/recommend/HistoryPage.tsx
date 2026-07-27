import { useCallback, useEffect, useRef, useState, type ReactNode } from "react";
import { Layers, RefreshCw, Shuffle, Trash2 } from "lucide-react";
import { ApiError } from "../../api/client";
import {
  deleteAllRecommendationHistory,
  deleteRecommendationHistory,
  getRecommendationHistory,
} from "../../api/recommendationHistory";
import { ContentPoster, formatReleaseYearMeta } from "../components/ContentPoster";
import { getCategoryPresentation } from "../presentation/categoryPresentation";
import type { RecommendationHistoryListItem } from "../../types/recommendation";

function formatSelectedAt(value: string): string {
  const date = new Date(value);
  if (Number.isNaN(date.getTime())) return value;
  const y = date.getFullYear();
  const m = String(date.getMonth() + 1).padStart(2, "0");
  const d = String(date.getDate()).padStart(2, "0");
  const hh = String(date.getHours()).padStart(2, "0");
  const mm = String(date.getMinutes()).padStart(2, "0");
  return `${y}-${m}-${d} ${hh}:${mm}`;
}

function statusFilterLabel(filter: string): string {
  if (filter === "PLANNED") return "예정";
  if (filter === "COMPLETED") return "완료";
  return "전체";
}

function ConfirmModal({
  title,
  body,
  confirmLabel,
  pending,
  onConfirm,
  onClose,
}: {
  title: string;
  body: string;
  confirmLabel: string;
  pending?: boolean;
  onConfirm: () => void;
  onClose: () => void;
  children?: ReactNode;
}) {
  return (
    <div
      className="fixed inset-0 bg-black/50 z-50 flex items-center justify-center p-4 pb-20 sm:pb-4"
      role="dialog"
      aria-modal="true"
      aria-labelledby="history-confirm-title"
    >
      <div className="bg-card rounded-2xl w-full max-w-sm p-6 shadow-2xl">
        <h3 id="history-confirm-title" className="text-base font-bold text-foreground mb-2">
          {title}
        </h3>
        <p className="text-sm text-muted-foreground mb-4 whitespace-pre-line">{body}</p>
        <div className="flex gap-3 mt-4">
          <button
            type="button"
            onClick={onClose}
            disabled={pending}
            className="flex-1 border border-border text-foreground py-2.5 rounded-xl font-medium hover:bg-muted transition-colors text-sm disabled:opacity-50"
          >
            취소
          </button>
          <button
            type="button"
            onClick={onConfirm}
            disabled={pending}
            className="flex-1 py-2.5 rounded-xl font-medium bg-red-500 hover:bg-red-600 text-white transition-colors text-sm disabled:opacity-50"
          >
            {pending ? "삭제 중..." : confirmLabel}
          </button>
        </div>
      </div>
    </div>
  );
}

export interface HistoryPageProps {
  showToast: (message: string) => void;
  openHistoryDetail: (historyId: string) => void;
}

export function HistoryPage({ showToast, openHistoryDetail }: HistoryPageProps) {
  const [items, setItems] = useState<RecommendationHistoryListItem[]>([]);
  const [page, setPage] = useState(1);
  const [totalPages, setTotalPages] = useState(0);
  const [total, setTotal] = useState(0);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [deleteTarget, setDeleteTarget] = useState<RecommendationHistoryListItem | null>(null);
  const [deleteAllOpen, setDeleteAllOpen] = useState(false);
  const [deletePending, setDeletePending] = useState(false);
  const requestIdRef = useRef(0);

  const load = useCallback(async (nextPage: number) => {
    const requestId = ++requestIdRef.current;
    setLoading(true);
    setError(null);
    try {
      const response = await getRecommendationHistory({
        page: nextPage,
        page_size: 20,
      });
      if (requestId !== requestIdRef.current) return;
      setItems(response.items);
      setPage(response.page);
      setTotalPages(response.total_pages);
      setTotal(response.total);
    } catch (err) {
      if (requestId !== requestIdRef.current) return;
      setItems([]);
      setError(
        err instanceof ApiError
          ? err.message
          : "추천 이력을 불러오지 못했습니다.",
      );
    } finally {
      if (requestId === requestIdRef.current) {
        setLoading(false);
      }
    }
  }, []);

  useEffect(() => {
    void load(1);
  }, [load]);

  const handleDeleteOne = async () => {
    if (!deleteTarget || deletePending) return;
    setDeletePending(true);
    try {
      await deleteRecommendationHistory(deleteTarget.id);
      showToast("추천 이력을 삭제했습니다.");
      setDeleteTarget(null);
      await load(page);
    } catch (err) {
      showToast(
        err instanceof ApiError ? err.message : "삭제에 실패했습니다.",
      );
    } finally {
      setDeletePending(false);
    }
  };

  const handleDeleteAll = async () => {
    if (deletePending) return;
    setDeletePending(true);
    try {
      const result = await deleteAllRecommendationHistory();
      showToast(`추천 이력 ${result.deleted_count}건을 삭제했습니다.`);
      setDeleteAllOpen(false);
      await load(1);
    } catch (err) {
      showToast(
        err instanceof ApiError ? err.message : "전체 삭제에 실패했습니다.",
      );
    } finally {
      setDeletePending(false);
    }
  };

  return (
    <div className="max-w-2xl mx-auto px-4 sm:px-6 py-6">
      <div className="flex items-center justify-between mb-5 gap-3">
        <h1 className="text-xl font-bold text-foreground">추천 이력</h1>
        {total > 0 && (
          <button
            type="button"
            onClick={() => setDeleteAllOpen(true)}
            className="text-xs text-red-600 hover:underline"
          >
            전체 삭제
          </button>
        )}
      </div>

      {loading ? (
        <div className="space-y-2" aria-live="polite">
          {[0, 1, 2].map((i) => (
            <div key={i} className="bg-card border border-border rounded-xl p-4 h-20 animate-pulse bg-muted/40" />
          ))}
        </div>
      ) : error ? (
        <div className="bg-card border border-border rounded-xl p-4 flex flex-col sm:flex-row sm:items-center sm:justify-between gap-3" role="alert">
          <p className="text-sm text-muted-foreground">{error}</p>
          <button
            type="button"
            onClick={() => void load(page)}
            className="inline-flex items-center gap-1.5 text-xs bg-primary text-white px-3 py-1.5 rounded-xl"
          >
            <RefreshCw size={12} /> 다시 시도
          </button>
        </div>
      ) : items.length === 0 ? (
        <div className="bg-card border border-border rounded-xl p-6 text-center">
          <p className="text-sm text-muted-foreground">저장된 추천 이력이 없습니다.</p>
        </div>
      ) : (
        <div className="space-y-2">
          {items.map((entry) => {
            const presentation = getCategoryPresentation(entry.category.name);
            return (
              <div
                key={entry.id}
                className="bg-card border border-border rounded-xl p-3 flex items-center gap-3"
              >
                <ContentPoster
                  src={entry.poster_url}
                  title={entry.title}
                  fallbackColor={presentation.color}
                  size="xs"
                />
                <div className="flex-1 min-w-0">
                  <div className="flex items-center gap-1.5 mb-0.5">
                    {entry.candidate_type === "COLLECTION" ? (
                      <Layers size={12} className="text-purple-600 flex-shrink-0" />
                    ) : (
                      <Shuffle size={12} className="text-blue-600 flex-shrink-0" />
                    )}
                    <div className="text-sm font-medium text-foreground truncate">
                      {entry.title}
                    </div>
                  </div>
                  <div className="text-xs text-muted-foreground">
                    {entry.category.name} · {statusFilterLabel(entry.status_filter)} ·{" "}
                    {entry.item_count}개 · {formatSelectedAt(entry.selected_at)}
                  </div>
                  {formatReleaseYearMeta(entry.release_year) && (
                    <div className="text-[10px] text-muted-foreground">
                      {formatReleaseYearMeta(entry.release_year)}
                    </div>
                  )}
                </div>
                <div className="flex flex-col items-end gap-2 flex-shrink-0">
                  <button
                    type="button"
                    onClick={() => openHistoryDetail(entry.id)}
                    className="text-[10px] text-primary hover:underline"
                  >
                    상세보기
                  </button>
                  <button
                    type="button"
                    aria-label={`${entry.title} 추천 이력 삭제`}
                    onClick={() => setDeleteTarget(entry)}
                    className="text-red-500 hover:text-red-600 p-1"
                  >
                    <Trash2 size={14} />
                  </button>
                </div>
              </div>
            );
          })}
        </div>
      )}

      {totalPages > 1 && (
        <div className="flex items-center justify-center gap-3 mt-5">
          <button
            type="button"
            disabled={page <= 1 || loading}
            onClick={() => void load(page - 1)}
            className="text-xs border border-border px-3 py-1.5 rounded-lg disabled:opacity-40"
          >
            이전
          </button>
          <span className="text-xs text-muted-foreground">
            {page} / {totalPages}
          </span>
          <button
            type="button"
            disabled={page >= totalPages || loading}
            onClick={() => void load(page + 1)}
            className="text-xs border border-border px-3 py-1.5 rounded-lg disabled:opacity-40"
          >
            다음
          </button>
        </div>
      )}

      {deleteTarget && (
        <ConfirmModal
          title="추천 이력 삭제"
          body={`“${deleteTarget.title}” 이력을 삭제하시겠습니까?\n이 작업은 되돌릴 수 없습니다.`}
          confirmLabel="삭제"
          pending={deletePending}
          onConfirm={() => void handleDeleteOne()}
          onClose={() => {
            if (!deletePending) setDeleteTarget(null);
          }}
        />
      )}

      {deleteAllOpen && (
        <ConfirmModal
          title="추천 이력 전체 삭제"
          body={"추천 이력을 모두 삭제하시겠습니까?\n이 작업은 되돌릴 수 없습니다."}
          confirmLabel="전체 삭제"
          pending={deletePending}
          onConfirm={() => void handleDeleteAll()}
          onClose={() => {
            if (!deletePending) setDeleteAllOpen(false);
          }}
        />
      )}
    </div>
  );
}
