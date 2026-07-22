import { useCallback, useEffect, useRef, useState } from "react";
import { getCollection } from "../../api/catalog";
import { ApiError } from "../../api/client";
import type { ApiCollection } from "../../types/api";

export interface CollectionDetailState {
  collection: ApiCollection | null;
  isLoading: boolean;
  error: ApiError | null;
  isNotFound: boolean;
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

export function useCollectionDetail(
  collectionId: string | null,
): CollectionDetailState {
  const [collection, setCollection] = useState<ApiCollection | null>(null);
  const [isLoading, setIsLoading] = useState(Boolean(collectionId));
  const [error, setError] = useState<ApiError | null>(null);

  const genRef = useRef(0);
  const abortRef = useRef<AbortController | null>(null);

  const load = useCallback(async () => {
    if (!collectionId) {
      abortRef.current?.abort();
      setCollection(null);
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
    setCollection(null);

    try {
      const data = await getCollection(collectionId, controller.signal);
      if (gen !== genRef.current) return;
      setCollection(data);
    } catch (err) {
      if (isAbortError(err) || gen !== genRef.current) return;
      console.warn("[collection-detail] failed", {
        status: err instanceof ApiError ? err.status : undefined,
      });
      setCollection(null);
      setError(toApiError(err));
    } finally {
      if (gen === genRef.current) setIsLoading(false);
    }
  }, [collectionId]);

  useEffect(() => {
    void load();
    return () => {
      abortRef.current?.abort();
    };
  }, [load]);

  return {
    collection,
    isLoading,
    error,
    isNotFound: error?.status === 404,
    reload: load,
  };
}
