import { useCallback, useEffect, useRef, useState } from "react";
import { getCollections } from "../../api/catalog";
import { ApiError } from "../../api/client";
import type { ApiCollection } from "../../types/api";

export interface CollectionsQuerySnapshot {
  searchInput: string;
  appliedSearch: string;
  page: number;
  pageSize: number;
}

export interface CollectionsReadDataState {
  collections: ApiCollection[];

  page: number;
  pageSize: number;
  total: number;
  totalPages: number;
  hasNext: boolean;
  hasPrevious: boolean;

  searchInput: string;
  appliedSearch: string;

  isLoading: boolean;
  error: ApiError | null;

  setSearchInput: (value: string) => void;
  applySearchNow: () => void;
  clearSearch: () => void;
  setPage: (value: number) => void;
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

function normalizeSearch(value: string): string {
  return value.trim();
}

const DEFAULT_PAGE_SIZE = 25;

export interface UseCollectionsReadDataOptions {
  initialState?: Partial<CollectionsQuerySnapshot> | null;
  onQueryChange?: (state: CollectionsQuerySnapshot) => void;
}

export function useCollectionsReadData(
  options?: UseCollectionsReadDataOptions,
): CollectionsReadDataState {
  const initial = options?.initialState;
  const onQueryChange = options?.onQueryChange;

  const [collections, setCollections] = useState<ApiCollection[]>([]);
  const [page, setPageState] = useState(() => initial?.page ?? 1);
  const [pageSize] = useState(() => initial?.pageSize ?? DEFAULT_PAGE_SIZE);
  const [total, setTotal] = useState(0);
  const [totalPages, setTotalPages] = useState(0);
  const [hasNext, setHasNext] = useState(false);
  const [hasPrevious, setHasPrevious] = useState(false);

  const [searchInput, setSearchInputState] = useState(
    () => initial?.searchInput ?? "",
  );
  const [appliedSearch, setAppliedSearch] = useState(
    () => initial?.appliedSearch ?? "",
  );

  const [isLoading, setIsLoading] = useState(true);
  const [error, setError] = useState<ApiError | null>(null);

  const gen = useRef(0);
  const abortRef = useRef<AbortController | null>(null);
  const debounceTimer = useRef<ReturnType<typeof setTimeout> | null>(null);
  const onQueryChangeRef = useRef(onQueryChange);
  onQueryChangeRef.current = onQueryChange;

  const loadCollections = useCallback(async () => {
    abortRef.current?.abort();
    const controller = new AbortController();
    abortRef.current = controller;
    const requestGen = ++gen.current;

    setIsLoading(true);
    setError(null);

    try {
      const data = await getCollections(
        {
          page,
          page_size: pageSize,
          search: appliedSearch || undefined,
        },
        controller.signal,
      );
      if (requestGen !== gen.current) return;
      setCollections(data.collections);
      setTotal(data.total);
      setTotalPages(data.total_pages);
      setHasNext(data.has_next);
      setHasPrevious(data.has_previous);
    } catch (err) {
      if (isAbortError(err) || requestGen !== gen.current) return;
      console.warn("[collections] list failed", {
        status: err instanceof ApiError ? err.status : undefined,
      });
      setCollections([]);
      setTotal(0);
      setTotalPages(0);
      setHasNext(false);
      setHasPrevious(false);
      setError(toApiError(err));
    } finally {
      if (requestGen === gen.current) setIsLoading(false);
    }
  }, [page, pageSize, appliedSearch]);

  useEffect(() => {
    void loadCollections();
    return () => {
      abortRef.current?.abort();
    };
  }, [loadCollections]);

  useEffect(() => {
    return () => {
      if (debounceTimer.current) clearTimeout(debounceTimer.current);
    };
  }, []);

  useEffect(() => {
    onQueryChangeRef.current?.({
      searchInput,
      appliedSearch,
      page,
      pageSize,
    });
  }, [searchInput, appliedSearch, page, pageSize]);

  const setSearchInput = useCallback((value: string) => {
    setSearchInputState(value);
    if (debounceTimer.current) clearTimeout(debounceTimer.current);
    debounceTimer.current = setTimeout(() => {
      const next = normalizeSearch(value);
      setAppliedSearch((prev) => {
        if (prev === next) return prev;
        setPageState(1);
        return next;
      });
    }, 300);
  }, []);

  const applySearchNow = useCallback(() => {
    if (debounceTimer.current) clearTimeout(debounceTimer.current);
    const next = normalizeSearch(searchInput);
    setAppliedSearch((prev) => {
      if (prev === next) return prev;
      setPageState(1);
      return next;
    });
  }, [searchInput]);

  const clearSearch = useCallback(() => {
    if (debounceTimer.current) clearTimeout(debounceTimer.current);
    setSearchInputState("");
    setAppliedSearch("");
    setPageState(1);
  }, []);

  const setPage = useCallback((value: number) => {
    setPageState(Math.max(1, value));
  }, []);

  return {
    collections,
    page,
    pageSize,
    total,
    totalPages,
    hasNext,
    hasPrevious,
    searchInput,
    appliedSearch,
    isLoading,
    error,
    setSearchInput,
    applySearchNow,
    clearSearch,
    setPage,
    reload: loadCollections,
  };
}
