import { useCallback, useEffect, useRef, useState } from "react";
import { getItems } from "../../api/catalog";
import { ApiError } from "../../api/client";
import type { ApiItemListItem } from "../../types/api";

export interface CollectionItemsReadDataState {
  items: ApiItemListItem[];
  page: number;
  pageSize: number;
  total: number;
  totalPages: number;
  hasNext: boolean;
  hasPrevious: boolean;
  isLoading: boolean;
  error: ApiError | null;
  setPage: (page: number) => void;
  reload: () => void;
}

function isAbortError(err: unknown): boolean {
  if (err instanceof DOMException && err.name === "AbortError") return true;
  if (err instanceof Error && err.name === "AbortError") return true;
  if (err instanceof ApiError) {
    if (err.message === "Request aborted") return true;
    const detail = err.detail;
    if (detail instanceof DOMException && detail.name === "AbortError") {
      return true;
    }
    if (detail instanceof Error && detail.name === "AbortError") return true;
  }
  return false;
}

function toApiError(err: unknown): ApiError {
  if (err instanceof ApiError) return err;
  if (err instanceof Error) return new ApiError(0, err.message, err);
  return new ApiError(0, "Unknown error", err);
}

const DEFAULT_PAGE_SIZE = 25;

export interface UseCollectionItemsReadDataOptions {
  enabled: boolean;
  /** Controlled page from parent (restored after Item detail). */
  page: number;
  onPageChange: (page: number) => void;
}

/**
 * Collection 소속 Item 목록.
 * page_size는 Item API 기본값(25) — 명시하지 않음.
 * sort=title&order=asc 고정.
 */
export function useCollectionItemsReadData(
  collectionId: string | null,
  options: UseCollectionItemsReadDataOptions,
): CollectionItemsReadDataState {
  const { enabled, page, onPageChange } = options;

  const [items, setItems] = useState<ApiItemListItem[]>([]);
  const [pageSize] = useState(DEFAULT_PAGE_SIZE);
  const [total, setTotal] = useState(0);
  const [totalPages, setTotalPages] = useState(0);
  const [hasNext, setHasNext] = useState(false);
  const [hasPrevious, setHasPrevious] = useState(false);
  const [isLoading, setIsLoading] = useState(false);
  const [error, setError] = useState<ApiError | null>(null);

  const genRef = useRef(0);
  const abortRef = useRef<AbortController | null>(null);
  const onPageChangeRef = useRef(onPageChange);
  onPageChangeRef.current = onPageChange;

  const clearItems = useCallback(() => {
    setItems([]);
    setTotal(0);
    setTotalPages(0);
    setHasNext(false);
    setHasPrevious(false);
    setError(null);
    setIsLoading(false);
  }, []);

  const load = useCallback(async () => {
    if (!collectionId || !enabled) {
      abortRef.current?.abort();
      clearItems();
      return;
    }

    abortRef.current?.abort();
    const controller = new AbortController();
    abortRef.current = controller;
    const gen = ++genRef.current;

    setIsLoading(true);
    setError(null);

    try {
      const data = await getItems(
        {
          collection_id: collectionId,
          sort: "title",
          order: "asc",
          page,
        },
        controller.signal,
      );
      if (gen !== genRef.current) return;
      if (data.total_pages > 0 && page > data.total_pages) {
        onPageChangeRef.current(data.total_pages);
        return;
      }
      setItems(data.items);
      setTotal(data.total);
      setTotalPages(data.total_pages);
      setHasNext(data.has_next);
      setHasPrevious(data.has_previous);
    } catch (err) {
      if (isAbortError(err) || gen !== genRef.current) return;
      console.warn("[collection-items] failed", {
        status: err instanceof ApiError ? err.status : undefined,
      });
      setItems([]);
      setTotal(0);
      setTotalPages(0);
      setHasNext(false);
      setHasPrevious(false);
      setError(toApiError(err));
    } finally {
      if (gen === genRef.current) setIsLoading(false);
    }
  }, [collectionId, enabled, page, clearItems]);

  useEffect(() => {
    void load();
    return () => {
      abortRef.current?.abort();
    };
  }, [load]);

  const setPage = useCallback((next: number) => {
    onPageChangeRef.current(Math.max(1, next));
  }, []);

  return {
    items,
    page,
    pageSize,
    total,
    totalPages,
    hasNext,
    hasPrevious,
    isLoading,
    error,
    setPage,
    reload: load,
  };
}
