import { useCallback, useEffect, useRef, useState } from "react";
import { getCategories, getItems } from "../../api/catalog";
import { ApiError } from "../../api/client";
import type {
  ApiCategory,
  ApiItemListItem,
  ApiItemSort,
  ApiSortOrder,
} from "../../types/api";

export type ItemsStatusFilter = "ALL" | "PLANNED" | "COMPLETED";
export type ItemsViewMode = "card" | "table";

/** Query filters persisted across Item Detail navigation. */
export interface ItemsQuerySnapshot {
  searchInput: string;
  appliedSearch: string;
  categoryId: string | null;
  status: ItemsStatusFilter;
  sort: ApiItemSort;
  order: ApiSortOrder;
  page: number;
  pageSize: number;
}

export interface ItemsPageStateSnapshot extends ItemsQuerySnapshot {
  viewMode: ItemsViewMode;
}

export interface ItemsReadDataState {
  categories: ApiCategory[];
  items: ApiItemListItem[];

  page: number;
  pageSize: number;
  total: number;
  totalPages: number;
  hasNext: boolean;
  hasPrevious: boolean;

  searchInput: string;
  appliedSearch: string;
  categoryId: string | null;
  status: ItemsStatusFilter;
  sort: ApiItemSort;
  order: ApiSortOrder;

  isItemsLoading: boolean;
  isCategoriesLoading: boolean;

  itemsError: ApiError | null;
  categoriesError: ApiError | null;

  setSearchInput: (value: string) => void;
  applySearchNow: () => void;
  setCategoryId: (value: string | null) => void;
  setStatus: (value: ItemsStatusFilter) => void;
  setSortPair: (sort: ApiItemSort, order: ApiSortOrder) => void;
  setPage: (value: number) => void;
  setPageSize: (value: number) => void;
  resetFilters: () => void;

  reloadItems: () => void;
  reloadCategories: () => void;
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

export interface UseItemsReadDataOptions {
  initialState?: Partial<ItemsQuerySnapshot> | null;
  onQueryChange?: (state: ItemsQuerySnapshot) => void;
}

export function useItemsReadData(
  options?: UseItemsReadDataOptions,
): ItemsReadDataState {
  const initial = options?.initialState;
  const onQueryChange = options?.onQueryChange;

  const [categories, setCategories] = useState<ApiCategory[]>([]);
  const [items, setItems] = useState<ApiItemListItem[]>([]);

  const [page, setPageState] = useState(() => initial?.page ?? 1);
  const [pageSize, setPageSizeState] = useState(
    () => initial?.pageSize ?? DEFAULT_PAGE_SIZE,
  );
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
  const [categoryId, setCategoryIdState] = useState<string | null>(
    () => initial?.categoryId ?? null,
  );
  const [status, setStatusState] = useState<ItemsStatusFilter>(
    () => initial?.status ?? "ALL",
  );
  const [sort, setSortState] = useState<ApiItemSort>(
    () => initial?.sort ?? "updated_at",
  );
  const [order, setOrderState] = useState<ApiSortOrder>(
    () => initial?.order ?? "desc",
  );

  const [isItemsLoading, setIsItemsLoading] = useState(true);
  const [isCategoriesLoading, setIsCategoriesLoading] = useState(true);
  const [itemsError, setItemsError] = useState<ApiError | null>(null);
  const [categoriesError, setCategoriesError] = useState<ApiError | null>(null);

  const itemsGen = useRef(0);
  const categoriesGen = useRef(0);
  const itemsAbort = useRef<AbortController | null>(null);
  const categoriesAbort = useRef<AbortController | null>(null);
  const debounceTimer = useRef<ReturnType<typeof setTimeout> | null>(null);
  const onQueryChangeRef = useRef(onQueryChange);
  onQueryChangeRef.current = onQueryChange;

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
      console.warn("[items] categories failed", {
        status: err instanceof ApiError ? err.status : undefined,
      });
      setCategories([]);
      setCategoriesError(toApiError(err));
    } finally {
      if (gen === categoriesGen.current) setIsCategoriesLoading(false);
    }
  }, []);

  const loadItems = useCallback(async () => {
    itemsAbort.current?.abort();
    const controller = new AbortController();
    itemsAbort.current = controller;
    const gen = ++itemsGen.current;

    setIsItemsLoading(true);
    setItemsError(null);

    try {
      const data = await getItems(
        {
          page,
          page_size: pageSize,
          search: appliedSearch || undefined,
          category_id: categoryId || undefined,
          status: status === "ALL" ? undefined : status,
          sort,
          order,
        },
        controller.signal,
      );
      if (gen !== itemsGen.current) return;
      if (data.total_pages > 0 && page > data.total_pages) {
        setPageState(data.total_pages);
        return;
      }
      setItems(data.items);
      setTotal(data.total);
      setTotalPages(data.total_pages);
      setHasNext(data.has_next);
      setHasPrevious(data.has_previous);
    } catch (err) {
      if (isAbortError(err) || gen !== itemsGen.current) return;
      console.warn("[items] list failed", {
        status: err instanceof ApiError ? err.status : undefined,
      });
      setItems([]);
      setTotal(0);
      setTotalPages(0);
      setHasNext(false);
      setHasPrevious(false);
      setItemsError(toApiError(err));
    } finally {
      if (gen === itemsGen.current) setIsItemsLoading(false);
    }
  }, [page, pageSize, appliedSearch, categoryId, status, sort, order]);

  useEffect(() => {
    void loadCategories();
    return () => {
      categoriesAbort.current?.abort();
    };
  }, [loadCategories]);

  useEffect(() => {
    void loadItems();
    return () => {
      itemsAbort.current?.abort();
    };
  }, [loadItems]);

  useEffect(() => {
    return () => {
      if (debounceTimer.current) clearTimeout(debounceTimer.current);
    };
  }, []);

  useEffect(() => {
    onQueryChangeRef.current?.({
      searchInput,
      appliedSearch,
      categoryId,
      status,
      sort,
      order,
      page,
      pageSize,
    });
  }, [
    searchInput,
    appliedSearch,
    categoryId,
    status,
    sort,
    order,
    page,
    pageSize,
  ]);

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

  const setCategoryId = useCallback((value: string | null) => {
    setCategoryIdState(value);
    setPageState(1);
  }, []);

  const setStatus = useCallback((value: ItemsStatusFilter) => {
    setStatusState(value);
    setPageState(1);
  }, []);

  const setSortPair = useCallback((nextSort: ApiItemSort, nextOrder: ApiSortOrder) => {
    setSortState(nextSort);
    setOrderState(nextOrder);
    setPageState(1);
  }, []);

  const setPage = useCallback((value: number) => {
    setPageState(Math.max(1, value));
  }, []);

  const setPageSize = useCallback((value: number) => {
    setPageSizeState(value);
    setPageState(1);
  }, []);

  const resetFilters = useCallback(() => {
    if (debounceTimer.current) clearTimeout(debounceTimer.current);
    setSearchInputState("");
    setAppliedSearch("");
    setCategoryIdState(null);
    setStatusState("ALL");
    setSortState("updated_at");
    setOrderState("desc");
    setPageSizeState(DEFAULT_PAGE_SIZE);
    setPageState(1);
  }, []);

  return {
    categories,
    items,
    page,
    pageSize,
    total,
    totalPages,
    hasNext,
    hasPrevious,
    searchInput,
    appliedSearch,
    categoryId,
    status,
    sort,
    order,
    isItemsLoading,
    isCategoriesLoading,
    itemsError,
    categoriesError,
    setSearchInput,
    applySearchNow,
    setCategoryId,
    setStatus,
    setSortPair,
    setPage,
    setPageSize,
    resetFilters,
    reloadItems: loadItems,
    reloadCategories: loadCategories,
  };
}
