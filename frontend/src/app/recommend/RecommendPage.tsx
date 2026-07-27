import { useCallback, useEffect, useId, useRef, useState, type ReactNode } from "react";
import {
  CheckCircle,
  ChevronLeft,
  Layers,
  RefreshCw,
  Shuffle,
  Star,
} from "lucide-react";
import { ApiError } from "../../api/client";
import { getCategories } from "../../api/catalog";
import { getRandomRecommendation } from "../../api/recommendations";
import { createRecommendationHistory } from "../../api/recommendationHistory";
import { ContentPoster, formatReleaseYearMeta } from "../components/ContentPoster";
import { getCategoryPresentation } from "../presentation/categoryPresentation";
import type { ApiCategory, ApiItemListItem, ApiItemStatus } from "../../types/api";
import type {
  RandomRecommendationResponse,
  RecommendationCandidateType,
  RecommendationStatusFilter,
} from "../../types/recommendation";
import type { RecommendStep } from "../../types/mock";

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

function StarRating({ rating, sm }: { rating?: number; sm?: boolean }) {
  if (rating === undefined || rating === null || rating <= 0) {
    return <span className="text-xs text-muted-foreground">평가 없음</span>;
  }
  return (
    <span className="inline-flex items-center gap-0.5">
      {[1, 2, 3, 4, 5].map((i) => {
        const filled = rating >= i;
        const half = !filled && rating >= i - 0.5;
        return (
          <Star
            key={i}
            size={sm ? 10 : 12}
            className={
              filled
                ? "fill-amber-400 text-amber-400"
                : half
                  ? "fill-amber-400/50 text-amber-400"
                  : "text-gray-200"
            }
          />
        );
      })}
      <span className="ml-1 text-xs text-muted-foreground">{rating.toFixed(1)}</span>
    </span>
  );
}

function ConfirmModal({
  title,
  body,
  confirmLabel,
  pending,
  onConfirm,
  onClose,
  children,
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
      aria-labelledby="recommend-confirm-title"
    >
      <div className="bg-card rounded-2xl w-full max-w-sm p-6 shadow-2xl max-h-[min(85vh,calc(100dvh-6rem))] overflow-y-auto">
        <h3 id="recommend-confirm-title" className="text-base font-bold text-foreground mb-2">
          {title}
        </h3>
        <p className="text-sm text-muted-foreground mb-4 whitespace-pre-line">{body}</p>
        {children}
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
            className="flex-1 py-2.5 rounded-xl font-medium bg-primary hover:bg-blue-700 text-white transition-colors text-sm disabled:opacity-50"
          >
            {pending ? "저장 중..." : confirmLabel}
          </button>
        </div>
      </div>
    </div>
  );
}

function statusFilterLabel(filter: RecommendationStatusFilter): string {
  if (filter === "PLANNED") return "예정";
  if (filter === "COMPLETED") return "완료";
  return "전체";
}

function ResultItemRow({
  item,
  onOpenDetail,
}: {
  item: ApiItemListItem;
  onOpenDetail: (itemId: string) => void;
}) {
  const presentation = getCategoryPresentation(item.category.name);
  const Icon = presentation.icon;
  return (
    <div className="flex items-center gap-3 px-4 py-3">
      <ContentPoster
        src={item.poster_url}
        title={item.title}
        fallbackColor={presentation.color}
        size="sm"
      />
      <div className="flex-1 min-w-0">
        <div className="text-sm font-medium text-foreground truncate">{item.title}</div>
        {formatReleaseYearMeta(item.release_year) && (
          <p className="text-[10px] text-muted-foreground">
            {formatReleaseYearMeta(item.release_year)}
          </p>
        )}
        <div className="mt-0.5 flex flex-wrap items-center gap-1.5">
          <span
            className="inline-flex items-center gap-1 rounded font-medium text-[10px] px-1.5 py-px"
            style={{ backgroundColor: presentation.bgColor, color: presentation.color }}
          >
            <Icon size={10} />
            {item.category.name}
          </span>
          <StatusBadge status={item.status} sm />
        </div>
        {item.progress_note && (
          <p className="text-[10px] text-muted-foreground mt-0.5">{item.progress_note}</p>
        )}
      </div>
      <button
        type="button"
        onClick={() => onOpenDetail(item.id)}
        className="text-[10px] text-primary hover:underline flex-shrink-0"
      >
        상세보기
      </button>
    </div>
  );
}

export interface RecommendPageProps {
  showToast: (message: string) => void;
  openItemDetail: (itemId: string) => void;
  onOpenHistory: () => void;
  initialCategoryId?: string | null;
}

export function RecommendPage({
  showToast,
  openItemDetail,
  onOpenHistory,
  initialCategoryId = null,
}: RecommendPageProps) {
  const categoryLabelId = useId();
  const statusLabelId = useId();
  const [step, setStep] = useState<RecommendStep>("setup");
  const [categories, setCategories] = useState<ApiCategory[]>([]);
  const [categoriesLoading, setCategoriesLoading] = useState(true);
  const [categoriesError, setCategoriesError] = useState<string | null>(null);
  const [categoryId, setCategoryId] = useState<string>("");
  const [statusFilter, setStatusFilter] =
    useState<RecommendationStatusFilter>("PLANNED");
  const [result, setResult] = useState<RandomRecommendationResponse | null>(null);
  const [savedHistoryId, setSavedHistoryId] = useState<string | null>(null);
  const [recommendPending, setRecommendPending] = useState(false);
  const [savePending, setSavePending] = useState(false);
  const [confirmOpen, setConfirmOpen] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const recommendRequestId = useRef(0);
  const saveRequestId = useRef(0);

  const loadCategories = useCallback(async () => {
    setCategoriesLoading(true);
    setCategoriesError(null);
    try {
      const response = await getCategories();
      setCategories(response.categories);
      setCategoryId((current) => {
        if (current && response.categories.some((c) => c.id === current)) {
          return current;
        }
        if (
          initialCategoryId &&
          response.categories.some((c) => c.id === initialCategoryId)
        ) {
          return initialCategoryId;
        }
        return response.categories[0]?.id ?? "";
      });
    } catch {
      setCategories([]);
      setCategoriesError("Category 목록을 불러오지 못했습니다.");
    } finally {
      setCategoriesLoading(false);
    }
  }, [initialCategoryId]);

  useEffect(() => {
    void loadCategories();
  }, [loadCategories]);

  const runRecommend = useCallback(async () => {
    if (!categoryId || recommendPending) return;
    const requestId = ++recommendRequestId.current;
    setRecommendPending(true);
    setError(null);
    try {
      const response = await getRandomRecommendation({
        category_id: categoryId,
        status_filter: statusFilter,
      });
      if (requestId !== recommendRequestId.current) return;
      setResult(response);
      setSavedHistoryId(null);
      setStep("result");
      if (response.eligible_candidate_count === 0) {
        setError("선택한 조건에 맞는 추천 항목이 없습니다.");
      }
    } catch (err) {
      if (requestId !== recommendRequestId.current) return;
      const message =
        err instanceof ApiError
          ? err.message
          : "추천을 불러오지 못했습니다. 다시 시도해 주세요.";
      setError(message);
      showToast(message);
    } finally {
      if (requestId === recommendRequestId.current) {
        setRecommendPending(false);
      }
    }
  }, [categoryId, recommendPending, showToast, statusFilter]);

  const saveSelection = useCallback(async () => {
    if (!result?.candidate_type || !result.candidate_id || savedHistoryId || savePending) {
      return;
    }
    const requestId = ++saveRequestId.current;
    setSavePending(true);
    try {
      const saved = await createRecommendationHistory({
        category_id: result.category.id,
        status_filter: result.status_filter,
        candidate_type: result.candidate_type,
        candidate_id: result.candidate_id,
      });
      if (requestId !== saveRequestId.current) return;
      setSavedHistoryId(saved.id);
      setConfirmOpen(false);
      setStep("complete");
      showToast("추천 이력이 저장되었습니다.");
    } catch (err) {
      if (requestId !== saveRequestId.current) return;
      const message =
        err instanceof ApiError
          ? err.message
          : "추천 이력 저장에 실패했습니다.";
      showToast(message);
    } finally {
      if (requestId === saveRequestId.current) {
        setSavePending(false);
      }
    }
  }, [result, savePending, savedHistoryId, showToast]);

  const resetToSetup = () => {
    setStep("setup");
    setResult(null);
    setSavedHistoryId(null);
    setError(null);
    setConfirmOpen(false);
  };

  const displayTitle =
    result?.candidate_type === "COLLECTION"
      ? result.collection?.name ?? "Collection"
      : result?.items[0]?.title ?? "";

  const primaryItem = result?.items[0] ?? null;
  const primaryPresentation = getCategoryPresentation(
    primaryItem?.category.name ?? result?.category.name ?? "",
  );

  if (step === "complete" && result) {
    return (
      <div className="max-w-md mx-auto px-4 py-12 text-center">
        <div className="w-16 h-16 rounded-full bg-emerald-100 flex items-center justify-center mx-auto mb-4">
          <CheckCircle size={30} className="text-emerald-600" />
        </div>
        <h1 className="text-2xl font-bold text-foreground mb-2">오늘의 선택을 확정했습니다.</h1>
        <p className="text-sm text-muted-foreground mb-7">추천 이력이 저장되었습니다.</p>
        <div className="bg-card border border-border rounded-2xl p-6 mb-6 flex flex-col items-center gap-4">
          <ContentPoster
            src={primaryItem?.poster_url}
            title={displayTitle}
            fallbackColor={primaryPresentation.color}
            size="lg"
          />
          <div>
            <div className="flex justify-center flex-wrap gap-1.5 mb-1.5">
              <span
                className="inline-flex items-center gap-1 rounded font-medium text-[10px] px-1.5 py-px"
                style={{
                  backgroundColor: primaryPresentation.bgColor,
                  color: primaryPresentation.color,
                }}
              >
                {result.category.name}
              </span>
              {result.candidate_type === "COLLECTION" && (
                <span className="text-[10px] bg-purple-100 text-purple-700 px-2 py-0.5 rounded flex items-center gap-1">
                  <Layers size={9} />
                  Collection
                </span>
              )}
            </div>
            <h2 className="text-xl font-bold text-foreground text-center">{displayTitle}</h2>
            {result.candidate_type === "ITEM" && primaryItem && (
              <div className="mt-1.5 flex justify-center">
                <StatusBadge status={primaryItem.status} />
              </div>
            )}
            {result.candidate_type === "COLLECTION" && (
              <p className="text-sm text-muted-foreground text-center mt-1">
                {result.items.length}개 항목
              </p>
            )}
          </div>
        </div>
        {result.candidate_type === "COLLECTION" && (
          <div className="bg-card border border-border rounded-xl overflow-hidden mb-4 text-left">
            <div className="px-4 py-2 border-b border-border bg-muted/30 text-xs font-medium text-muted-foreground">
              Collection 소속 항목
            </div>
            {result.items.map((item) => (
              <ResultItemRow key={item.id} item={item} onOpenDetail={openItemDetail} />
            ))}
          </div>
        )}
        <div className="space-y-2">
          {result.candidate_type === "ITEM" && primaryItem && (
            <button
              type="button"
              onClick={() => openItemDetail(primaryItem.id)}
              className="w-full border border-border text-foreground py-3 rounded-xl font-medium hover:bg-muted transition-colors"
            >
              상세보기
            </button>
          )}
          <button
            type="button"
            onClick={onOpenHistory}
            className="w-full bg-primary text-white py-3 rounded-xl font-medium hover:bg-blue-700 transition-colors"
          >
            추천 이력 보기
          </button>
          <button
            type="button"
            onClick={resetToSetup}
            className="w-full border border-border text-muted-foreground py-3 rounded-xl font-medium hover:bg-muted transition-colors"
          >
            다시 추천
          </button>
        </div>
      </div>
    );
  }

  if (step === "result" && result) {
    const isItem = result.candidate_type === "ITEM";
    const isEmpty = result.eligible_candidate_count === 0 || !result.candidate_type;

    return (
      <div className="max-w-lg mx-auto px-4 py-6 pb-32 sm:pb-6">
        <button
          type="button"
          onClick={resetToSetup}
          className="flex items-center gap-1 text-sm text-muted-foreground hover:text-foreground mb-5"
        >
          <ChevronLeft size={16} /> 추천 설정
        </button>
        <h1 className="text-lg font-bold text-foreground mb-4">추천 결과</h1>

        {isEmpty ? (
          <div
            className="bg-card border border-border rounded-2xl p-6 text-center"
            role="status"
            aria-live="polite"
          >
            <p className="text-sm text-muted-foreground">
              선택한 조건에 맞는 추천 항목이 없습니다.
            </p>
            <button
              type="button"
              onClick={() => void runRecommend()}
              disabled={recommendPending}
              className="mt-4 inline-flex items-center gap-2 border border-border px-4 py-2 rounded-xl text-sm"
            >
              <RefreshCw size={14} className={recommendPending ? "animate-spin" : ""} />
              다시 시도
            </button>
          </div>
        ) : (
          <>
            <div
              className={`bg-card border-2 border-primary/20 rounded-2xl p-6 transition-all duration-300 mb-4 ${
                recommendPending ? "opacity-40 scale-95" : ""
              }`}
            >
              <div className="text-center mb-4">
                <span className="text-xs font-semibold text-primary bg-blue-50 px-3 py-1 rounded-full">
                  PickNext 추천
                </span>
              </div>
              <div className="flex flex-col items-center gap-4">
                <ContentPoster
                  src={primaryItem?.poster_url}
                  title={displayTitle}
                  fallbackColor={primaryPresentation.color}
                  size="lg"
                />
                <div className="text-center w-full">
                  <div className="flex justify-center flex-wrap gap-1.5 mb-2">
                    <span
                      className="inline-flex items-center gap-1 rounded font-medium text-[10px] px-1.5 py-px"
                      style={{
                        backgroundColor: primaryPresentation.bgColor,
                        color: primaryPresentation.color,
                      }}
                    >
                      {result.category.name}
                    </span>
                    {!isItem && (
                      <span className="text-[10px] bg-purple-100 text-purple-700 px-2 py-0.5 rounded flex items-center gap-1">
                        <Layers size={9} />
                        Collection
                      </span>
                    )}
                    {isItem && primaryItem && <StatusBadge status={primaryItem.status} />}
                  </div>
                  <h2 className="text-2xl font-bold text-foreground mb-1">{displayTitle}</h2>
                  {!isItem && (
                    <p className="text-sm text-muted-foreground">
                      {result.items.length}개 항목
                    </p>
                  )}
                  {isItem && primaryItem && formatReleaseYearMeta(primaryItem.release_year) && (
                    <p className="text-xs text-muted-foreground">
                      {formatReleaseYearMeta(primaryItem.release_year)}
                    </p>
                  )}
                  {isItem && primaryItem?.progress_note && (
                    <p className="text-xs text-muted-foreground">
                      진행: {primaryItem.progress_note}
                    </p>
                  )}
                  {isItem && primaryItem && (
                    <div className="mt-1 flex justify-center">
                      <StarRating rating={primaryItem.rating} />
                    </div>
                  )}
                </div>
              </div>
            </div>

            {!isItem && (
              <div className="bg-card border border-border rounded-2xl overflow-hidden mb-4">
                <div className="px-4 py-2.5 border-b border-border bg-muted/30">
                  <p className="text-xs font-medium text-foreground">소속 항목 목록</p>
                </div>
                <div className="divide-y divide-border max-h-60 overflow-y-auto">
                  {result.items.map((item) => (
                    <ResultItemRow key={item.id} item={item} onOpenDetail={openItemDetail} />
                  ))}
                </div>
              </div>
            )}

            <div className="fixed bottom-16 left-0 right-0 sm:static sm:bottom-auto px-4 sm:px-0 pb-2 sm:pb-0 bg-background sm:bg-transparent">
              <div className="flex flex-col gap-2.5">
                <button
                  type="button"
                  aria-label="이걸로 선택"
                  disabled={Boolean(savedHistoryId) || savePending || recommendPending}
                  onClick={() => setConfirmOpen(true)}
                  className="w-full bg-primary text-white py-4 rounded-xl font-semibold hover:bg-blue-700 transition-colors disabled:opacity-40"
                >
                  {savedHistoryId
                    ? "선택 완료"
                    : isItem
                      ? "이걸로 선택"
                      : "이 Collection으로 선택"}
                </button>
                <div className="flex gap-2">
                  <button
                    type="button"
                    aria-label="다시 추천"
                    onClick={() => void runRecommend()}
                    disabled={recommendPending || savePending}
                    className="flex-1 border border-border bg-card text-foreground py-3 rounded-xl font-medium hover:bg-muted transition-colors flex items-center justify-center gap-2 text-sm disabled:opacity-40"
                  >
                    <RefreshCw
                      size={14}
                      className={recommendPending ? "animate-spin" : ""}
                    />
                    {recommendPending ? "추천 중..." : "다시 추천"}
                  </button>
                  {isItem && primaryItem && (
                    <button
                      type="button"
                      onClick={() => openItemDetail(primaryItem.id)}
                      className="flex-1 border border-border text-muted-foreground py-3 rounded-xl font-medium hover:bg-muted transition-colors text-sm"
                    >
                      상세보기
                    </button>
                  )}
                </div>
              </div>
            </div>

            {confirmOpen && (
              <ConfirmModal
                title="선택을 확정하시겠습니까?"
                body="선택 결과가 추천 이력에 저장됩니다."
                confirmLabel="선택 확정"
                pending={savePending}
                onConfirm={() => void saveSelection()}
                onClose={() => {
                  if (!savePending) setConfirmOpen(false);
                }}
              >
                <div className="bg-muted rounded-xl p-3 text-sm font-medium text-foreground">
                  {displayTitle}
                </div>
              </ConfirmModal>
            )}
          </>
        )}
      </div>
    );
  }

  const canRecommend = Boolean(categoryId) && !categoriesLoading && !recommendPending;

  return (
    <div className="max-w-xl mx-auto px-4 py-6">
      <h1 className="text-xl font-bold text-foreground mb-6">랜덤 추천</h1>

      <div className="bg-card border border-border rounded-2xl p-5 mb-4">
        <h3 id={statusLabelId} className="text-sm font-semibold text-foreground mb-3">
          상태 필터
        </h3>
        <div
          className="flex bg-muted rounded-xl p-0.5"
          role="group"
          aria-labelledby={statusLabelId}
        >
          {(
            [
              ["PLANNED", "예정"],
              ["COMPLETED", "완료"],
              ["ALL", "전체"],
            ] as const
          ).map(([value, label]) => (
            <button
              key={value}
              type="button"
              onClick={() => setStatusFilter(value)}
              className={`flex-1 py-2 rounded-lg text-xs font-medium transition-colors ${
                statusFilter === value
                  ? "bg-card shadow text-foreground"
                  : "text-muted-foreground hover:text-foreground"
              }`}
            >
              {label}
            </button>
          ))}
        </div>
      </div>

      <div className="bg-card border border-border rounded-2xl p-5 mb-4">
        <h3 id={categoryLabelId} className="text-sm font-semibold text-foreground mb-3">
          카테고리
        </h3>
        {categoriesLoading ? (
          <div className="h-10 animate-pulse rounded-xl bg-muted" aria-live="polite">
            Category 불러오는 중...
          </div>
        ) : categoriesError ? (
          <div className="space-y-2" role="alert" aria-live="assertive">
            <p className="text-sm text-muted-foreground">{categoriesError}</p>
            <button
              type="button"
              onClick={() => void loadCategories()}
              className="text-xs text-primary hover:underline"
            >
              다시 시도
            </button>
          </div>
        ) : categories.length === 0 ? (
          <p className="text-sm text-muted-foreground">
            추천을 받으려면 먼저 카테고리를 등록해 주세요.
          </p>
        ) : (
          <div className="grid grid-cols-2 sm:grid-cols-3 gap-2" role="listbox" aria-labelledby={categoryLabelId}>
            {categories.map((cat) => {
              const presentation = getCategoryPresentation(cat.name);
              const Icon = presentation.icon;
              const selected = categoryId === cat.id;
              return (
                <button
                  key={cat.id}
                  type="button"
                  role="option"
                  aria-selected={selected}
                  onClick={() => setCategoryId(cat.id)}
                  className={`flex items-center gap-2 p-2.5 rounded-xl border text-xs font-medium transition-colors ${
                    selected
                      ? "border-primary bg-blue-50 text-blue-700"
                      : "border-border bg-background text-foreground hover:border-primary/30"
                  }`}
                >
                  <span style={{ color: presentation.color }}>
                    <Icon size={14} />
                  </span>
                  <span className="flex-1 text-left truncate">{cat.name}</span>
                </button>
              );
            })}
          </div>
        )}
      </div>

      <div className="bg-blue-50 border border-blue-100 rounded-xl p-4 mb-5 text-sm text-blue-700">
        <p className="font-semibold mb-1">
          상태: {statusFilterLabel(statusFilter)} · 매 요청 독립 랜덤
        </p>
        <p className="text-xs text-blue-600">
          Collection에 속한 항목은 개별이 아니라 Collection 하나 단위로 후보가 됩니다.
          같은 결과가 연속으로 나올 수 있습니다.
        </p>
      </div>

      {error && step === "setup" && (
        <p className="text-sm text-red-600 mb-3" role="alert" aria-live="assertive">
          {error}
        </p>
      )}

      <button
        type="button"
        aria-label="랜덤 추천 실행"
        onClick={() => void runRecommend()}
        disabled={!canRecommend}
        className="w-full bg-primary text-white py-4 rounded-xl font-semibold hover:bg-blue-700 transition-colors disabled:opacity-40 disabled:cursor-not-allowed flex items-center justify-center gap-2"
      >
        {recommendPending ? (
          <>
            <RefreshCw size={18} className="animate-spin" /> 추천 중...
          </>
        ) : (
          <>
            <Shuffle size={18} /> 추천 결과 보기
          </>
        )}
      </button>
    </div>
  );
}

export type { RecommendationCandidateType };
