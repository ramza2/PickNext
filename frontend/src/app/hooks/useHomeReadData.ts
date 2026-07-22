import { useCallback, useEffect, useRef, useState } from "react";
import { getCategories, getItems, getSummary } from "../../api/catalog";
import { ApiError } from "../../api/client";
import type {
  ApiCategory,
  ApiItemListItem,
  ApiSummaryResponse,
} from "../../types/api";

export interface HomeReadDataState {
  summary: ApiSummaryResponse | null;
  categories: ApiCategory[];
  recentItems: ApiItemListItem[];

  isLoading: boolean;
  isSummaryLoading: boolean;
  isCategoriesLoading: boolean;
  isRecentItemsLoading: boolean;

  summaryError: ApiError | null;
  categoriesError: ApiError | null;
  recentItemsError: ApiError | null;

  reloadAll: () => void;
  reloadSummary: () => void;
  reloadCategories: () => void;
  reloadRecentItems: () => void;
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

export function useHomeReadData(): HomeReadDataState {
  const [summary, setSummary] = useState<ApiSummaryResponse | null>(null);
  const [categories, setCategories] = useState<ApiCategory[]>([]);
  const [recentItems, setRecentItems] = useState<ApiItemListItem[]>([]);

  const [isSummaryLoading, setIsSummaryLoading] = useState(true);
  const [isCategoriesLoading, setIsCategoriesLoading] = useState(true);
  const [isRecentItemsLoading, setIsRecentItemsLoading] = useState(true);

  const [summaryError, setSummaryError] = useState<ApiError | null>(null);
  const [categoriesError, setCategoriesError] = useState<ApiError | null>(null);
  const [recentItemsError, setRecentItemsError] = useState<ApiError | null>(
    null,
  );

  const summaryGen = useRef(0);
  const categoriesGen = useRef(0);
  const recentGen = useRef(0);
  const summaryAbort = useRef<AbortController | null>(null);
  const categoriesAbort = useRef<AbortController | null>(null);
  const recentAbort = useRef<AbortController | null>(null);

  const loadSummary = useCallback(async () => {
    summaryAbort.current?.abort();
    const controller = new AbortController();
    summaryAbort.current = controller;
    const gen = ++summaryGen.current;

    setIsSummaryLoading(true);
    setSummaryError(null);

    try {
      const data = await getSummary(controller.signal);
      if (gen !== summaryGen.current) return;
      setSummary(data);
    } catch (err) {
      if (isAbortError(err) || gen !== summaryGen.current) return;
      console.warn("[home] summary failed", {
        status: err instanceof ApiError ? err.status : undefined,
      });
      setSummary(null);
      setSummaryError(toApiError(err));
    } finally {
      if (gen === summaryGen.current) setIsSummaryLoading(false);
    }
  }, []);

  const loadCategories = useCallback(async () => {
    categoriesAbort.current?.abort();
    const controller = new AbortController();
    categoriesAbort.current = controller;
    const gen = ++categoriesGen.current;

    setIsCategoriesLoading(true);
    setCategoriesError(null);

    try {
      const data = await getCategories(controller.signal);
      if (gen !== categoriesGen.current) return;
      setCategories(data.categories);
    } catch (err) {
      if (isAbortError(err) || gen !== categoriesGen.current) return;
      console.warn("[home] categories failed", {
        status: err instanceof ApiError ? err.status : undefined,
      });
      setCategories([]);
      setCategoriesError(toApiError(err));
    } finally {
      if (gen === categoriesGen.current) setIsCategoriesLoading(false);
    }
  }, []);

  const loadRecentItems = useCallback(async () => {
    recentAbort.current?.abort();
    const controller = new AbortController();
    recentAbort.current = controller;
    const gen = ++recentGen.current;

    setIsRecentItemsLoading(true);
    setRecentItemsError(null);

    try {
      const data = await getItems(
        {
          page: 1,
          page_size: 5,
          sort: "created_at",
          order: "desc",
        },
        controller.signal,
      );
      if (gen !== recentGen.current) return;
      setRecentItems(data.items);
    } catch (err) {
      if (isAbortError(err) || gen !== recentGen.current) return;
      console.warn("[home] recent items failed", {
        status: err instanceof ApiError ? err.status : undefined,
      });
      setRecentItems([]);
      setRecentItemsError(toApiError(err));
    } finally {
      if (gen === recentGen.current) setIsRecentItemsLoading(false);
    }
  }, []);

  const reloadAll = useCallback(() => {
    void loadSummary();
    void loadCategories();
    void loadRecentItems();
  }, [loadSummary, loadCategories, loadRecentItems]);

  useEffect(() => {
    reloadAll();
    return () => {
      summaryAbort.current?.abort();
      categoriesAbort.current?.abort();
      recentAbort.current?.abort();
    };
  }, [reloadAll]);

  return {
    summary,
    categories,
    recentItems,
    isLoading:
      isSummaryLoading || isCategoriesLoading || isRecentItemsLoading,
    isSummaryLoading,
    isCategoriesLoading,
    isRecentItemsLoading,
    summaryError,
    categoriesError,
    recentItemsError,
    reloadAll,
    reloadSummary: loadSummary,
    reloadCategories: loadCategories,
    reloadRecentItems: loadRecentItems,
  };
}
