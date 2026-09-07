import { useCallback, useEffect, useRef, useState } from "react";
import type { FormEvent } from "react";
import { Check, ChevronLeft, Plus, X } from "lucide-react";
import {
  createCollection,
  getCollections,
  updateItem,
} from "../../api/catalog";
import { ApiError } from "../../api/client";
import {
  collectionCreateFailureToast,
  collectionWriteConflictInline,
  collectionWriteValidationInline,
  normalizeCollectionNameInput,
  validateCollectionName,
} from "../../api/collectionWriteMessages";
import type { ApiCollection, ApiItemDetail } from "../../types/api";
import { ClearableSearchInput } from "../components/ClearableSearchInput";

type PickerView = "picker" | "create";

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

type SharedProps = {
  open: boolean;
  onClose: () => void;
  showToast: (message: string) => void;
  /** Override dialog title. */
  title?: string;
};

export type CollectionPickerImmediateProps = SharedProps & {
  mode: "immediate";
  item: ApiItemDetail;
  onAssigned: (item: ApiItemDetail) => void;
};

export type CollectionPickerSelectProps = SharedProps & {
  mode: "select";
  currentCollection?: { id: string; name: string } | null;
  allowClear?: boolean;
  onSelect: (collection: ApiCollection | null) => void;
};

export type CollectionPickerModalProps =
  | CollectionPickerImmediateProps
  | CollectionPickerSelectProps;

export function CollectionPickerModal(props: CollectionPickerModalProps) {
  const { open, onClose, showToast, title } = props;
  const isImmediate = props.mode === "immediate";
  const item = isImmediate ? props.item : null;
  const currentCollectionId = isImmediate
    ? (item?.collection?.id ?? null)
    : (props.currentCollection?.id ?? null);
  const currentCollectionName = isImmediate
    ? (item?.collection?.name ?? null)
    : (props.currentCollection?.name ?? null);
  const allowClear = isImmediate
    ? Boolean(currentCollectionId)
    : Boolean(props.allowClear);

  const hasCollection = Boolean(currentCollectionId);
  const titleId = "collection-picker-title";
  const searchRef = useRef<HTMLInputElement>(null);
  const createNameRef = useRef<HTMLInputElement>(null);

  const [view, setView] = useState<PickerView>("picker");
  const [searchInput, setSearchInput] = useState("");
  const [appliedSearch, setAppliedSearch] = useState("");
  const [collections, setCollections] = useState<ApiCollection[]>([]);
  const [loading, setLoading] = useState(false);
  const [listError, setListError] = useState<string | null>(null);
  const [selectedId, setSelectedId] = useState<string | null>(currentCollectionId);
  const [pending, setPending] = useState(false);
  const [actionError, setActionError] = useState<string | null>(null);

  const [createName, setCreateName] = useState("");
  const [createValidationError, setCreateValidationError] = useState<string | null>(null);
  const [createServerError, setCreateServerError] = useState<string | null>(null);
  const [createdCollection, setCreatedCollection] = useState<ApiCollection | null>(null);

  const isSameSelection =
    selectedId != null && selectedId === currentCollectionId;
  const canSubmit = isImmediate
    ? selectedId != null && !isSameSelection && !pending
    : selectedId != null && !pending;

  useEffect(() => {
    if (!open) return;
    setView("picker");
    setSearchInput("");
    setAppliedSearch("");
    setCollections([]);
    setListError(null);
    setSelectedId(currentCollectionId);
    setPending(false);
    setActionError(null);
    setCreateName("");
    setCreateValidationError(null);
    setCreateServerError(null);
    setCreatedCollection(null);
  }, [open, currentCollectionId, item?.id]);

  useEffect(() => {
    if (!open || view !== "picker") return undefined;
    const timer = window.setTimeout(() => searchRef.current?.focus(), 0);
    return () => window.clearTimeout(timer);
  }, [open, view]);

  useEffect(() => {
    if (!open || view !== "create") return undefined;
    const timer = window.setTimeout(() => createNameRef.current?.focus(), 0);
    return () => window.clearTimeout(timer);
  }, [open, view]);

  useEffect(() => {
    if (!open || pending) return undefined;
    const onKeyDown = (event: KeyboardEvent) => {
      if (event.key === "Escape") onClose();
    };
    window.addEventListener("keydown", onKeyDown);
    return () => window.removeEventListener("keydown", onKeyDown);
  }, [open, pending, onClose]);

  useEffect(() => {
    if (!open || view !== "picker") return undefined;
    const timer = window.setTimeout(() => {
      setAppliedSearch(searchInput.trim());
    }, 300);
    return () => window.clearTimeout(timer);
  }, [open, view, searchInput]);

  useEffect(() => {
    if (!open || view !== "picker") return undefined;
    const controller = new AbortController();
    setLoading(true);
    setListError(null);
    void (async () => {
      try {
        const response = await getCollections(
          {
            page: 1,
            page_size: 50,
            search: appliedSearch || undefined,
            sort: "name",
            order: "asc",
          },
          controller.signal,
        );
        if (controller.signal.aborted) return;
        setCollections(response.collections);
      } catch (err) {
        if (controller.signal.aborted || isAbortError(err)) return;
        setCollections([]);
        setListError("Collection 목록을 불러오지 못했습니다.");
      } finally {
        if (!controller.signal.aborted) setLoading(false);
      }
    })();
    return () => controller.abort();
  }, [open, view, appliedSearch]);

  const finishSelect = useCallback((collection: ApiCollection | null) => {
    if (props.mode !== "select") return;
    props.onSelect(collection);
    onClose();
  }, [onClose, props]);

  const assignToCollection = useCallback(async (collectionId: string) => {
    if (props.mode !== "immediate" || !item || pending) return;
    if (collectionId === currentCollectionId) return;
    setPending(true);
    setActionError(null);
    try {
      const updated = await updateItem(item.id, { collection_id: collectionId });
      props.onAssigned(updated);
      showToast(
        hasCollection
          ? "Collection을 변경했습니다."
          : "Collection에 추가했습니다.",
      );
      onClose();
    } catch (err) {
      if (err instanceof ApiError && err.status === 404) {
        setActionError("항목 또는 Collection을 찾을 수 없습니다.");
      } else if (err instanceof ApiError && err.status === 409) {
        setActionError("상태가 변경되었습니다. 다시 시도해 주세요.");
      } else {
        setActionError(
          hasCollection
            ? "Collection을 변경하지 못했습니다."
            : "Collection에 추가하지 못했습니다.",
        );
      }
    } finally {
      setPending(false);
    }
  }, [currentCollectionId, hasCollection, item, onClose, pending, props, showToast]);

  const handleConfirm = async () => {
    if (!selectedId || pending) return;
    if (isImmediate) {
      await assignToCollection(selectedId);
      return;
    }
    const selected = collections.find((row) => row.id === selectedId)
      ?? (createdCollection?.id === selectedId ? createdCollection : null);
    if (!selected) {
      setActionError("선택한 Collection을 찾을 수 없습니다.");
      return;
    }
    finishSelect(selected);
  };

  const handleClear = async () => {
    if (pending || !allowClear) return;
    if (isImmediate && item) {
      setPending(true);
      setActionError(null);
      try {
        const updated = await updateItem(item.id, { collection_id: null });
        props.onAssigned(updated);
        showToast("Collection에서 제거했습니다.");
        onClose();
      } catch (err) {
        if (err instanceof ApiError && err.status === 404) {
          setActionError("항목을 찾을 수 없습니다.");
        } else {
          setActionError("Collection에서 제거하지 못했습니다.");
        }
      } finally {
        setPending(false);
      }
      return;
    }
    finishSelect(null);
  };

  const handleCreate = async (event?: FormEvent) => {
    event?.preventDefault();
    if (pending) return;

    if (createdCollection) {
      if (isImmediate) {
        await assignToCollection(createdCollection.id);
      } else {
        finishSelect(createdCollection);
      }
      return;
    }

    const normalized = normalizeCollectionNameInput(createName);
    const validation = validateCollectionName(normalized);
    if (validation) {
      setCreateValidationError(validation);
      setCreateServerError(null);
      return;
    }

    setPending(true);
    setCreateValidationError(null);
    setCreateServerError(null);
    setActionError(null);
    try {
      const created = await createCollection({ name: normalized });
      setCreatedCollection(created);
      setSelectedId(created.id);
      setCollections((prev) => {
        if (prev.some((row) => row.id === created.id)) return prev;
        return [created, ...prev];
      });

      if (isImmediate && item) {
        try {
          const updated = await updateItem(item.id, {
            collection_id: created.id,
          });
          props.onAssigned(updated);
          showToast("Collection을 만들고 항목을 추가했습니다.");
          onClose();
        } catch {
          setView("picker");
          setActionError(
            "Collection은 생성되었지만 항목 추가에 실패했습니다. 다시 시도해 주세요.",
          );
        }
      } else {
        showToast("Collection을 만들었습니다.");
        finishSelect(created);
      }
    } catch (err) {
      if (err instanceof ApiError && err.status === 409) {
        setCreateServerError(collectionWriteConflictInline());
      } else if (err instanceof ApiError && err.status === 422) {
        setCreateServerError(collectionWriteValidationInline());
      } else {
        setCreateServerError(collectionCreateFailureToast());
      }
    } finally {
      setPending(false);
    }
  };

  if (!open) return null;

  const modalTitle = title
    ?? (isImmediate
      ? (hasCollection ? "Collection 변경" : "Collection에 추가")
      : "Collection 선택");
  const primaryLabel = isImmediate
    ? (hasCollection
      ? (pending ? "변경 중..." : "변경")
      : (pending ? "추가 중..." : "추가"))
    : (pending ? "선택 중..." : "선택");

  return (
    <div
      className="fixed inset-0 bg-black/50 z-[60] flex items-end sm:items-center justify-center p-0 sm:p-4 pb-16 sm:pb-4"
      role="dialog"
      aria-modal="true"
      aria-labelledby={titleId}
      onClick={(event) => {
        event.stopPropagation();
        if (!pending) onClose();
      }}
    >
      <div
        className="bg-card rounded-t-2xl sm:rounded-2xl w-full max-w-md shadow-2xl flex flex-col max-h-[min(90dvh,calc(100dvh-5rem))]"
        onClick={(event) => event.stopPropagation()}
      >
        <div className="flex items-center justify-between gap-3 px-5 pt-5 pb-3 border-b border-border flex-shrink-0">
          <div className="flex items-center gap-2 min-w-0">
            {view === "create" && (
              <button
                type="button"
                disabled={pending}
                onClick={() => {
                  if (pending) return;
                  setView("picker");
                  setCreateValidationError(null);
                  setCreateServerError(null);
                }}
                className="p-1 rounded-lg text-muted-foreground hover:text-foreground hover:bg-muted disabled:opacity-50"
                aria-label="목록으로"
              >
                <ChevronLeft size={18} />
              </button>
            )}
            <h3 id={titleId} className="text-base font-bold text-foreground truncate">
              {view === "create" ? "새 Collection" : modalTitle}
            </h3>
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

        {view === "picker" ? (
          <>
            <div className="px-5 pt-3 pb-2 flex-shrink-0">
              <label className="sr-only" htmlFor="collection-picker-search">
                Collection 이름 검색
              </label>
              <ClearableSearchInput
                id="collection-picker-search"
                inputRef={searchRef}
                value={searchInput}
                onChange={setSearchInput}
                placeholder="Collection 이름 검색"
                disabled={pending}
                className="bg-background focus:outline-none focus:ring-2 focus:ring-primary/25 disabled:opacity-50"
              />
              {currentCollectionId && (
                <p className="text-xs text-muted-foreground mt-2">
                  현재: {currentCollectionName ?? "미지정"}
                </p>
              )}
            </div>

            <div className="flex-1 min-h-0 overflow-y-auto px-3 pb-2">
              {loading ? (
                <p className="text-sm text-muted-foreground text-center py-8">검색 중…</p>
              ) : listError ? (
                <p className="text-sm text-red-600 text-center py-8 px-2">{listError}</p>
              ) : collections.length === 0 ? (
                <p className="text-sm text-muted-foreground text-center py-8 px-2">
                  {appliedSearch
                    ? `"${appliedSearch}"에 해당하는 Collection이 없습니다.`
                    : "등록된 Collection이 없습니다."}
                </p>
              ) : (
                <ul className="space-y-1" role="listbox" aria-label="Collection 검색 결과">
                  {collections.map((collection) => {
                    const selected = selectedId === collection.id;
                    const isCurrent = collection.id === currentCollectionId;
                    return (
                      <li key={collection.id}>
                        <button
                          type="button"
                          role="option"
                          aria-selected={selected}
                          disabled={pending}
                          onClick={() => setSelectedId(collection.id)}
                          className={`w-full text-left px-3 py-2.5 rounded-xl text-sm flex items-center gap-2 transition-colors disabled:opacity-50 ${
                            selected
                              ? "bg-primary/10 text-foreground ring-1 ring-primary/30"
                              : "hover:bg-muted text-foreground"
                          }`}
                        >
                          <span
                            className={`w-4 h-4 rounded-full border flex items-center justify-center flex-shrink-0 ${
                              selected
                                ? "border-primary bg-primary text-white"
                                : "border-border"
                            }`}
                          >
                            {selected ? <Check size={10} /> : null}
                          </span>
                          <span className="min-w-0 flex-1 truncate font-medium">
                            {collection.name}
                          </span>
                          {isCurrent && (
                            <span className="text-[10px] text-muted-foreground flex-shrink-0">
                              현재
                            </span>
                          )}
                        </button>
                      </li>
                    );
                  })}
                </ul>
              )}
            </div>

            <div className="px-5 py-3 border-t border-border flex-shrink-0 space-y-3">
              <button
                type="button"
                disabled={pending}
                onClick={() => {
                  setView("create");
                  setCreateValidationError(null);
                  setCreateServerError(null);
                }}
                className="w-full flex items-center justify-center gap-1.5 text-sm text-primary border border-primary/25 py-2.5 rounded-xl hover:bg-blue-50 transition-colors disabled:opacity-50"
              >
                <Plus size={14} /> 새 Collection 만들기
              </button>

              {allowClear && currentCollectionId && (
                <button
                  type="button"
                  disabled={pending}
                  onClick={() => void handleClear()}
                  className="w-full text-sm text-muted-foreground py-2 hover:text-foreground transition-colors disabled:opacity-50"
                >
                  {isImmediate ? "Collection에서 제거" : "Collection 없음"}
                </button>
              )}

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
                  disabled={!canSubmit}
                  onClick={() => void handleConfirm()}
                  className="flex-1 bg-primary hover:bg-blue-700 text-white py-2.5 rounded-xl font-medium transition-colors text-sm disabled:opacity-50 disabled:cursor-not-allowed"
                >
                  {primaryLabel}
                </button>
              </div>
            </div>
          </>
        ) : (
          <form
            className="px-5 py-4 flex flex-col gap-4"
            onSubmit={(event) => void handleCreate(event)}
          >
            <div>
              <label
                htmlFor="collection-picker-create-name"
                className="block text-sm font-medium text-foreground mb-1.5"
              >
                Collection 이름 *
              </label>
              <input
                ref={createNameRef}
                id="collection-picker-create-name"
                value={createName}
                onChange={(event) => {
                  setCreateName(event.target.value);
                  setCreateValidationError(null);
                  setCreateServerError(null);
                }}
                disabled={pending || Boolean(createdCollection)}
                placeholder="새 Collection 이름"
                className="w-full px-3 py-2.5 border border-border rounded-xl text-sm bg-background focus:outline-none focus:ring-2 focus:ring-primary/25 disabled:opacity-50"
                aria-invalid={
                  createValidationError || createServerError ? true : undefined
                }
              />
              {(createValidationError || createServerError) && (
                <p className="text-xs text-red-600 mt-1.5" role="alert">
                  {createValidationError ?? createServerError}
                </p>
              )}
              {createdCollection && isImmediate && (
                <p className="text-xs text-muted-foreground mt-1.5">
                  Collection은 생성되었습니다. 항목 추가를 다시 시도하세요.
                </p>
              )}
            </div>
            {actionError && (
              <p className="text-xs text-red-600 text-center" role="alert">
                {actionError}
              </p>
            )}
            <div className="flex gap-3">
              <button
                type="button"
                disabled={pending}
                onClick={() => {
                  setView("picker");
                  setCreateValidationError(null);
                  setCreateServerError(null);
                }}
                className="flex-1 border border-border text-foreground py-2.5 rounded-xl font-medium hover:bg-muted transition-colors text-sm disabled:opacity-50"
              >
                목록으로
              </button>
              <button
                type="submit"
                disabled={pending}
                className="flex-1 bg-primary hover:bg-blue-700 text-white py-2.5 rounded-xl font-medium transition-colors text-sm disabled:opacity-50"
              >
                {pending
                  ? (createdCollection
                    ? (isImmediate ? "추가 중..." : "선택 중...")
                    : "생성 중...")
                  : (createdCollection
                    ? (isImmediate ? "다시 추가" : "선택")
                    : (isImmediate ? "생성 후 추가" : "생성 후 선택"))}
              </button>
            </div>
          </form>
        )}
      </div>
    </div>
  );
}
