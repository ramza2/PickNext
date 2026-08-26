import { useEffect, useRef, useState } from "react";
import { ChevronLeft, ChevronRight, Search, X } from "lucide-react";
import {
  addExistingItemsToCollection,
  getCategories,
  getItems,
} from "../../api/catalog";
import { ApiError } from "../../api/client";
import { ContentPoster } from "../components/ContentPoster";
import { getCategoryPresentation } from "../presentation/categoryPresentation";
import type {
  ApiCategory,
  ApiItemListItem,
  ApiItemStatus,
} from "../../types/api";

type StatusFilter = "ALL" | ApiItemStatus;

function isAbortError(err: unknown): boolean {
  if (err instanceof DOMException && err.name === "AbortError") return true;
  if (err instanceof Error && err.name === "AbortError") return true;
  if (err instanceof ApiError) {
    if (err.message === "Request aborted") return true;
    const detail = err.detail;
    if (detail instanceof DOMException && detail.name === "AbortError") return true;
    if (detail instanceof Error && detail.name === "AbortError") return true;
  }
  return false;
}

function statusLabel(status: ApiItemStatus): string {
  return status === "COMPLETED" ? "완료" : "예정";
}

export function AddExistingItemsModal({
  open,
  collectionId,
  collectionName,
  onClose,
  onAdded,
  showToast,
}: {
  open: boolean;
  collectionId: string;
  collectionName: string;
  onClose: () => void;
  onAdded: (addedCount: number) => void | Promise<void>;
  showToast: (message: string) => void;
}) {
  const titleId = "add-existing-items-title";
  const searchRef = useRef<HTMLInputElement>(null);

  const [searchInput, setSearchInput] = useState("");
  const [appliedSearch, setAppliedSearch] = useState("");
  const [categoryId, setCategoryId] = useState<string>("");
  const [status, setStatus] = useState<StatusFilter>("ALL");
  const [page, setPage] = useState(1);
  const [pageSize] = useState(20);
  const [categories, setCategories] = useState<ApiCategory[]>([]);
  const [items, setItems] = useState<ApiItemListItem[]>([]);
  const [total, setTotal] = useState(0);
  const [totalPages, setTotalPages] = useState(0);
  const [loading, setLoading] = useState(false);
  const [listError, setListError] = useState<string | null>(null);
  const [selectedIds, setSelectedIds] = useState<Set<string>>(() => new Set());
  const [pending, setPending] = useState(false);
  const [actionError, setActionError] = useState<string | null>(null);
  const requestIdRef = useRef(0);

  useEffect(() => {
    if (!open) return;
    setSearchInput("");
    setAppliedSearch("");
    setCategoryId("");
    setStatus("ALL");
    setPage(1);
    setItems([]);
    setTotal(0);
    setTotalPages(0);
    setListError(null);
    setSelectedIds(new Set());
    setPending(false);
    setActionError(null);
  }, [open, collectionId]);

  useEffect(() => {
    if (!open) return undefined;
    const timer = window.setTimeout(() => searchRef.current?.focus(), 0);
    return () => window.clearTimeout(timer);
  }, [open]);

  useEffect(() => {
    if (!open || pending) return undefined;
    const onKeyDown = (event: KeyboardEvent) => {
      if (event.key === "Escape") onClose();
    };
    window.addEventListener("keydown", onKeyDown);
    return () => window.removeEventListener("keydown", onKeyDown);
  }, [open, pending, onClose]);

  useEffect(() => {
    if (!open) return undefined;
    const controller = new AbortController();
    void (async () => {
      try {
        const response = await getCategories(controller.signal);
        if (controller.signal.aborted) return;
        setCategories(response.categories);
      } catch (err) {
        if (controller.signal.aborted || isAbortError(err)) return;
      }
    })();
    return () => controller.abort();
  }, [open]);

  useEffect(() => {
    if (!open) return undefined;
    const timer = window.setTimeout(() => {
      setAppliedSearch(searchInput.trim());
      setPage(1);
    }, 300);
    return () => window.clearTimeout(timer);
  }, [open, searchInput]);

  useEffect(() => {
    if (!open) return undefined;
    const controller = new AbortController();
    const requestId = ++requestIdRef.current;
    setLoading(true);
    setListError(null);
    void (async () => {
      try {
        const response = await getItems(
          {
            page,
            page_size: pageSize,
            search: appliedSearch || undefined,
            category_id: categoryId || undefined,
            status: status === "ALL" ? undefined : status,
            has_collection: false,
            sort: "title",
            order: "asc",
          },
          controller.signal,
        );
        if (controller.signal.aborted || requestId !== requestIdRef.current) {
          return;
        }
        setItems(response.items);
        setTotal(response.total);
        setTotalPages(response.total_pages);
      } catch (err) {
        if (
          controller.signal.aborted
          || isAbortError(err)
          || requestId !== requestIdRef.current
        ) {
          return;
        }
        setItems([]);
        setTotal(0);
        setTotalPages(0);
        setListError("항목을 불러오지 못했습니다.");
      } finally {
        if (!controller.signal.aborted && requestId === requestIdRef.current) {
          setLoading(false);
        }
      }
    })();
    return () => controller.abort();
  }, [open, page, pageSize, appliedSearch, categoryId, status]);

  const toggleItem = (itemId: string) => {
    if (pending) return;
    setSelectedIds((prev) => {
      const next = new Set(prev);
      if (next.has(itemId)) next.delete(itemId);
      else next.add(itemId);
      return next;
    });
  };

  const handleSubmit = async () => {
    if (pending || selectedIds.size === 0) return;
    setPending(true);
    setActionError(null);
    try {
      const result = await addExistingItemsToCollection(
        collectionId,
        Array.from(selectedIds),
      );
      await onAdded(result.added_count);
      showToast(
        result.added_count > 0
          ? `${result.added_count}개 항목을 Collection에 추가했습니다.`
          : "선택한 항목이 이미 Collection에 포함되어 있습니다.",
      );
      onClose();
    } catch (err) {
      if (err instanceof ApiError && err.status === 409) {
        setActionError(
          "일부 항목의 Collection 상태가 변경되었습니다. 목록을 새로고침한 뒤 다시 선택해 주세요.",
        );
        setSelectedIds(new Set());
        setPage(1);
        setAppliedSearch((value) => value);
        // Force reload by bumping applied search identity via page reset effect;
        // also re-trigger fetch by toggling a noop on search.
        requestIdRef.current += 1;
        setLoading(true);
        try {
          const response = await getItems({
            page: 1,
            page_size: pageSize,
            search: appliedSearch || undefined,
            category_id: categoryId || undefined,
            status: status === "ALL" ? undefined : status,
            has_collection: false,
            sort: "title",
            order: "asc",
          });
          setItems(response.items);
          setTotal(response.total);
          setTotalPages(response.total_pages);
          setPage(1);
        } catch {
          setListError("항목을 불러오지 못했습니다.");
        } finally {
          setLoading(false);
        }
      } else if (err instanceof ApiError && err.status === 404) {
        setActionError("Collection 또는 항목을 찾을 수 없습니다.");
      } else {
        setActionError("항목을 추가하지 못했습니다. 잠시 후 다시 시도해 주세요.");
      }
    } finally {
      setPending(false);
    }
  };

  if (!open) return null;

  const selectedCount = selectedIds.size;
  const emptyMessage = appliedSearch
    ? `"${appliedSearch}"에 해당하는 항목이 없습니다.`
    : "추가할 수 있는 미지정 항목이 없습니다.";

  return (
    <div
      className="fixed inset-0 bg-black/50 z-50 flex items-end sm:items-center justify-center p-0 sm:p-4 pb-16 sm:pb-4"
      role="dialog"
      aria-modal="true"
      aria-labelledby={titleId}
      onClick={() => {
        if (!pending) onClose();
      }}
    >
      <div
        className="bg-card rounded-t-2xl sm:rounded-2xl w-full max-w-lg shadow-2xl flex flex-col max-h-[min(92dvh,calc(100dvh-5rem))]"
        onClick={(event) => event.stopPropagation()}
      >
        <div className="flex items-center justify-between gap-3 px-5 pt-5 pb-3 border-b border-border flex-shrink-0">
          <div className="min-w-0">
            <h3 id={titleId} className="text-base font-bold text-foreground">
              기존 항목 추가
            </h3>
            <p className="text-xs text-muted-foreground truncate mt-0.5">
              {collectionName}
            </p>
          </div>
          <button
            type="button"
            disabled={pending}
            onClick={onClose}
            className="p-1.5 rounded-lg text-muted-foreground hover:text-foreground hover:bg-muted disabled:opacity-50"
            aria-label="닫기"
          >
            <X size={18} />
          </button>
        </div>

        <div className="px-5 pt-3 pb-2 space-y-2 flex-shrink-0">
          <label className="sr-only" htmlFor="add-existing-search">
            제목 검색
          </label>
          <div className="relative">
            <Search
              size={14}
              className="absolute left-3 top-1/2 -translate-y-1/2 text-muted-foreground"
            />
            <input
              ref={searchRef}
              id="add-existing-search"
              value={searchInput}
              onChange={(event) => setSearchInput(event.target.value)}
              placeholder="제목 검색"
              disabled={pending}
              className="w-full pl-9 pr-3 py-2.5 border border-border rounded-xl text-sm bg-background focus:outline-none focus:ring-2 focus:ring-primary/25 disabled:opacity-50"
            />
          </div>
          <div className="flex gap-2">
            <select
              value={categoryId}
              onChange={(event) => {
                setCategoryId(event.target.value);
                setPage(1);
              }}
              disabled={pending}
              aria-label="Category Filter"
              className="flex-1 min-w-0 px-2.5 py-2 border border-border rounded-xl text-xs bg-background disabled:opacity-50"
            >
              <option value="">전체 Category</option>
              {categories.map((category) => (
                <option key={category.id} value={category.id}>
                  {category.name}
                </option>
              ))}
            </select>
            <select
              value={status}
              onChange={(event) => {
                setStatus(event.target.value as StatusFilter);
                setPage(1);
              }}
              disabled={pending}
              aria-label="상태 Filter"
              className="w-[7.5rem] flex-shrink-0 px-2.5 py-2 border border-border rounded-xl text-xs bg-background disabled:opacity-50"
            >
              <option value="ALL">전체 상태</option>
              <option value="PLANNED">예정</option>
              <option value="COMPLETED">완료</option>
            </select>
          </div>
        </div>

        <div className="flex-1 min-h-0 overflow-y-auto px-3 pb-2">
          {loading && items.length === 0 ? (
            <p className="text-sm text-muted-foreground text-center py-10">검색 중…</p>
          ) : listError ? (
            <p className="text-sm text-red-600 text-center py-10 px-2">{listError}</p>
          ) : items.length === 0 ? (
            <p className="text-sm text-muted-foreground text-center py-10 px-2">
              {emptyMessage}
            </p>
          ) : (
            <ul className={`space-y-1 ${loading ? "opacity-70" : ""}`}>
              {items.map((item) => {
                const selected = selectedIds.has(item.id);
                const presentation = getCategoryPresentation(item.category.name);
                return (
                  <li key={item.id}>
                    <button
                      type="button"
                      disabled={pending}
                      onClick={() => toggleItem(item.id)}
                      className={`w-full text-left px-2.5 py-2 rounded-xl flex items-center gap-2.5 transition-colors disabled:opacity-50 ${
                        selected
                          ? "bg-primary/10 ring-1 ring-primary/30"
                          : "hover:bg-muted"
                      }`}
                    >
                      <input
                        type="checkbox"
                        checked={selected}
                        readOnly
                        tabIndex={-1}
                        className="accent-primary flex-shrink-0"
                        aria-hidden="true"
                      />
                      <ContentPoster
                        src={item.poster_url}
                        title={item.title}
                        fallbackColor={presentation.color}
                        size="xs"
                      />
                      <div className="min-w-0 flex-1">
                        <div className="text-sm font-medium text-foreground truncate">
                          {item.title}
                          {item.release_year != null ? (
                            <span className="text-muted-foreground font-normal">
                              {" "}({item.release_year})
                            </span>
                          ) : null}
                        </div>
                        <div className="text-[11px] text-muted-foreground mt-0.5 truncate">
                          {item.category.name} / {statusLabel(item.status)}
                        </div>
                      </div>
                    </button>
                  </li>
                );
              })}
            </ul>
          )}
        </div>

        {totalPages > 1 && (
          <div className="px-5 py-2 border-t border-border flex items-center justify-between text-xs text-muted-foreground flex-shrink-0">
            <button
              type="button"
              disabled={pending || page <= 1}
              onClick={() => setPage((value) => Math.max(1, value - 1))}
              className="inline-flex items-center gap-1 disabled:opacity-40"
            >
              <ChevronLeft size={14} /> 이전
            </button>
            <span>
              {page} / {totalPages}
              {total > 0 ? ` · ${total}건` : ""}
            </span>
            <button
              type="button"
              disabled={pending || page >= totalPages}
              onClick={() => setPage((value) => value + 1)}
              className="inline-flex items-center gap-1 disabled:opacity-40"
            >
              다음 <ChevronRight size={14} />
            </button>
          </div>
        )}

        <div className="px-5 py-3 border-t border-border flex-shrink-0 space-y-3">
          <p className="text-xs text-muted-foreground text-center">
            선택 {selectedCount}개
          </p>
          {actionError && (
            <p className="text-xs text-red-600 text-center" role="alert">
              {actionError}
            </p>
          )}
          <div className="flex gap-3">
            <button
              type="button"
              disabled={pending}
              onClick={onClose}
              className="flex-1 border border-border text-foreground py-2.5 rounded-xl font-medium hover:bg-muted transition-colors text-sm disabled:opacity-50"
            >
              취소
            </button>
            <button
              type="button"
              disabled={pending || selectedCount === 0}
              onClick={() => void handleSubmit()}
              className="flex-1 bg-primary hover:bg-blue-700 text-white py-2.5 rounded-xl font-medium transition-colors text-sm disabled:opacity-50 disabled:cursor-not-allowed"
            >
              {pending ? "추가 중..." : "선택 항목 추가"}
            </button>
          </div>
        </div>
      </div>
    </div>
  );
}
