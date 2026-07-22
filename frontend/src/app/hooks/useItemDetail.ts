import { useCallback, useEffect, useRef, useState } from "react";
import { getItem } from "../../api/catalog";
import { ApiError } from "../../api/client";
import type { ApiItemDetail } from "../../types/api";

export interface ItemDetailState {
  item: ApiItemDetail | null;
  isLoading: boolean;
  error: ApiError | null;
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

export function useItemDetail(itemId: string | null): ItemDetailState {
  const [item, setItem] = useState<ApiItemDetail | null>(null);
  const [isLoading, setIsLoading] = useState(Boolean(itemId));
  const [error, setError] = useState<ApiError | null>(null);

  const genRef = useRef(0);
  const abortRef = useRef<AbortController | null>(null);

  const load = useCallback(async () => {
    if (!itemId) {
      abortRef.current?.abort();
      setItem(null);
      setError(null);
      setIsLoading(false);
      return;
    }

    abortRef.current?.abort();
    const controller = new AbortController();
    abortRef.current = controller;
    const gen = ++genRef.current;

    setIsLoading(true);
    setError(null);
    setItem(null);

    try {
      const data = await getItem(itemId, controller.signal);
      if (gen !== genRef.current) return;
      setItem(data);
    } catch (err) {
      if (isAbortError(err) || gen !== genRef.current) return;
      console.warn("[item-detail] failed", {
        status: err instanceof ApiError ? err.status : undefined,
      });
      setItem(null);
      setError(toApiError(err));
    } finally {
      if (gen === genRef.current) setIsLoading(false);
    }
  }, [itemId]);

  useEffect(() => {
    void load();
    return () => {
      abortRef.current?.abort();
    };
  }, [load]);

  return {
    item,
    isLoading,
    error,
    reload: load,
  };
}
