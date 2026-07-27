import { useEffect, useRef, useState } from "react";
import { ChevronLeft, Layers, RefreshCw } from "lucide-react";
import { ApiError } from "../../api/client";
import { getRecommendationHistoryDetail } from "../../api/recommendationHistory";
import { ContentPoster, formatReleaseYearMeta } from "../components/ContentPoster";
import { getCategoryPresentation } from "../presentation/categoryPresentation";
import type { ApiItemStatus } from "../../types/api";
import type { RecommendationHistoryDetail } from "../../types/recommendation";

function StatusBadge({ status, sm }: { status: ApiItemStatus; sm?: boolean }) {
  return (
    <span
      className={`inline-flex items-center rounded font-medium ${
        sm ? "text-[10px] px-1.5 py-px" : "text-xs px-2 py-0.5"
      } ${
        status === "PLANNED"
          ? "bg-blue-100 text-blue-700"
          : "bg-emerald-100 text-emerald-700"
      }`}
    >
      {status === "PLANNED" ? "예정" : "완료"}
    </span>
  );
}

function formatSelectedAt(value: string): string {
  const date = new Date(value);
  if (Number.isNaN(date.getTime())) return value;
  return date.toLocaleString("ko-KR");
}

function statusFilterLabel(filter: string): string {
  if (filter === "PLANNED") return "예정";
  if (filter === "COMPLETED") return "완료";
  return "전체";
}

export interface HistoryDetailPageProps {
  historyId: string;
  onBack: () => void;
  openItemDetail: (itemId: string) => void;
  showToast: (message: string) => void;
}

export function HistoryDetailPage({
  historyId,
  onBack,
  openItemDetail,
  showToast,
}: HistoryDetailPageProps) {
  const [detail, setDetail] = useState<RecommendationHistoryDetail | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const requestIdRef = useRef(0);

  const load = async () => {
    const requestId = ++requestIdRef.current;
    setLoading(true);
    setError(null);
    try {
      const response = await getRecommendationHistoryDetail(historyId);
      if (requestId !== requestIdRef.current) return;
      setDetail(response);
    } catch (err) {
      if (requestId !== requestIdRef.current) return;
      setDetail(null);
      const message =
        err instanceof ApiError && err.status === 404
          ? "추천 이력을 찾을 수 없습니다."
          : err instanceof ApiError
            ? err.message
            : "추천 이력을 불러오지 못했습니다.";
      setError(message);
      if (err instanceof ApiError && err.status === 404) {
        showToast(message);
      }
    } finally {
      if (requestId === requestIdRef.current) {
        setLoading(false);
      }
    }
  };

  useEffect(() => {
    void load();
    // eslint-disable-next-line react-hooks/exhaustive-deps -- reload on historyId change
  }, [historyId]);

  return (
    <div className="max-w-2xl mx-auto px-4 sm:px-6 py-6">
      <button
        type="button"
        onClick={onBack}
        className="flex items-center gap-1 text-sm text-muted-foreground hover:text-foreground mb-5"
      >
        <ChevronLeft size={16} /> 추천 이력
      </button>

      {loading ? (
        <div className="space-y-3" aria-live="polite">
          <div className="h-8 w-48 animate-pulse rounded bg-muted" />
          <div className="h-24 animate-pulse rounded-2xl bg-muted" />
        </div>
      ) : error ? (
        <div className="bg-card border border-border rounded-xl p-4 space-y-3" role="alert">
          <p className="text-sm text-muted-foreground">{error}</p>
          <button
            type="button"
            onClick={() => void load()}
            className="inline-flex items-center gap-1.5 text-xs bg-primary text-white px-3 py-1.5 rounded-xl"
          >
            <RefreshCw size={12} /> 다시 시도
          </button>
        </div>
      ) : detail ? (
        <div className="space-y-5">
          <div>
            <div className="flex items-center gap-2 mb-1">
              {detail.candidate_type === "COLLECTION" && (
                <Layers size={16} className="text-purple-600" />
              )}
              <h1 className="text-xl font-bold text-foreground">
                {detail.collection?.name ??
                  detail.items[0]?.title_snapshot ??
                  "추천 이력"}
              </h1>
            </div>
            <p className="text-sm text-muted-foreground">
              {formatSelectedAt(detail.selected_at)}
            </p>
            <div className="flex flex-wrap gap-2 mt-2 text-xs text-muted-foreground">
              <span>Category: {detail.category.name}</span>
              <span>상태 필터: {statusFilterLabel(detail.status_filter)}</span>
              <span>{detail.items.length}개 항목</span>
            </div>
          </div>

          <div className="bg-card border border-border rounded-2xl overflow-hidden divide-y divide-border">
            {detail.items.map((row) => {
              const current = row.current;
              const presentation = getCategoryPresentation(
                current?.category.name ?? detail.category.name,
              );
              return (
                <div key={`${row.item_id}-${row.sort_order}`} className="p-4 flex items-center gap-3">
                  <ContentPoster
                    src={current?.poster_url ?? null}
                    title={row.title_snapshot}
                    fallbackColor={presentation.color}
                    size="sm"
                  />
                  <div className="flex-1 min-w-0">
                    <div className="text-sm font-medium text-foreground truncate">
                      {row.title_snapshot}
                    </div>
                    {formatReleaseYearMeta(current?.release_year ?? null) && (
                      <p className="text-[10px] text-muted-foreground">
                        {formatReleaseYearMeta(current?.release_year ?? null)}
                      </p>
                    )}
                    <div className="flex flex-wrap gap-1.5 mt-1">
                      <span className="text-[10px] text-muted-foreground">
                        선택 시:{" "}
                      </span>
                      <StatusBadge status={row.status_at_selection} sm />
                      {current && (
                        <>
                          <span className="text-[10px] text-muted-foreground">현재:</span>
                          <StatusBadge status={current.status} sm />
                        </>
                      )}
                    </div>
                  </div>
                  {row.item_exists && (
                    <button
                      type="button"
                      onClick={() => openItemDetail(row.item_id)}
                      className="text-[10px] text-primary hover:underline flex-shrink-0"
                    >
                      상세보기
                    </button>
                  )}
                </div>
              );
            })}
          </div>
        </div>
      ) : null}
    </div>
  );
}
