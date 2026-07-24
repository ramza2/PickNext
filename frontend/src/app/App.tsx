import { useState, useMemo, useCallback, useEffect, useRef } from "react";
import type { FormEvent, ReactNode } from "react";
import {
  Search, Shuffle, Plus, Star, AlignJustify,
  Grid, X, RefreshCw, Edit2, MoreVertical, ChevronLeft, ChevronRight,
  CheckCircle, Layers, Trash2, Check,
  ChevronsLeft, ChevronsRight, Palette,
} from "lucide-react";
import type { Page } from "./pageTypes";
import AppLayout from "./layout/AppLayout";
import PwaUpdatePrompt from "./components/PwaUpdatePrompt";
import { useHomeReadData } from "./hooks/useHomeReadData";
import {
  useItemsReadData,
  type ItemsPageStateSnapshot,
  type ItemsQuerySnapshot,
  type ItemsViewMode,
} from "./hooks/useItemsReadData";
import {
  useCollectionsReadData,
  type CollectionsQuerySnapshot,
} from "./hooks/useCollectionsReadData";
import { useCollectionDetail } from "./hooks/useCollectionDetail";
import { useCollectionItemsReadData } from "./hooks/useCollectionItemsReadData";
import { useItemDetail } from "./hooks/useItemDetail";
import {
  mapApiCategoryToHomeCategory,
  mapApiItemToHomeRecentItem,
} from "./mappers/home";
import {
  displayItemRating,
  mapApiItemToItemsListViewModel,
} from "./mappers/items";
import {
  mapApiCollectionToDetail,
  mapApiCollectionToListItem,
  type CollectionListItemViewModel,
} from "./mappers/collections";
import {
  displayDetailRating,
  mapApiItemDetailToViewModel,
} from "./mappers/itemDetail";
import { formatDate } from "../utils/date";
import { deleteCollection, deleteItem, getCollection, createCollection, updateCollection, createItem, updateItem, getItem, getCategories, getAllCollectionsForSelect } from "../api/catalog";
import {
  collectionCreateFailureToast,
  collectionPatchNotFoundToast,
  collectionUpdateFailureToast,
  collectionWriteConflictInline,
  collectionWriteValidationInline,
  isCollectionWriteNetworkOrServerError,
  normalizeCollectionNameInput,
  validateCollectionName,
} from "../api/collectionWriteMessages";
import {
  ITEM_CATEGORY_EMPTY_LIST_ERROR,
  ITEM_COLLECTION_NOT_FOUND_TOAST,
  ITEM_NOT_FOUND_TOAST,
  ITEM_PATCH_CONFLICT_ERROR,
  ITEM_RELATED_CHANGED_ERROR,
  ITEM_RELATED_NOT_FOUND_ERROR,
  ITEM_STATUS_CHECK_FAILED_TOAST,
  ITEM_WRITE_VALIDATION_ERROR,
  RATING_OPTIONS,
  buildItemCreatePayload,
  buildItemUpdatePayload,
  itemCreateFailureToast,
  itemFormValuesFromDetail,
  itemStatusConflictToast,
  itemStatusSuccessToast,
  itemStatusUpdateFailureToast,
  itemStatusValidationToast,
  itemUnlinkChangedToast,
  itemUnlinkFailureToast,
  itemUnlinkSuccessToast,
  itemUnlinkValidationToast,
  itemUpdateFailureToast,
  isItemWriteNetworkOrServerError,
  normalizeNullableText,
  collectItemFormFieldErrors,
  hasItemFormFieldErrors,
  buildCollectionUnlinkConfirmBody,
  type ItemFormFieldErrors,
  type ItemFormValues,
} from "../api/itemWriteMessages";
import { ApiError } from "../api/client";
import {
  collectionDeleteErrorMessage,
  itemDeleteErrorMessage,
} from "../api/deleteMessages";
import type { ApiCategory, ApiCollection, ApiItemDetail, ApiItemStatus } from "../types/api";
import { getCategoryPresentation } from "./presentation/categoryPresentation";
import {
  SearchPage,
  type SearchPageSnapshot,
} from "./search/SearchPage";
import { unmarkDeletedItemInSearchSnapshot } from "./search/registration";

// ─── Helpers ──────────────────────────────────────────────────────────────────

type ItemDetailOrigin = "items" | "home" | "collections" | "search";

const HIDDEN_PAGES = new Set<Page>(["recommend", "history", "history-detail", "data"]);

// ─── Shared Atoms ─────────────────────────────────────────────────────────────

function StarRating({ rating, sm }: { rating?: number; sm?: boolean }) {
  if (rating === undefined || rating === null || rating <= 0) {
    return <span className="text-xs text-muted-foreground">평가 없음</span>;
  }
  return (
    <span className="inline-flex items-center gap-0.5">
      {[1,2,3,4,5].map(i => {
        const filled = rating >= i;
        const half = !filled && rating >= i - 0.5;
        return (
          <Star
            key={i}
            size={sm?10:12}
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

function StarPicker({ value, onChange }: { value?: number; onChange: (v?: number) => void }) {
  return (
    <div className="flex items-center gap-1">
      {[1,2,3,4,5].map(i => (
        <button key={i} type="button" onClick={() => onChange(value === i ? undefined : i)}
          className="p-0.5 hover:scale-110 transition-transform">
          <Star size={24} className={i<=(value||0)?"fill-amber-400 text-amber-400":"text-gray-300"}/>
        </button>
      ))}
      <span className="text-sm text-muted-foreground ml-1">{value ? `${value}점` : "평가 없음"}</span>
    </div>
  );
}

function StatusBadge({ status, sm }: { status: ApiItemStatus; sm?: boolean }) {
  return (
    <span className={`inline-flex items-center rounded font-medium ${sm?"text-[10px] px-1.5 py-px":"text-xs px-2 py-0.5"} ${status==="PLANNED"?"bg-blue-100 text-blue-700":"bg-emerald-100 text-emerald-700"}`}>
      {status==="PLANNED"?"예정":"완료"}
    </span>
  );
}

function ProgressBar({ value, className="" }: { value: number; className?: string }) {
  return (
    <div className={`h-1.5 bg-gray-200 rounded-full overflow-hidden ${className}`}>
      <div className="h-full bg-blue-500 rounded-full transition-all" style={{ width:`${Math.min(100,Math.max(0,value))}%` }}/>
    </div>
  );
}

function Toast({ msg }: { msg: string }) {
  return (
    <div className="fixed bottom-24 sm:bottom-6 left-1/2 -translate-x-1/2 bg-zinc-900 text-white px-4 py-2.5 rounded-xl text-sm shadow-xl z-[70] flex items-center gap-2 whitespace-nowrap">
      <CheckCircle size={14} className="text-emerald-400 flex-shrink-0"/>{msg}
    </div>
  );
}

function ConfirmModal({ title, body, danger, confirmLabel, pending, pendingLabel, onConfirm, onClose, children }: {
  title: string; body: string; danger?: boolean; confirmLabel: string; pending?: boolean;
  pendingLabel?: string;
  onConfirm: () => void; onClose: () => void; children?: ReactNode;
}) {
  return (
    <div className="fixed inset-0 bg-black/50 z-50 flex items-center justify-center p-4 pb-20 sm:pb-4" role="dialog" aria-modal="true" aria-labelledby="confirm-modal-title">
      <div className="bg-card rounded-2xl w-full max-w-sm p-6 shadow-2xl max-h-[min(85vh,calc(100dvh-6rem))] overflow-y-auto">
        <h3 id="confirm-modal-title" className="text-base font-bold text-foreground mb-2 break-words">{title}</h3>
        <p className="text-sm text-muted-foreground mb-4 whitespace-pre-line break-words">{body}</p>
        {children}
        <div className="flex gap-3 mt-4">
          <button onClick={onClose} disabled={pending}
            className="flex-1 border border-border text-foreground py-2.5 rounded-xl font-medium hover:bg-muted transition-colors text-sm disabled:opacity-50 disabled:cursor-not-allowed">취소</button>
          <button onClick={onConfirm} disabled={pending}
            className={`flex-1 py-2.5 rounded-xl font-medium transition-colors text-sm disabled:opacity-50 disabled:cursor-not-allowed ${danger?"bg-red-500 hover:bg-red-600 text-white":"bg-primary hover:bg-blue-700 text-white"}`}>
            {pending ? (pendingLabel ?? "삭제 중...") : confirmLabel}
          </button>
        </div>
      </div>
    </div>
  );
}

function CollectionFormModal({
  open,
  mode,
  name,
  pending,
  validationError,
  serverError,
  submitDisabled,
  onNameChange,
  onSubmit,
  onClose,
}: {
  open: boolean;
  mode: "create" | "edit";
  name: string;
  pending: boolean;
  validationError: string | null;
  serverError: string | null;
  submitDisabled?: boolean;
  onNameChange: (value: string) => void;
  onSubmit: () => void;
  onClose: () => void;
}) {
  const inputRef = useRef<HTMLInputElement>(null);
  const titleId = "collection-form-modal-title";
  const errorId = "collection-form-modal-error";
  const isCreate = mode === "create";
  const normalizedLength = normalizeCollectionNameInput(name).length;
  const inlineError = validationError ?? serverError;

  useEffect(() => {
    if (open) {
      const timer = window.setTimeout(() => inputRef.current?.focus(), 0);
      return () => window.clearTimeout(timer);
    }
    return undefined;
  }, [open, mode]);

  useEffect(() => {
    if (!open || pending) return undefined;
    const onKeyDown = (event: KeyboardEvent) => {
      if (event.key === "Escape") onClose();
    };
    window.addEventListener("keydown", onKeyDown);
    return () => window.removeEventListener("keydown", onKeyDown);
  }, [open, pending, onClose]);

  if (!open) return null;

  const handleOverlayClick = () => {
    if (!pending) onClose();
  };

  const handleSubmit = (event: FormEvent) => {
    event.preventDefault();
    if (pending || submitDisabled) return;
    onSubmit();
  };

  return (
    <div
      className="fixed inset-0 bg-black/50 z-50 flex items-center justify-center p-4 pb-20 sm:pb-4"
      role="dialog"
      aria-modal="true"
      aria-labelledby={titleId}
      onClick={handleOverlayClick}
    >
      <form
        className="bg-card rounded-2xl w-full max-w-sm p-6 shadow-2xl max-h-[min(85vh,calc(100dvh-6rem))] overflow-y-auto"
        onClick={(event) => event.stopPropagation()}
        onSubmit={handleSubmit}
      >
        <h3 id={titleId} className="text-base font-bold text-foreground mb-4 break-words">
          {isCreate ? "새 컬렉션" : "컬렉션 이름 수정"}
        </h3>
        <div>
          <label htmlFor="collection-form-name" className="block text-sm font-medium text-foreground mb-1.5">
            컬렉션 이름
          </label>
          <input
            ref={inputRef}
            id="collection-form-name"
            value={name}
            onChange={(event) => onNameChange(event.target.value)}
            placeholder="컬렉션 이름을 입력하세요"
            disabled={pending}
            aria-invalid={inlineError ? true : undefined}
            aria-describedby={inlineError ? errorId : undefined}
            className="w-full px-3 py-2.5 border border-border rounded-xl text-sm bg-background focus:outline-none focus:ring-2 focus:ring-primary/25 disabled:opacity-50"
          />
          <div className="flex items-start justify-between gap-2 mt-1.5 min-h-[1.25rem]">
            {inlineError ? (
              <p id={errorId} className="text-xs text-red-600 break-words">{inlineError}</p>
            ) : (
              <span className="text-xs text-transparent select-none" aria-hidden="true">.</span>
            )}
            <span className="text-xs text-muted-foreground flex-shrink-0">{normalizedLength}/200</span>
          </div>
        </div>
        <div className="flex gap-3 mt-4">
          <button
            type="button"
            onClick={onClose}
            disabled={pending}
            className="flex-1 border border-border text-foreground py-2.5 rounded-xl font-medium hover:bg-muted transition-colors text-sm disabled:opacity-50 disabled:cursor-not-allowed"
          >
            취소
          </button>
          <button
            type="submit"
            disabled={pending || submitDisabled}
            className="flex-1 bg-primary hover:bg-blue-700 text-white py-2.5 rounded-xl font-medium transition-colors text-sm disabled:opacity-50 disabled:cursor-not-allowed"
          >
            {pending ? (isCreate ? "생성 중..." : "저장 중...") : isCreate ? "생성" : "저장"}
          </button>
        </div>
      </form>
    </div>
  );
}

// ─── Item Form Modal ──────────────────────────────────────────────────────────

type ItemFormSession =
  | {
      mode: "create";
      origin: ItemDetailOrigin;
      initialCategoryId?: string | null;
      initialCollectionId?: string | null;
      lockedCollection?: { id: string; name: string };
      collectionItemsPage?: number;
    }
  | {
      mode: "edit";
      item: ApiItemDetail;
      origin: ItemDetailOrigin;
      collectionId?: string;
      collectionItemsPage?: number;
    };

function emptyItemFormValues(
  overrides?: Partial<ItemFormValues>,
): ItemFormValues {
  return {
    title: "",
    categoryId: "",
    collectionId: null,
    status: "PLANNED",
    rating: 0,
    progressNote: "",
    memo: "",
    ...overrides,
  };
}

function ItemFormModal({
  session,
  busy,
  onBusyChange,
  onClose,
  onCreated,
  onUpdated,
  onItemMissing,
  onLockedCollectionMissing,
  showToast,
}: {
  session: ItemFormSession;
  busy: boolean;
  onBusyChange: (value: boolean) => void;
  onClose: () => void;
  onCreated: (item: ApiItemDetail, session: Extract<ItemFormSession, { mode: "create" }>) => void | Promise<void>;
  onUpdated: (item: ApiItemDetail, session: Extract<ItemFormSession, { mode: "edit" }>) => void | Promise<void>;
  onItemMissing: (session: Extract<ItemFormSession, { mode: "edit" }>) => void | Promise<void>;
  onLockedCollectionMissing: () => void | Promise<void>;
  showToast: (m: string) => void;
}) {
  const isEdit = session.mode === "edit";
  const lockedCollection =
    session.mode === "create" ? session.lockedCollection : undefined;

  const [values, setValues] = useState<ItemFormValues>(() => {
    if (session.mode === "edit") return itemFormValuesFromDetail(session.item);
    return emptyItemFormValues({
      categoryId: session.initialCategoryId ?? "",
      collectionId:
        session.lockedCollection?.id
        ?? session.initialCollectionId
        ?? null,
    });
  });
  const [categories, setCategories] = useState<ApiCategory[]>([]);
  const [collections, setCollections] = useState<ApiCollection[]>([]);
  const [optionsLoading, setOptionsLoading] = useState(true);
  const [optionsError, setOptionsError] = useState<string | null>(null);
  const [fieldErrors, setFieldErrors] = useState<ItemFormFieldErrors>({});
  const [serverError, setServerError] = useState<string | null>(null);
  const [pending, setPending] = useState(false);
  const titleRef = useRef<HTMLInputElement>(null);
  const categorySectionRef = useRef<HTMLDivElement>(null);
  const progressRef = useRef<HTMLInputElement>(null);
  const formErrorRef = useRef<HTMLParagraphElement>(null);
  const titleId = "item-form-modal-title";
  const titleErrorId = "item-form-title-error";
  const categoryErrorId = "item-form-category-error";
  const progressErrorId = "item-form-progress-error";
  const formErrorId = "item-form-modal-error";
  const formBusy = pending || busy;

  const progressLength = normalizeNullableText(values.progressNote)?.length ?? 0;
  const formLevelError = fieldErrors.form ?? serverError;

  const editHasChanges = useMemo(() => {
    if (session.mode !== "edit") return true;
    return Object.keys(buildItemUpdatePayload(values, session.item)).length > 0;
  }, [session, values]);

  const reloadOptions = useCallback(async () => {
    setOptionsLoading(true);
    setOptionsError(null);
    try {
      const [categoriesResponse, collectionRows] = await Promise.all([
        getCategories(),
        getAllCollectionsForSelect(),
      ]);
      let nextCollections = collectionRows;
      if (
        session.mode === "edit"
        && session.item.collection
        && !collectionRows.some((row) => row.id === session.item.collection?.id)
      ) {
        nextCollections = [
          {
            id: session.item.collection.id,
            name: session.item.collection.name,
            item_count: 0,
            planned_count: 0,
            completed_count: 0,
            categories: [],
            created_at: session.item.created_at,
            updated_at: session.item.updated_at,
          },
          ...collectionRows,
        ];
      }
      setCategories(categoriesResponse.categories);
      setCollections(nextCollections);
      return {
        categories: categoriesResponse.categories,
        collections: nextCollections,
      };
    } catch {
      setOptionsError("카테고리 또는 컬렉션 목록을 불러오지 못했습니다.");
      return null;
    } finally {
      setOptionsLoading(false);
    }
  }, [session]);

  useEffect(() => {
    void reloadOptions();
  }, [reloadOptions]);

  useEffect(() => {
    const timer = window.setTimeout(() => titleRef.current?.focus(), 0);
    return () => window.clearTimeout(timer);
  }, []);

  useEffect(() => {
    if (formBusy) return undefined;
    const onKeyDown = (event: KeyboardEvent) => {
      if (event.key === "Escape") onClose();
    };
    window.addEventListener("keydown", onKeyDown);
    return () => window.removeEventListener("keydown", onKeyDown);
  }, [formBusy, onClose]);

  const updateField = <K extends keyof ItemFormValues>(
    key: K,
    value: ItemFormValues[K],
  ) => {
    setValues((prev) => ({ ...prev, [key]: value }));
    setFieldErrors((prev) => {
      const next = { ...prev };
      if (key === "title") delete next.title;
      if (key === "categoryId") delete next.categoryId;
      if (key === "progressNote") delete next.progressNote;
      return next;
    });
    if (serverError) setServerError(null);
  };

  const focusFirstFieldError = (errors: ItemFormFieldErrors) => {
    window.requestAnimationFrame(() => {
      if (errors.title) {
        titleRef.current?.scrollIntoView({ behavior: "smooth", block: "center" });
        titleRef.current?.focus();
        return;
      }
      if (errors.categoryId) {
        categorySectionRef.current?.scrollIntoView({
          behavior: "smooth",
          block: "center",
        });
        const focusable = categorySectionRef.current?.querySelector<HTMLButtonElement>(
          "button:not([disabled])",
        );
        focusable?.focus();
        return;
      }
      if (errors.progressNote) {
        progressRef.current?.scrollIntoView({ behavior: "smooth", block: "center" });
        progressRef.current?.focus();
        return;
      }
      if (errors.form) {
        formErrorRef.current?.scrollIntoView({ behavior: "smooth", block: "center" });
      }
    });
  };

  const handleSubmit = async (event: FormEvent) => {
    event.preventDefault();
    if (formBusy) return;

    const categoriesEmpty = !optionsLoading && categories.length === 0;
    const nextFieldErrors = collectItemFormFieldErrors(values, {
      categoriesEmpty,
    });
    if (hasItemFormFieldErrors(nextFieldErrors)) {
      setFieldErrors(nextFieldErrors);
      setServerError(null);
      focusFirstFieldError(nextFieldErrors);
      return;
    }

    if (isEdit && session.mode === "edit") {
      const payload = buildItemUpdatePayload(values, session.item);
      if (Object.keys(payload).length === 0) {
        onClose();
        return;
      }
      setPending(true);
      onBusyChange(true);
      setFieldErrors({});
      setServerError(null);
      try {
        const updated = await updateItem(session.item.id, payload);
        await onUpdated(updated, session);
      } catch (err) {
        if (err instanceof ApiError && err.status === 404) {
          try {
            await getItem(session.item.id);
            setServerError(ITEM_RELATED_NOT_FOUND_ERROR);
            const loaded = await reloadOptions();
            if (loaded) {
              if (
                values.categoryId
                && !loaded.categories.some((row) => row.id === values.categoryId)
              ) {
                updateField("categoryId", "");
              }
              if (
                values.collectionId
                && !loaded.collections.some((row) => row.id === values.collectionId)
              ) {
                updateField("collectionId", null);
              }
            }
          } catch (confirmErr) {
            if (confirmErr instanceof ApiError && confirmErr.status === 404) {
              await onItemMissing(session);
            } else {
              showToast(ITEM_STATUS_CHECK_FAILED_TOAST);
            }
          }
        } else if (err instanceof ApiError && err.status === 409) {
          setServerError(ITEM_PATCH_CONFLICT_ERROR);
          await reloadOptions();
          try {
            const fresh = await getItem(session.item.id);
            setValues(itemFormValuesFromDetail(fresh));
          } catch {
            /* keep current form values */
          }
        } else if (err instanceof ApiError && err.status === 422) {
          setServerError(ITEM_WRITE_VALIDATION_ERROR);
        } else if (isItemWriteNetworkOrServerError(err)) {
          showToast(itemUpdateFailureToast());
        } else {
          showToast(itemUpdateFailureToast());
        }
      } finally {
        setPending(false);
        onBusyChange(false);
      }
      return;
    }

    if (session.mode !== "create") return;
    const payload = buildItemCreatePayload(values);
    setPending(true);
    onBusyChange(true);
    setFieldErrors({});
    setServerError(null);
    try {
      const created = await createItem(payload);
      await onCreated(created, session);
    } catch (err) {
      if (err instanceof ApiError && err.status === 404) {
        if (lockedCollection) {
          try {
            await getCollection(lockedCollection.id);
            setServerError(ITEM_RELATED_NOT_FOUND_ERROR);
            await reloadOptions();
          } catch (colErr) {
            if (colErr instanceof ApiError && colErr.status === 404) {
              await onLockedCollectionMissing();
            } else {
              setServerError(ITEM_RELATED_NOT_FOUND_ERROR);
            }
          }
        } else {
          setServerError(ITEM_RELATED_NOT_FOUND_ERROR);
          const loaded = await reloadOptions();
          if (
            loaded
            && values.categoryId
            && !loaded.categories.some((row) => row.id === values.categoryId)
          ) {
            updateField("categoryId", "");
          }
          if (
            loaded
            && values.collectionId
            && !loaded.collections.some((row) => row.id === values.collectionId)
          ) {
            updateField("collectionId", null);
          }
        }
      } else if (err instanceof ApiError && err.status === 409) {
        setServerError(ITEM_RELATED_CHANGED_ERROR);
        await reloadOptions();
      } else if (err instanceof ApiError && err.status === 422) {
        setServerError(ITEM_WRITE_VALIDATION_ERROR);
      } else if (isItemWriteNetworkOrServerError(err)) {
        showToast(itemCreateFailureToast());
      } else {
        showToast(itemCreateFailureToast());
      }
    } finally {
      setPending(false);
      onBusyChange(false);
    }
  };

  const handleOverlayClick = () => {
    if (!formBusy) onClose();
  };

  const collectionOptions = collections;
  const submitDisabled =
    formBusy
    || optionsLoading
    || (isEdit && !editHasChanges)
    || (!optionsLoading && categories.length === 0);

  return (
    <div
      className="fixed inset-0 bg-black/50 z-50 flex items-stretch sm:items-center justify-center"
      role="dialog"
      aria-modal="true"
      aria-labelledby={titleId}
      onClick={handleOverlayClick}
    >
      <form
        className="bg-card w-full sm:max-w-lg sm:rounded-2xl flex flex-col max-h-screen sm:max-h-[90vh] shadow-2xl"
        onClick={(event) => event.stopPropagation()}
        onSubmit={(event) => void handleSubmit(event)}
      >
        <div className="flex items-center justify-between px-5 py-4 border-b border-border flex-shrink-0">
          <h2 id={titleId} className="font-bold text-foreground">
            {isEdit ? "항목 수정" : "새 항목"}
          </h2>
          <button
            type="button"
            onClick={onClose}
            disabled={formBusy}
            className="p-1.5 text-muted-foreground hover:text-foreground hover:bg-muted rounded-lg transition-colors disabled:opacity-50"
          >
            <X size={18}/>
          </button>
        </div>

        <div className="flex-1 overflow-y-auto p-5 space-y-4">
          {optionsError && (
            <div className="rounded-xl border border-amber-200 bg-amber-50 px-3 py-2 text-xs text-amber-800">
              {optionsError}{" "}
              <button
                type="button"
                className="underline font-medium"
                onClick={() => void reloadOptions()}
                disabled={formBusy}
              >
                다시 시도
              </button>
            </div>
          )}

          {!optionsLoading && categories.length === 0 && (
            <div className="rounded-xl border border-border bg-muted/40 px-3 py-2 text-xs text-muted-foreground">
              {ITEM_CATEGORY_EMPTY_LIST_ERROR}
            </div>
          )}

          <div>
            <label htmlFor="item-form-title" className="block text-sm font-medium text-foreground mb-1.5">
              제목 <span className="text-red-500">*</span>
            </label>
            <input
              ref={titleRef}
              id="item-form-title"
              value={values.title}
              onChange={(event) => updateField("title", event.target.value)}
              placeholder="제목을 입력하세요"
              disabled={formBusy}
              aria-invalid={fieldErrors.title ? true : undefined}
              aria-describedby={fieldErrors.title ? titleErrorId : undefined}
              className="w-full px-3 py-2.5 border border-border rounded-xl text-sm bg-background focus:outline-none focus:ring-2 focus:ring-primary/25 disabled:opacity-50"
            />
            {fieldErrors.title && (
              <p id={titleErrorId} role="alert" className="text-xs text-red-600 break-words mt-1.5">
                {fieldErrors.title}
              </p>
            )}
          </div>

          <div ref={categorySectionRef}>
            <span className="block text-sm font-medium text-foreground mb-1.5" id="item-form-category-label">
              Category <span className="text-red-500">*</span>
            </span>
            {optionsLoading ? (
              <p className="text-xs text-muted-foreground">카테고리 불러오는 중…</p>
            ) : (
              <div
                className="grid grid-cols-2 gap-1.5"
                role="group"
                aria-labelledby="item-form-category-label"
                aria-invalid={fieldErrors.categoryId ? true : undefined}
                aria-describedby={fieldErrors.categoryId ? categoryErrorId : undefined}
              >
                {categories.map((cat) => {
                  const presentation = getCategoryPresentation(cat.name);
                  const Icon = presentation.icon;
                  const selected = values.categoryId === cat.id;
                  return (
                    <button
                      key={cat.id}
                      type="button"
                      disabled={formBusy}
                      onClick={() => updateField("categoryId", cat.id)}
                      className={`flex items-center gap-1.5 p-2 rounded-lg border text-xs font-medium transition-colors disabled:opacity-50 ${
                        selected
                          ? "border-primary bg-blue-50 text-blue-700"
                          : "border-border hover:border-primary/30 text-foreground"
                      }`}
                    >
                      <Icon size={14} style={{ color: presentation.color }}/>
                      <span className="truncate">{cat.name}</span>
                    </button>
                  );
                })}
              </div>
            )}
            {fieldErrors.categoryId && (
              <p id={categoryErrorId} role="alert" className="text-xs text-red-600 break-words mt-1.5">
                {fieldErrors.categoryId}
              </p>
            )}
          </div>

          <div>
            <span className="block text-sm font-medium text-foreground mb-1.5">상태</span>
            <div className="flex bg-muted rounded-xl p-0.5">
              {(["PLANNED", "COMPLETED"] as ApiItemStatus[]).map((status) => (
                <button
                  key={status}
                  type="button"
                  disabled={formBusy}
                  onClick={() => updateField("status", status)}
                  className={`flex-1 py-2 rounded-lg text-sm font-medium transition-colors disabled:opacity-50 ${
                    values.status === status
                      ? "bg-card shadow text-foreground"
                      : "text-muted-foreground hover:text-foreground"
                  }`}
                >
                  {status === "PLANNED" ? "볼 예정" : "완료"}
                </button>
              ))}
            </div>
          </div>

          <div>
            <label htmlFor="item-form-rating" className="block text-sm font-medium text-foreground mb-1.5">
              평점
            </label>
            <select
              id="item-form-rating"
              value={String(values.rating)}
              disabled={formBusy}
              onChange={(event) => updateField("rating", Number(event.target.value))}
              className="w-full px-3 py-2.5 border border-border rounded-xl text-sm bg-background focus:outline-none focus:ring-2 focus:ring-primary/25 disabled:opacity-50"
            >
              {RATING_OPTIONS.map((rating) => (
                <option key={rating} value={rating}>
                  {rating === 0 ? "미평가 (0)" : rating.toFixed(1)}
                </option>
              ))}
            </select>
          </div>

          <div>
            <label htmlFor="item-form-collection" className="block text-sm font-medium text-foreground mb-1.5">
              Collection <span className="text-muted-foreground font-normal text-xs">(선택)</span>
            </label>
            {lockedCollection ? (
              <input
                id="item-form-collection"
                value={lockedCollection.name}
                readOnly
                disabled
                className="w-full px-3 py-2.5 border border-border rounded-xl text-sm bg-muted text-foreground disabled:opacity-80"
              />
            ) : (
              <select
                id="item-form-collection"
                value={values.collectionId ?? ""}
                disabled={formBusy || optionsLoading}
                onChange={(event) =>
                  updateField("collectionId", event.target.value || null)
                }
                className="w-full px-3 py-2.5 border border-border rounded-xl text-sm bg-background focus:outline-none focus:ring-2 focus:ring-primary/25 disabled:opacity-50"
              >
                <option value="">컬렉션 없음</option>
                {collectionOptions.map((collection) => (
                  <option key={collection.id} value={collection.id}>
                    {collection.name}
                  </option>
                ))}
              </select>
            )}
          </div>

          <div>
            <label htmlFor="item-form-progress" className="block text-sm font-medium text-foreground mb-1.5">
              진행 상황 <span className="text-muted-foreground font-normal text-xs">(선택)</span>
            </label>
            <input
              ref={progressRef}
              id="item-form-progress"
              value={values.progressNote}
              disabled={formBusy}
              onChange={(event) => updateField("progressNote", event.target.value)}
              placeholder="예: 시즌 2 / 15권까지 읽음"
              aria-invalid={fieldErrors.progressNote ? true : undefined}
              aria-describedby={fieldErrors.progressNote ? progressErrorId : undefined}
              className="w-full px-3 py-2.5 border border-border rounded-xl text-sm bg-background focus:outline-none focus:ring-2 focus:ring-primary/25 disabled:opacity-50"
            />
            <div className="flex flex-col sm:flex-row sm:items-start sm:justify-between gap-1 mt-1.5">
              {fieldErrors.progressNote ? (
                <p id={progressErrorId} role="alert" className="text-xs text-red-600 break-words">
                  {fieldErrors.progressNote}
                </p>
              ) : (
                <span className="hidden sm:block"/>
              )}
              <span
                className={`text-xs flex-shrink-0 sm:ml-auto ${
                  progressLength > 200 ? "text-red-600" : "text-muted-foreground"
                }`}
              >
                {progressLength}/200
              </span>
            </div>
          </div>

          <div>
            <label htmlFor="item-form-memo" className="block text-sm font-medium text-foreground mb-1.5">
              메모 <span className="text-muted-foreground font-normal text-xs">(선택)</span>
            </label>
            <textarea
              id="item-form-memo"
              value={values.memo}
              disabled={formBusy}
              onChange={(event) => updateField("memo", event.target.value)}
              rows={3}
              placeholder="개인 메모"
              className="w-full px-3 py-2.5 border border-border rounded-xl text-sm bg-background focus:outline-none focus:ring-2 focus:ring-primary/25 resize-y min-h-[5rem] disabled:opacity-50"
            />
          </div>
        </div>

        {formLevelError && (
          <p
            ref={formErrorRef}
            id={formErrorId}
            role="alert"
            className="px-5 pt-2 text-xs text-red-600 break-words flex-shrink-0"
          >
            {formLevelError}
          </p>
        )}

        <div className="px-5 py-4 border-t border-border flex gap-3 flex-shrink-0">
          <button
            type="button"
            onClick={onClose}
            disabled={formBusy}
            className="flex-1 border border-border text-foreground py-2.5 rounded-xl font-medium hover:bg-muted transition-colors text-sm disabled:opacity-50 disabled:cursor-not-allowed"
          >
            취소
          </button>
          <button
            type="submit"
            disabled={submitDisabled}
            className="flex-1 bg-primary text-white py-2.5 rounded-xl font-semibold hover:bg-blue-700 transition-colors text-sm disabled:opacity-40 disabled:cursor-not-allowed"
          >
            {formBusy
              ? (isEdit ? "저장 중..." : "추가 중...")
              : (isEdit ? "저장" : "추가")}
          </button>
        </div>
      </form>
    </div>
  );
}

// ─── Item Detail Page ─────────────────────────────────────────────────────────

function ItemDetailPage({
  itemId,
  onBack,
  showToast,
  backLabel = "목록으로",
  origin = "items",
  collectionId,
  collectionItemsPage,
  onDeleteSuccess,
  onEdit,
  writeBusy,
}: {
  itemId: string | null;
  onBack: () => void;
  showToast: (m: string) => void;
  backLabel?: string;
  origin?: ItemDetailOrigin;
  collectionId?: string;
  collectionItemsPage?: number;
  onDeleteSuccess?: (context: {
    origin: ItemDetailOrigin;
    collectionId?: string;
    collectionItemsPage?: number;
    deletedItem: ApiItemDetail;
  }) => void | Promise<void>;
  onEdit?: (item: ApiItemDetail) => void;
  writeBusy?: boolean;
}) {
  const { item, isLoading, error, reload } = useItemDetail(itemId);
  const [showDeleteConfirm, setShowDeleteConfirm] = useState(false);
  const [deletePending, setDeletePending] = useState(false);
  const [statusPending, setStatusPending] = useState(false);
  const actionBusy = Boolean(writeBusy) || deletePending || statusPending;

  if (!itemId) {
    return (
      <div className="max-w-2xl mx-auto px-4 sm:px-6 py-6">
        <button onClick={onBack} className="flex items-center gap-1 text-sm text-muted-foreground hover:text-foreground mb-5">
          <ChevronLeft size={16}/> {backLabel}
        </button>
        <div className="bg-card border border-border rounded-2xl p-8 text-center">
          <p className="font-medium text-foreground mb-4">선택된 항목이 없습니다.</p>
          <button onClick={onBack}
            className="inline-flex items-center gap-1.5 text-sm bg-primary text-white px-4 py-2 rounded-xl hover:bg-blue-700 transition-colors font-medium">
            {backLabel} 돌아가기
          </button>
        </div>
      </div>
    );
  }

  if (isLoading) {
    return (
      <div className="max-w-2xl mx-auto px-4 sm:px-6 py-6">
        <button onClick={onBack} className="flex items-center gap-1 text-sm text-muted-foreground hover:text-foreground mb-5">
          <ChevronLeft size={16}/> {backLabel}
        </button>
        <div className="bg-card border border-border rounded-2xl p-6 mb-4">
          <div className="flex gap-5">
            <div className="w-32 h-48 rounded-2xl animate-pulse bg-muted flex-shrink-0"/>
            <div className="flex-1 min-w-0 space-y-3">
              <div className="h-4 w-24 animate-pulse rounded bg-muted"/>
              <div className="h-7 w-3/4 animate-pulse rounded bg-muted"/>
              <div className="h-4 w-32 animate-pulse rounded bg-muted"/>
              <div className="h-4 w-40 animate-pulse rounded bg-muted"/>
            </div>
          </div>
        </div>
        <div className="bg-card border border-border rounded-2xl p-5 mb-4 space-y-3">
          {[0,1,2,3].map(i => <div key={i} className="h-4 w-full animate-pulse rounded bg-muted"/>)}
        </div>
        <div className="space-y-2.5">
          {[0,1,2].map(i => <div key={i} className="h-12 w-full animate-pulse rounded-xl bg-muted"/>)}
        </div>
      </div>
    );
  }

  if (error) {
    const isNotFound = error.status === 404;
    return (
      <div className="max-w-2xl mx-auto px-4 sm:px-6 py-6">
        <button onClick={onBack} className="flex items-center gap-1 text-sm text-muted-foreground hover:text-foreground mb-5">
          <ChevronLeft size={16}/> {backLabel}
        </button>
        <div className="bg-card border border-border rounded-2xl p-8 text-center">
          <p className="font-medium text-foreground mb-2">
            {isNotFound ? "항목을 찾을 수 없습니다." : "항목 정보를 불러오지 못했습니다."}
          </p>
          {isNotFound && (
            <p className="text-sm text-muted-foreground mb-5">삭제되었거나 접근할 수 없는 항목입니다.</p>
          )}
          <div className="flex flex-wrap gap-2 justify-center">
            {!isNotFound && (
              <button onClick={reload}
                className="inline-flex items-center gap-1.5 text-sm bg-primary text-white px-4 py-2 rounded-xl hover:bg-blue-700 transition-colors font-medium">
                <RefreshCw size={14}/> 다시 시도
              </button>
            )}
            <button onClick={onBack}
              className="inline-flex items-center gap-1.5 text-sm border border-border text-foreground px-4 py-2 rounded-xl hover:bg-muted transition-colors font-medium">
              {backLabel} 돌아가기
            </button>
          </div>
        </div>
      </div>
    );
  }

  if (!item) {
    return (
      <div className="max-w-2xl mx-auto px-4 sm:px-6 py-6">
        <button onClick={onBack} className="flex items-center gap-1 text-sm text-muted-foreground hover:text-foreground mb-5">
          <ChevronLeft size={16}/> {backLabel}
        </button>
        <div className="bg-card border border-border rounded-2xl p-8 text-center">
          <p className="font-medium text-foreground mb-4">선택된 항목이 없습니다.</p>
          <button onClick={onBack}
            className="inline-flex items-center gap-1.5 text-sm bg-primary text-white px-4 py-2 rounded-xl hover:bg-blue-700 transition-colors font-medium">
            {backLabel} 돌아가기
          </button>
        </div>
      </div>
    );
  }

  const vm = mapApiItemDetailToViewModel(item);
  const Icon = vm.presentation.icon;
  const createdLabel = formatDate(vm.createdAt);
  const updatedLabel = formatDate(vm.updatedAt);

  const detailRows = [
    {
      label: "Progress Note",
      value: vm.progressNote ?? "등록된 진행 정보가 없습니다.",
      muted: !vm.progressNote,
    },
    {
      label: "메모",
      value: vm.memo ?? "등록된 메모가 없습니다.",
      muted: !vm.memo,
    },
    { label: "등록일", value: createdLabel || "—", muted: !createdLabel },
    { label: "수정일", value: updatedLabel || "—", muted: !updatedLabel },
  ];

  const deleteDialogBody = [
    `"${vm.title}" 항목을 삭제합니다.`,
    "삭제된 항목은 복구할 수 없습니다.",
    "이 항목이 포함된 추천 이력도 함께 삭제됩니다.",
    vm.collectionName
      ? "이 항목이 컬렉션의 마지막 항목이면 컬렉션도 함께 삭제됩니다."
      : null,
  ]
    .filter(Boolean)
    .join("\n");

  const handleDeleteConfirm = async () => {
    if (!item || deletePending || actionBusy) return;
    setDeletePending(true);
    try {
      await deleteItem(item.id);
      setShowDeleteConfirm(false);
      const ctx = {
        origin,
        collectionId: collectionId ?? item.collection?.id ?? undefined,
        collectionItemsPage,
        deletedItem: item,
      };
      if (onDeleteSuccess) {
        await onDeleteSuccess(ctx);
      } else {
        onBack();
        showToast("항목을 삭제했습니다.");
      }
    } catch (err) {
      const message = itemDeleteErrorMessage(err);
      showToast(message);
      if (err instanceof ApiError && err.status === 404) {
        setShowDeleteConfirm(false);
        if (onDeleteSuccess) {
          await onDeleteSuccess({
            origin,
            collectionId: collectionId ?? item.collection?.id ?? undefined,
            collectionItemsPage,
            deletedItem: item,
          });
        } else {
          onBack();
        }
      }
    } finally {
      setDeletePending(false);
    }
  };

  const handleStatusToggle = async () => {
    if (!item || actionBusy) return;
    const nextStatus: ApiItemStatus =
      item.status === "PLANNED" ? "COMPLETED" : "PLANNED";
    setStatusPending(true);
    try {
      await updateItem(item.id, { status: nextStatus });
      await reload();
      showToast(itemStatusSuccessToast(nextStatus));
    } catch (err) {
      if (err instanceof ApiError && err.status === 404) {
        try {
          await getItem(item.id);
          showToast(itemStatusConflictToast());
          await reload();
        } catch (confirmErr) {
          if (confirmErr instanceof ApiError && confirmErr.status === 404) {
            if (onDeleteSuccess) {
              await onDeleteSuccess({
                origin,
                collectionId: collectionId ?? item.collection?.id ?? undefined,
                collectionItemsPage,
                deletedItem: item,
              });
            } else {
              onBack();
            }
            showToast(ITEM_NOT_FOUND_TOAST);
          } else {
            showToast(ITEM_STATUS_CHECK_FAILED_TOAST);
          }
        }
      } else if (err instanceof ApiError && err.status === 409) {
        showToast(itemStatusConflictToast());
        await reload();
      } else if (err instanceof ApiError && err.status === 422) {
        showToast(itemStatusValidationToast());
      } else {
        showToast(itemStatusUpdateFailureToast());
      }
    } finally {
      setStatusPending(false);
    }
  };

  return (
    <div className="max-w-2xl mx-auto px-4 sm:px-6 py-6">
      <button onClick={onBack} className="flex items-center gap-1 text-sm text-muted-foreground hover:text-foreground mb-5">
        <ChevronLeft size={16}/> {backLabel}
      </button>

      {/* Header */}
      <div className="bg-card border border-border rounded-2xl p-6 mb-4">
        <div className="flex gap-5">
          <div className="w-32 h-48 text-4xl rounded-2xl flex items-center justify-center flex-shrink-0 text-white font-bold"
            style={{ backgroundColor: vm.presentation.color }}>
            {vm.title.charAt(0)}
          </div>
          <div className="flex-1 min-w-0">
            <div className="flex flex-wrap gap-1.5 mb-2">
              <span className="inline-flex items-center gap-1 rounded font-medium text-xs px-2 py-0.5"
                style={{ backgroundColor: vm.presentation.bgColor, color: vm.presentation.color }}>
                <Icon size={14}/>{vm.categoryName}
              </span>
              <StatusBadge status={vm.status}/>
            </div>
            <h1 className="text-xl font-bold text-foreground leading-tight mb-1 break-words">{vm.title}</h1>
            <div className="mb-2"><StarRating rating={displayDetailRating(vm.rating)}/></div>
            <div className="flex items-center gap-1.5 text-xs text-muted-foreground">
              <Layers size={12}/><span>Collection: </span>
              <span className="font-medium text-foreground">{vm.collectionName ?? "미지정"}</span>
            </div>
          </div>
        </div>
      </div>

      {/* Details */}
      <div className="bg-card border border-border rounded-2xl overflow-hidden mb-4">
        {detailRows.map((row, i, arr) => (
          <div key={row.label} className={`flex gap-4 px-5 py-3 text-sm ${i < arr.length-1?"border-b border-border":""}`}>
            <span className="text-muted-foreground w-28 flex-shrink-0">{row.label}</span>
            <span className={`min-w-0 break-words ${row.muted ? "text-muted-foreground" : "text-foreground"}`}>{row.value}</span>
          </div>
        ))}
      </div>

      <div className="bg-card border border-border rounded-2xl p-5 mb-4">
        <h3 className="text-sm font-semibold text-foreground mb-2">줄거리</h3>
        <p className="text-sm text-muted-foreground leading-relaxed">등록된 상세 설명이 없습니다.</p>
      </div>

      {/* Actions */}
      <div className="space-y-2.5">
        <button
          type="button"
          disabled={actionBusy || showDeleteConfirm}
          onClick={() => {
            if (item && onEdit) onEdit(item);
          }}
          className="w-full flex items-center gap-2 justify-center border border-border bg-card text-foreground py-3 rounded-xl font-medium hover:bg-muted transition-colors text-sm disabled:opacity-50 disabled:cursor-not-allowed"
        >
          <Edit2 size={15}/> 수정
        </button>

        {vm.status === "PLANNED" ? (
          <button
            type="button"
            disabled={actionBusy || showDeleteConfirm}
            onClick={() => void handleStatusToggle()}
            className="w-full flex items-center gap-2 justify-center bg-emerald-600 text-white py-3 rounded-xl font-medium hover:bg-emerald-700 transition-colors text-sm disabled:opacity-50 disabled:cursor-not-allowed"
          >
            <Check size={15}/> {statusPending ? "변경 중..." : "완료 처리"}
          </button>
        ) : (
          <button
            type="button"
            disabled={actionBusy || showDeleteConfirm}
            onClick={() => void handleStatusToggle()}
            className="w-full flex items-center gap-2 justify-center border border-border text-foreground py-3 rounded-xl font-medium hover:bg-muted transition-colors text-sm disabled:opacity-50 disabled:cursor-not-allowed"
          >
            <RefreshCw size={15}/> {statusPending ? "변경 중..." : "볼 예정으로 변경"}
          </button>
        )}

        <button
          type="button"
          disabled={actionBusy || showDeleteConfirm}
          onClick={() => {
            if (item && onEdit) onEdit(item);
          }}
          className="w-full flex items-center gap-2 justify-center border border-border text-foreground py-3 rounded-xl font-medium hover:bg-muted transition-colors text-sm disabled:opacity-50 disabled:cursor-not-allowed"
        >
          <Layers size={15}/> Collection 이동
        </button>

        <button
          type="button"
          disabled={actionBusy}
          onClick={() => setShowDeleteConfirm(true)}
          className="w-full flex items-center gap-2 justify-center border border-red-200 text-red-600 py-3 rounded-xl font-medium hover:bg-red-50 transition-colors text-sm disabled:opacity-50 disabled:cursor-not-allowed"
        >
          <Trash2 size={15}/> 삭제
        </button>
      </div>

      {showDeleteConfirm && (
        <ConfirmModal
          title="항목 삭제"
          body={deleteDialogBody}
          danger
          confirmLabel="삭제"
          pending={deletePending}
          onConfirm={() => void handleDeleteConfirm()}
          onClose={() => {
            if (!deletePending) setShowDeleteConfirm(false);
          }}
        />
      )}
    </div>
  );
}

// ─── Category Manage Page ─────────────────────────────────────────────────────

function CategoryManagePage({ onBack }: { onBack: () => void }) {
  const [categories, setCategories] = useState<ApiCategory[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  const loadCategories = useCallback(async () => {
    setLoading(true);
    setError(null);
    try {
      const response = await getCategories();
      setCategories(response.categories);
    } catch {
      setError("Category 목록을 불러오지 못했습니다.");
      setCategories([]);
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => {
    void loadCategories();
  }, [loadCategories]);

  return (
    <div className="max-w-2xl mx-auto px-4 sm:px-6 py-6">
      <button onClick={onBack} className="flex items-center gap-1 text-sm text-muted-foreground hover:text-foreground mb-5">
        <ChevronLeft size={16}/> 설정
      </button>
      <h1 className="text-xl font-bold text-foreground mb-2">Category</h1>
      <p className="text-sm text-muted-foreground mb-1">
        현재 사용 중인 Category와 항목 수를 확인합니다.
      </p>
      <p className="text-xs text-muted-foreground mb-5">
        Category 추가·수정·삭제 기능은 추후 제공됩니다.
      </p>

      {loading ? (
        <div className="space-y-2">
          {[0, 1, 2, 3].map((i) => (
            <div key={i} className="bg-card border border-border rounded-2xl p-4 space-y-2">
              <div className="h-4 w-32 animate-pulse rounded bg-muted"/>
              <div className="h-3 w-48 animate-pulse rounded bg-muted"/>
            </div>
          ))}
        </div>
      ) : error ? (
        <div className="bg-card border border-border rounded-xl p-4 flex flex-col sm:flex-row sm:items-center sm:justify-between gap-3">
          <p className="text-sm text-muted-foreground">{error}</p>
          <button onClick={() => void loadCategories()}
            className="inline-flex items-center justify-center gap-1.5 text-xs bg-primary text-white px-3 py-1.5 rounded-xl hover:bg-blue-700 transition-colors font-medium self-start sm:self-auto">
            <RefreshCw size={12}/> 다시 시도
          </button>
        </div>
      ) : categories.length === 0 ? (
        <div className="bg-card border border-border rounded-xl p-4">
          <p className="text-sm text-muted-foreground">등록된 Category가 없습니다.</p>
        </div>
      ) : (
        <div className="space-y-2">
          {categories.map((cat) => {
            const presentation = getCategoryPresentation(cat.name);
            const Icon = presentation.icon;
            return (
              <div key={cat.id} className="bg-card border border-border rounded-2xl p-4 flex items-center gap-3">
                <div className="w-8 h-8 rounded-xl flex items-center justify-center flex-shrink-0"
                  style={{ backgroundColor: presentation.bgColor, color: presentation.color }}>
                  <Icon size={16}/>
                </div>
                <div className="flex-1 min-w-0">
                  <div className="text-sm font-semibold text-foreground">{cat.name}</div>
                  <div className="flex flex-wrap gap-3 text-[10px] text-muted-foreground mt-0.5">
                    <span>순서 {cat.sort_order}</span>
                    <span>전체 {cat.item_count.toLocaleString("ko-KR")}</span>
                    <span className="text-blue-600">예정 {cat.planned_count.toLocaleString("ko-KR")}</span>
                    <span className="text-emerald-600">완료 {cat.completed_count.toLocaleString("ko-KR")}</span>
                  </div>
                </div>
              </div>
            );
          })}
        </div>
      )}
    </div>
  );
}

// ─── Home Page ────────────────────────────────────────────────────────────────

function HomeSectionError({ message, onRetry }: { message: string; onRetry: () => void }) {
  return (
    <div className="bg-card border border-border rounded-xl p-4 flex flex-col sm:flex-row sm:items-center sm:justify-between gap-3">
      <p className="text-sm text-muted-foreground">{message}</p>
      <button onClick={onRetry}
        className="inline-flex items-center justify-center gap-1.5 text-xs bg-primary text-white px-3 py-1.5 rounded-xl hover:bg-blue-700 transition-colors font-medium self-start sm:self-auto">
        <RefreshCw size={12}/> 다시 시도
      </button>
    </div>
  );
}

function HomePage({ setPage, openAddItem, openItemDetail }: {
  setPage: (p: Page) => void;
  openAddItem: () => void;
  openItemDetail: (itemId: string) => void;
}) {
  // Hook lives in HomePage: App uses conditional page render, so data loads on Home entry
  // and refetches when returning to Home (no cache library in B-2a).
  const {
    summary,
    categories,
    recentItems,
    isSummaryLoading,
    isCategoriesLoading,
    isRecentItemsLoading,
    summaryError,
    categoriesError,
    recentItemsError,
    reloadSummary,
    reloadCategories,
    reloadRecentItems,
  } = useHomeReadData();

  const homeCategories = categories.map(mapApiCategoryToHomeCategory);
  const recent = recentItems.map(mapApiItemToHomeRecentItem);

  const statDefs = [
    { label:"전체 항목",    key:"item_count" as const },
    { label:"앞으로 볼",    key:"planned_count" as const },
    { label:"완료 항목",    key:"completed_count" as const },
    { label:"Collection",  key:"collection_count" as const },
  ];

  return (
    <div className="max-w-5xl mx-auto px-4 sm:px-6 py-6 space-y-7">
      {/* Hero */}
      <div className="bg-card border border-border rounded-2xl p-6 sm:p-8">
        <p className="text-sm text-muted-foreground mb-1">내 콘텐츠를 한눈에 확인하세요.</p>
        <h1 className="text-2xl sm:text-3xl font-bold text-foreground mb-5">오늘은 무엇을 선택할까요?</h1>
        <div className="flex flex-wrap gap-3">
          <button onClick={() => setPage("search")}
            className="inline-flex items-center gap-2 border border-border bg-card text-foreground px-5 py-2.5 rounded-xl font-medium hover:bg-muted transition-colors">
            <Search size={16}/> 콘텐츠 검색
          </button>
          <button onClick={openAddItem}
            className="inline-flex items-center gap-2 text-primary px-4 py-2.5 rounded-xl font-medium hover:bg-blue-50 transition-colors">
            <Plus size={16}/> 직접 항목 추가
          </button>
        </div>
      </div>

      {/* Stats — Backend Summary (no Mock fallback) */}
      <div>
        <h2 className="text-xs font-semibold text-muted-foreground uppercase tracking-wide mb-3">요약 통계</h2>
        {summaryError && !isSummaryLoading ? (
          <HomeSectionError message="통계를 불러오지 못했습니다." onRetry={reloadSummary}/>
        ) : (
          <div className="grid grid-cols-2 sm:grid-cols-4 gap-3">
            {statDefs.map(s => (
              <div key={s.label} className="bg-card border border-border rounded-2xl p-4">
                {isSummaryLoading || !summary ? (
                  <div className="h-8 w-20 animate-pulse rounded bg-muted"/>
                ) : (
                  <div className="text-2xl font-bold text-foreground">
                    {summary[s.key].toLocaleString("ko-KR")}
                  </div>
                )}
                <div className="text-xs text-muted-foreground mt-0.5">{s.label}</div>
              </div>
            ))}
          </div>
        )}
      </div>

      <div>
        <div className="flex items-center justify-between mb-3">
          <h2 className="text-xs font-semibold text-muted-foreground uppercase tracking-wide">최근 등록</h2>
          <button onClick={() => setPage("items")} className="text-xs text-primary hover:underline">전체 보기</button>
        </div>
        {recentItemsError && !isRecentItemsLoading ? (
          <HomeSectionError message="최근 등록 항목을 불러오지 못했습니다." onRetry={reloadRecentItems}/>
        ) : isRecentItemsLoading ? (
          <div className="space-y-2">
            {[0,1,2,3,4].map(i => (
              <div key={i} className="bg-card border border-border rounded-xl p-3 flex items-center gap-3">
                <div className="w-10 h-14 rounded-lg animate-pulse bg-muted flex-shrink-0"/>
                <div className="flex-1 min-w-0 space-y-2">
                  <div className="h-4 w-3/4 animate-pulse rounded bg-muted"/>
                  <div className="h-3 w-1/3 animate-pulse rounded bg-muted"/>
                </div>
                <div className="h-4 w-10 animate-pulse rounded bg-muted flex-shrink-0"/>
              </div>
            ))}
          </div>
        ) : recent.length === 0 ? (
          <div className="bg-card border border-border rounded-xl p-4">
            <p className="text-sm text-muted-foreground">최근 등록된 항목이 없습니다.</p>
          </div>
        ) : (
          <div className="space-y-2">
            {recent.map(item => {
              const Icon = item.presentation.icon;
              return (
                <div key={item.id}
                  role="button"
                  tabIndex={0}
                  onClick={() => openItemDetail(item.id)}
                  onKeyDown={e => {
                    if (e.key === "Enter" || e.key === " ") {
                      e.preventDefault();
                      openItemDetail(item.id);
                    }
                  }}
                  className="bg-card border border-border rounded-xl p-3 flex items-center gap-3 hover:border-primary/20 transition-colors cursor-pointer">
                  {/* Placeholder poster — Legacy items have no poster_path */}
                  <div className="w-10 h-14 text-base rounded-lg flex items-center justify-center flex-shrink-0 text-white font-bold"
                    style={{ backgroundColor: item.presentation.color }}>
                    {item.title.charAt(0)}
                  </div>
                  <div className="flex-1 min-w-0">
                    <div className="text-sm font-medium text-foreground truncate">{item.title}</div>
                    <div className="mt-0.5">
                      <span className="inline-flex items-center gap-1 rounded font-medium text-[10px] px-1.5 py-px"
                        style={{ backgroundColor: item.presentation.bgColor, color: item.presentation.color }}>
                        <Icon size={10}/>{item.categoryName}
                      </span>
                    </div>
                  </div>
                  <StatusBadge status={item.status} sm/>
                </div>
              );
            })}
          </div>
        )}
      </div>

      <div>
        <h2 className="text-xs font-semibold text-muted-foreground uppercase tracking-wide mb-3">카테고리별 현황</h2>
        {categoriesError && !isCategoriesLoading ? (
          <HomeSectionError message="카테고리를 불러오지 못했습니다." onRetry={reloadCategories}/>
        ) : isCategoriesLoading ? (
          <div className="grid sm:grid-cols-2 gap-2">
            {[0,1,2,3,4,5].map(i => (
              <div key={i} className="bg-card border border-border rounded-xl p-4 space-y-2">
                <div className="flex items-center justify-between">
                  <div className="h-4 w-24 animate-pulse rounded bg-muted"/>
                  <div className="h-3 w-12 animate-pulse rounded bg-muted"/>
                </div>
                <div className="h-1.5 w-full animate-pulse rounded-full bg-muted"/>
                <div className="flex justify-between">
                  <div className="h-3 w-16 animate-pulse rounded bg-muted"/>
                  <div className="h-3 w-16 animate-pulse rounded bg-muted"/>
                </div>
              </div>
            ))}
          </div>
        ) : (
          <div className="grid sm:grid-cols-2 gap-2">
            {homeCategories.map(cat => {
              const Icon = cat.presentation.icon;
              const total = cat.itemCount;
              return (
                <div key={cat.id} className="bg-card border border-border rounded-xl p-4">
                  <div className="flex items-center justify-between mb-2">
                    <div className="flex items-center gap-2">
                      <span style={{ color: cat.presentation.color }}><Icon size={14}/></span>
                      <span className="text-sm font-medium text-foreground">{cat.name}</span>
                    </div>
                    <span className="text-xs text-muted-foreground">{total.toLocaleString("ko-KR")}개</span>
                  </div>
                  <ProgressBar value={total > 0 ? (cat.completedCount / total) * 100 : 0}/>
                  <div className="flex justify-between mt-1.5 text-xs">
                    <span className="text-blue-600">예정 {cat.plannedCount.toLocaleString("ko-KR")}</span>
                    <span className="text-emerald-600">완료 {cat.completedCount.toLocaleString("ko-KR")}</span>
                  </div>
                </div>
              );
            })}
          </div>
        )}
      </div>
    </div>
  );
}

// ─── Search Page ──────────────────────────────────────────────────────────────
// Implemented in ./search/SearchPage.tsx

// ─── Items Page ───────────────────────────────────────────────────────────────

function ItemsPage({
  showToast,
  openAddItem,
  openItemDetail,
  initialSnapshot,
  onSnapshotChange,
}: {
  showToast: (m: string) => void;
  openAddItem: (opts?: { categoryId?: string | null }) => void;
  openItemDetail: (itemId: string) => void;
  initialSnapshot?: ItemsPageStateSnapshot | null;
  onSnapshotChange?: (snapshot: ItemsPageStateSnapshot) => void;
}) {
  const [tableView, setTableV] = useState(
    () => (initialSnapshot?.viewMode ?? "card") === "table",
  );
  const viewModeRef = useRef<ItemsViewMode>(
    initialSnapshot?.viewMode ?? "card",
  );
  const [selected, setSelected] = useState<Set<string>>(new Set());
  const onSnapshotChangeRef = useRef(onSnapshotChange);
  onSnapshotChangeRef.current = onSnapshotChange;

  const {
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
    reloadItems,
    reloadCategories,
  } = useItemsReadData({
    initialState: initialSnapshot,
    onQueryChange: (query: ItemsQuerySnapshot) => {
      onSnapshotChangeRef.current?.({
        ...query,
        viewMode: viewModeRef.current,
      });
    },
  });

  const setViewMode = (mode: ItemsViewMode) => {
    viewModeRef.current = mode;
    setTableV(mode === "table");
    onSnapshotChangeRef.current?.({
      searchInput,
      appliedSearch,
      categoryId,
      status,
      sort,
      order,
      page,
      pageSize,
      viewMode: mode,
    });
  };

  const listItems = items.map(mapApiItemToItemsListViewModel);
  const hasActiveFilters =
    Boolean(appliedSearch) ||
    categoryId !== null ||
    status !== "ALL" ||
    sort !== "updated_at" ||
    order !== "desc";

  const sortSelectValue =
    sort === "title" && order === "asc"
      ? "title"
      : sort === "rating" && order === "desc"
        ? "rating"
        : "updatedAt";

  const onSortChange = (value: string) => {
    if (value === "title") setSortPair("title", "asc");
    else if (value === "rating") setSortPair("rating", "desc");
    else setSortPair("updated_at", "desc");
  };

  // Clear selection when the visible page of results changes.
  useEffect(() => {
    setSelected(new Set());
  }, [page, pageSize, appliedSearch, categoryId, status, sort, order, items]);

  const toggleSelect = (id: string) =>
    setSelected(prev => { const s=new Set(prev); s.has(id)?s.delete(id):s.add(id); return s; });
  const toggleAll = () =>
    setSelected(prev => prev.size===listItems.length ? new Set() : new Set(listItems.map(i=>i.id)));

  const onItemActivate = (itemId: string) => {
    openItemDetail(itemId);
  };

  const onBulkAction = () => {
    showToast("일괄 작업 API는 아직 연결되지 않았습니다.");
  };

  const rangeStart = total === 0 ? 0 : (page - 1) * pageSize + 1;
  const rangeEnd = Math.min(page * pageSize, total);

  const Card = ({ item }: { item: ReturnType<typeof mapApiItemToItemsListViewModel> }) => {
    const Icon = item.presentation.icon;
    return (
      <div className="bg-card border border-border rounded-2xl p-4 flex items-center gap-3 hover:border-primary/20 transition-colors cursor-pointer group"
        role="button"
        tabIndex={0}
        aria-label={`${item.title} 상세 보기`}
        onClick={() => onItemActivate(item.id)}
        onKeyDown={e => {
          if (e.key === "Enter" || e.key === " ") {
            e.preventDefault();
            onItemActivate(item.id);
          }
        }}>
        <input
          type="checkbox"
          checked={selected.has(item.id)}
          onChange={() => toggleSelect(item.id)}
          onClick={(e) => e.stopPropagation()}
          aria-label={`${item.title} 선택`}
          className="w-3.5 h-3.5 flex-shrink-0 cursor-pointer accent-primary"
        />
        <div className="w-10 h-14 text-base rounded-lg flex items-center justify-center flex-shrink-0 text-white font-bold"
          style={{ backgroundColor: item.presentation.color }}>
          {item.title.charAt(0)}
        </div>
        <div className="flex-1 min-w-0">
          <div className="flex items-start justify-between gap-2">
            <div className="font-medium text-foreground text-sm leading-snug truncate group-hover:text-primary transition-colors">{item.title}</div>
            <button onClick={e=>{ e.stopPropagation(); }} className="text-muted-foreground flex-shrink-0 hover:text-foreground">
              <MoreVertical size={14}/>
            </button>
          </div>
          <div className="flex flex-wrap gap-1 mt-1.5">
            <span className="inline-flex items-center gap-1 rounded font-medium text-[10px] px-1.5 py-px"
              style={{ backgroundColor: item.presentation.bgColor, color: item.presentation.color }}>
              <Icon size={10}/>{item.categoryName}
            </span>
            <StatusBadge status={item.status} sm/>
          </div>
          {item.collectionName && <div className="text-[10px] text-muted-foreground mt-1 flex items-center gap-0.5"><Layers size={9}/>{item.collectionName}</div>}
          {item.progressNote && <div className="text-[10px] text-muted-foreground">{item.progressNote}</div>}
          <div className="mt-1"><StarRating rating={displayItemRating(item.rating)} sm/></div>
        </div>
      </div>
    );
  };

  return (
    <div className="max-w-7xl mx-auto px-4 sm:px-6 py-6">
      <div className="flex items-center justify-between mb-5">
        <h1 className="text-xl font-bold text-foreground">전체 항목</h1>
        <button onClick={() => openAddItem({ categoryId })}
          className="inline-flex items-center gap-1.5 bg-primary text-white px-4 py-2 rounded-xl text-sm font-medium hover:bg-blue-700 transition-colors">
          <Plus size={14}/> 신규 항목 추가
        </button>
      </div>

      {/* Bulk action bar — visual only; write APIs not connected */}
      {selected.size > 0 && (
        <div className="bg-primary/10 border border-primary/20 rounded-2xl px-4 py-3 mb-4 flex items-center gap-3 flex-wrap">
          <span className="text-sm font-medium text-primary">{selected.size}개 항목 선택됨</span>
          <div className="flex gap-2 ml-2">
            {["완료 처리","Category 이동","Collection 지정","삭제"].map(a => (
              <button key={a} onClick={onBulkAction}
                className={`text-xs px-3 py-1.5 rounded-lg border font-medium transition-colors ${a==="삭제"?"border-red-200 text-red-600 hover:bg-red-50":"border-border text-foreground hover:bg-muted"}`}>
                {a}
              </button>
            ))}
          </div>
          <button onClick={() => setSelected(new Set())} className="ml-auto text-muted-foreground hover:text-foreground">
            <X size={16}/>
          </button>
        </div>
      )}

      {/* Toolbar */}
      <div className="bg-card border border-border rounded-2xl p-4 mb-4 space-y-3">
        <div className="flex gap-2">
          <div className="flex-1 relative">
            <Search size={13} className="absolute left-3 top-1/2 -translate-y-1/2 text-muted-foreground pointer-events-none"/>
            <input value={searchInput}
              onChange={e => setSearchInput(e.target.value)}
              onKeyDown={e => { if (e.key === "Enter") applySearchNow(); }}
              placeholder="제목 검색"
              className="w-full pl-8 pr-3 py-2 border border-border rounded-xl text-sm bg-background focus:outline-none focus:ring-2 focus:ring-primary/25"/>
          </div>
          <div className="hidden sm:flex gap-1">
            <button onClick={() => setViewMode("card")}
              className={`p-2 rounded-lg border transition-colors ${!tableView?"border-primary bg-blue-50 text-primary":"border-border text-muted-foreground hover:text-foreground"}`}>
              <AlignJustify size={15}/>
            </button>
            <button onClick={() => setViewMode("table")}
              className={`p-2 rounded-lg border transition-colors ${tableView?"border-primary bg-blue-50 text-primary":"border-border text-muted-foreground hover:text-foreground"}`}>
              <Grid size={15}/>
            </button>
          </div>
        </div>
        <div className="flex flex-wrap gap-2">
          {categoriesError && !isCategoriesLoading ? (
            <div className="flex items-center gap-2 text-xs text-muted-foreground">
              <span>카테고리를 불러오지 못했습니다.</span>
              <button onClick={reloadCategories}
                className="inline-flex items-center gap-1 text-xs bg-primary text-white px-2.5 py-1 rounded-lg hover:bg-blue-700 transition-colors font-medium">
                <RefreshCw size={11}/> 다시 시도
              </button>
            </div>
          ) : (
            <select
              value={categoryId ?? "all"}
              onChange={e => setCategoryId(e.target.value === "all" ? null : e.target.value)}
              disabled={isCategoriesLoading}
              className="text-xs border border-border rounded-lg px-3 py-1.5 bg-background focus:outline-none focus:ring-2 focus:ring-primary/25">
              <option value="all">전체 카테고리</option>
              {categories.map(c => <option key={c.id} value={c.id}>{c.name}</option>)}
            </select>
          )}
          <select
            value={status === "ALL" ? "all" : status}
            onChange={e => {
              const v = e.target.value;
              setStatus(v === "all" ? "ALL" : (v as "PLANNED" | "COMPLETED"));
            }}
            className="text-xs border border-border rounded-lg px-3 py-1.5 bg-background focus:outline-none focus:ring-2 focus:ring-primary/25">
            <option value="all">전체 상태</option><option value="PLANNED">예정</option><option value="COMPLETED">완료</option>
          </select>
          <select value={sortSelectValue} onChange={e => onSortChange(e.target.value)}
            className="text-xs border border-border rounded-lg px-3 py-1.5 bg-background focus:outline-none focus:ring-2 focus:ring-primary/25">
            <option value="updatedAt">최근 수정순</option><option value="title">제목순</option><option value="rating">평점 높은 순</option>
          </select>
          <select value={pageSize} onChange={e => setPageSize(Number(e.target.value))}
            className="text-xs border border-border rounded-lg px-3 py-1.5 bg-background focus:outline-none focus:ring-2 focus:ring-primary/25">
            <option value={25}>25개씩</option><option value={50}>50개씩</option><option value={100}>100개씩</option>
          </select>
        </div>
      </div>

      <p className="text-xs text-muted-foreground mb-3">
        {isItemsLoading && items.length === 0
          ? "불러오는 중…"
          : `${total.toLocaleString("ko-KR")}건 · ${page}/${Math.max(totalPages, 1)} 페이지`}
      </p>

      {itemsError && !isItemsLoading ? (
        <div className="bg-card border border-border rounded-2xl p-6 flex flex-col sm:flex-row sm:items-center sm:justify-between gap-3 mb-4">
          <p className="text-sm text-muted-foreground">항목 목록을 불러오지 못했습니다.</p>
          <button onClick={reloadItems}
            className="inline-flex items-center justify-center gap-1.5 text-xs bg-primary text-white px-3 py-1.5 rounded-xl hover:bg-blue-700 transition-colors font-medium self-start sm:self-auto">
            <RefreshCw size={12}/> 다시 시도
          </button>
        </div>
      ) : isItemsLoading && items.length === 0 ? (
        <>
          {tableView && (
            <div className="hidden sm:block bg-card border border-border rounded-2xl overflow-hidden mb-4">
              <table className="w-full text-sm">
                <thead>
                  <tr className="border-b border-border bg-muted/40">
                    <th className="px-3 py-3 w-8"/>
                    {["","제목","카테고리","Collection","상태","평점","Progress Note","수정일",""].map((h,i) => (
                      <th key={i} className="text-left px-3 py-3 text-[10px] font-semibold text-muted-foreground uppercase tracking-wide">{h}</th>
                    ))}
                  </tr>
                </thead>
                <tbody>
                  {Array.from({ length: 8 }).map((_, i) => (
                    <tr key={i} className="border-b border-border">
                      <td className="px-3 py-3" colSpan={10}>
                        <div className="h-10 animate-pulse rounded bg-muted"/>
                      </td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          )}
          <div className={tableView?"sm:hidden space-y-2":"space-y-2"}>
            {Array.from({ length: 6 }).map((_, i) => (
              <div key={i} className="bg-card border border-border rounded-2xl p-4 flex items-center gap-3">
                <div className="w-3.5 h-3.5 rounded animate-pulse bg-muted flex-shrink-0"/>
                <div className="w-10 h-14 rounded-lg animate-pulse bg-muted flex-shrink-0"/>
                <div className="flex-1 space-y-2">
                  <div className="h-4 w-2/3 animate-pulse rounded bg-muted"/>
                  <div className="h-3 w-1/3 animate-pulse rounded bg-muted"/>
                </div>
              </div>
            ))}
          </div>
        </>
      ) : listItems.length === 0 ? (
        <div className="bg-card border border-border rounded-2xl text-center py-16">
          <Search size={28} className="text-muted-foreground mx-auto mb-3"/>
          <p className="font-medium text-foreground">
            {hasActiveFilters ? "조건에 맞는 항목이 없습니다." : "등록된 항목이 없습니다."}
          </p>
          <p className="text-sm text-muted-foreground mt-1">
            {hasActiveFilters ? "다른 검색어 또는 필터를 시도해 보세요" : "신규 항목을 추가해 보세요"}
          </p>
          {hasActiveFilters && (
            <button onClick={resetFilters}
              className="mt-4 inline-flex items-center gap-1.5 text-xs bg-primary text-white px-3 py-1.5 rounded-xl hover:bg-blue-700 transition-colors font-medium">
              필터 초기화
            </button>
          )}
        </div>
      ) : (
        <>
          {/* Desktop table */}
          {tableView && (
            <div className="hidden sm:block bg-card border border-border rounded-2xl overflow-hidden mb-4 relative">
              {isItemsLoading && (
                <div className="absolute inset-0 bg-card/40 pointer-events-none z-10"/>
              )}
              <table className="w-full text-sm">
                <thead>
                  <tr className="border-b border-border bg-muted/40">
                    <th className="px-3 py-3 w-8">
                      <input type="checkbox" onChange={toggleAll} checked={selected.size===listItems.length&&listItems.length>0} className="accent-primary"/>
                    </th>
                    {["","제목","카테고리","Collection","상태","평점","Progress Note","수정일",""].map((h,i) => (
                      <th key={i} className="text-left px-3 py-3 text-[10px] font-semibold text-muted-foreground uppercase tracking-wide">{h}</th>
                    ))}
                  </tr>
                </thead>
                <tbody>
                  {listItems.map((item,i) => {
                    const Icon = item.presentation.icon;
                    return (
                      <tr key={item.id}
                        onClick={() => onItemActivate(item.id)}
                        onKeyDown={e => {
                          if (e.key === "Enter" || e.key === " ") {
                            e.preventDefault();
                            onItemActivate(item.id);
                          }
                        }}
                        tabIndex={0}
                        aria-label={`${item.title} 상세 보기`}
                        className={`border-b border-border hover:bg-muted/20 transition-colors cursor-pointer ${i%2===1?"bg-muted/5":""} ${selected.has(item.id)?"bg-blue-50/50":""}`}>
                        <td className="px-3 py-3" onClick={e=>e.stopPropagation()}>
                          <input type="checkbox" checked={selected.has(item.id)} onChange={()=>toggleSelect(item.id)} className="accent-primary"/>
                        </td>
                        <td className="px-3 py-3 w-12">
                          <div className="w-10 h-14 text-base rounded-lg flex items-center justify-center flex-shrink-0 text-white font-bold"
                            style={{ backgroundColor: item.presentation.color }}>
                            {item.title.charAt(0)}
                          </div>
                        </td>
                        <td className="px-3 py-3 font-medium text-foreground max-w-xs">
                          <div className="truncate">{item.title}</div>
                        </td>
                        <td className="px-3 py-3">
                          <span className="inline-flex items-center gap-1 rounded font-medium text-[10px] px-1.5 py-px"
                            style={{ backgroundColor: item.presentation.bgColor, color: item.presentation.color }}>
                            <Icon size={10}/>{item.categoryName}
                          </span>
                        </td>
                        <td className="px-3 py-3 text-xs text-muted-foreground">{item.collectionName || "—"}</td>
                        <td className="px-3 py-3"><StatusBadge status={item.status} sm/></td>
                        <td className="px-3 py-3"><StarRating rating={displayItemRating(item.rating)} sm/></td>
                        <td className="px-3 py-3 text-xs text-muted-foreground max-w-[120px] truncate">{item.progressNote||"—"}</td>
                        <td className="px-3 py-3 text-xs text-muted-foreground whitespace-nowrap">{formatDate(item.updatedAt) || "—"}</td>
                        <td className="px-3 py-3" onClick={e=>e.stopPropagation()}>
                          <button className="text-muted-foreground hover:text-foreground"><MoreVertical size={14}/></button>
                        </td>
                      </tr>
                    );
                  })}
                </tbody>
              </table>
            </div>
          )}

          {/* Card list */}
          <div className={`relative ${tableView?"sm:hidden space-y-2":"space-y-2"}`}>
            {isItemsLoading && (
              <div className="absolute inset-0 bg-background/30 pointer-events-none z-10 rounded-2xl"/>
            )}
            {listItems.map(item => <Card key={item.id} item={item}/>)}
          </div>
        </>
      )}

      {/* Pagination */}
      {!itemsError && totalPages > 1 && (
        <div className="flex items-center justify-between mt-5">
          <p className="text-xs text-muted-foreground">
            {rangeStart}–{rangeEnd} / {total.toLocaleString("ko-KR")}건
          </p>
          <div className="flex items-center gap-1">
            <button onClick={() => setPage(1)} disabled={!hasPrevious}
              className="p-1.5 rounded-lg border border-border text-muted-foreground hover:text-foreground disabled:opacity-30 transition-colors">
              <ChevronsLeft size={14}/>
            </button>
            <button onClick={() => setPage(page - 1)} disabled={!hasPrevious}
              className="p-1.5 rounded-lg border border-border text-muted-foreground hover:text-foreground disabled:opacity-30 transition-colors">
              <ChevronLeft size={14}/>
            </button>
            {Array.from({length:Math.min(5,totalPages)},(_,i) => {
              const p = Math.min(Math.max(page-2,1)+i, totalPages);
              return (
                <button key={`${p}-${i}`} onClick={() => setPage(p)}
                  className={`w-7 h-7 rounded-lg text-xs font-medium border transition-colors ${page===p?"border-primary bg-primary text-white":"border-border text-foreground hover:bg-muted"}`}>
                  {p}
                </button>
              );
            })}
            <button onClick={() => setPage(page + 1)} disabled={!hasNext}
              className="p-1.5 rounded-lg border border-border text-muted-foreground hover:text-foreground disabled:opacity-30 transition-colors">
              <ChevronRight size={14}/>
            </button>
            <button onClick={() => setPage(totalPages)} disabled={!hasNext}
              className="p-1.5 rounded-lg border border-border text-muted-foreground hover:text-foreground disabled:opacity-30 transition-colors">
              <ChevronsRight size={14}/>
            </button>
          </div>
        </div>
      )}
    </div>
  );
}

// ─── Collections Page ─────────────────────────────────────────────────────────

interface CollectionDetailSelection {
  collectionId: string;
  itemsPage: number;
}

function CollectionCategoryBadges({
  categories,
  sm,
}: {
  categories: CollectionListItemViewModel["categories"];
  sm?: boolean;
}) {
  if (categories.length === 0) {
    return (
      <span className={`inline-flex items-center rounded font-medium text-muted-foreground bg-muted ${sm?"text-[10px] px-1.5 py-px":"text-xs px-2 py-0.5"}`}>
        카테고리 없음
      </span>
    );
  }
  return (
    <div className="flex flex-wrap gap-1">
      {categories.map((category) => {
        const Icon = category.presentation.icon;
        return (
          <span
            key={category.id}
            title={`${category.name} ${category.itemCount}개`}
            className={`inline-flex items-center gap-1 rounded font-medium ${sm?"text-[10px] px-1.5 py-px":"text-xs px-2 py-0.5"}`}
            style={{
              backgroundColor: category.presentation.bgColor,
              color: category.presentation.color,
            }}
          >
            <Icon size={sm ? 10 : 12}/>{category.name}
          </span>
        );
      })}
    </div>
  );
}

function CollectionsPage({
  showToast,
  initialSnapshot,
  onSnapshotChange,
  selection,
  onSelectionChange,
  openItemDetail,
  openAddItem,
  onNavigateToSearch,
  itemWriteBusy,
}: {
  showToast: (m: string) => void;
  initialSnapshot?: CollectionsQuerySnapshot | null;
  onSnapshotChange?: (snapshot: CollectionsQuerySnapshot) => void;
  selection: CollectionDetailSelection | null;
  onSelectionChange: (selection: CollectionDetailSelection | null) => void;
  openItemDetail: (
    itemId: string,
    context: { collectionId: string; collectionItemsPage: number },
  ) => void;
  openAddItem: (opts: {
    origin: "collections";
    lockedCollection: { id: string; name: string };
    collectionItemsPage?: number;
  }) => void;
  onNavigateToSearch: () => void;
  itemWriteBusy?: boolean;
}) {
  const onSnapshotChangeRef = useRef(onSnapshotChange);
  onSnapshotChangeRef.current = onSnapshotChange;

  const {
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
    reload,
  } = useCollectionsReadData({
    initialState: initialSnapshot,
    onQueryChange: (query) => {
      onSnapshotChangeRef.current?.(query);
    },
  });

  const listItems = useMemo(
    () => collections.map(mapApiCollectionToListItem),
    [collections],
  );

  const rangeStart = total === 0 ? 0 : (page - 1) * pageSize + 1;
  const rangeEnd = Math.min(page * pageSize, total);

  const [showCreateModal, setShowCreateModal] = useState(false);
  const [createName, setCreateName] = useState("");
  const [createPending, setCreatePending] = useState(false);
  const [createValidationError, setCreateValidationError] = useState<string | null>(null);
  const [createServerError, setCreateServerError] = useState<string | null>(null);

  const openCreateModal = () => {
    if (itemWriteBusy) return;
    setCreateName("");
    setCreatePending(false);
    setCreateValidationError(null);
    setCreateServerError(null);
    setShowCreateModal(true);
  };

  const handleCreateNameChange = (value: string) => {
    setCreateName(value);
    setCreateValidationError(null);
    if (createServerError) setCreateServerError(null);
  };

  const handleCreateSubmit = async () => {
    const normalizedName = normalizeCollectionNameInput(createName);
    const validationMessage = validateCollectionName(normalizedName);
    if (validationMessage) {
      setCreateValidationError(validationMessage);
      setCreateServerError(null);
      return;
    }
    if (createPending) return;
    setCreatePending(true);
    setCreateValidationError(null);
    setCreateServerError(null);
    try {
      const created = await createCollection({ name: normalizedName });
      setShowCreateModal(false);
      await reload();
      onSelectionChange({ collectionId: created.id, itemsPage: 1 });
      showToast("컬렉션을 만들었습니다.");
    } catch (err) {
      if (err instanceof ApiError && err.status === 409) {
        setCreateServerError(collectionWriteConflictInline());
      } else if (err instanceof ApiError && err.status === 422) {
        setCreateServerError(collectionWriteValidationInline());
      } else if (isCollectionWriteNetworkOrServerError(err)) {
        showToast(collectionCreateFailureToast());
      } else {
        showToast(collectionCreateFailureToast());
      }
    } finally {
      setCreatePending(false);
    }
  };

  if (selection) {
    return (
      <CollectionDetailInline
        collectionId={selection.collectionId}
        itemsPage={selection.itemsPage}
        onItemsPageChange={(itemsPage) =>
          onSelectionChange({ collectionId: selection.collectionId, itemsPage })
        }
        onBack={() => onSelectionChange(null)}
        openItemDetail={openItemDetail}
        openAddItem={openAddItem}
        onNavigateToSearch={onNavigateToSearch}
        itemWriteBusy={itemWriteBusy}
        showToast={showToast}
        onCollectionDeleted={() => {
          onSelectionChange(null);
          void reload();
        }}
        onCollectionUpdated={() => {
          void reload();
        }}
        onCollectionMissing={() => {
          onSelectionChange(null);
          void reload();
        }}
      />
    );
  }

  return (
    <div className="max-w-4xl mx-auto px-4 sm:px-6 py-6">
      <div className="flex items-center justify-between mb-5">
        <h1 className="text-xl font-bold text-foreground">Collection</h1>
        <button
          type="button"
          onClick={openCreateModal}
          disabled={itemWriteBusy}
          className="inline-flex items-center gap-1.5 bg-primary text-white px-4 py-2 rounded-xl text-sm font-medium hover:bg-blue-700 transition-colors disabled:opacity-50 disabled:cursor-not-allowed"
        >
          <Plus size={14}/> 추가
        </button>
      </div>
      <div className="relative mb-4">
        <Search size={13} className="absolute left-3 top-1/2 -translate-y-1/2 text-muted-foreground pointer-events-none"/>
        <input
          value={searchInput}
          onChange={(e) => setSearchInput(e.target.value)}
          onKeyDown={(e) => {
            if (e.key === "Enter") applySearchNow();
          }}
          placeholder="Collection 이름 검색"
          aria-label="Collection 이름 검색"
          className="w-full pl-8 pr-4 py-2 border border-border rounded-xl text-sm bg-card focus:outline-none focus:ring-2 focus:ring-primary/25"
        />
      </div>

      {error ? (
        <div className="bg-card border border-border rounded-2xl p-8 text-center">
          <p className="text-sm text-foreground mb-1">Collection 목록을 불러오지 못했습니다.</p>
          <p className="text-xs text-muted-foreground mb-4">잠시 후 다시 시도해 주세요.</p>
          <button
            type="button"
            onClick={() => void reload()}
            className="inline-flex items-center gap-1.5 text-sm text-primary border border-primary/25 px-4 py-2 rounded-xl hover:bg-blue-50 transition-colors"
          >
            <RefreshCw size={14}/> 다시 시도
          </button>
        </div>
      ) : isLoading && listItems.length === 0 ? (
        <div className="bg-card border border-border rounded-2xl py-16 text-center text-sm text-muted-foreground">
          Collection을 불러오는 중…
        </div>
      ) : total === 0 ? (
        <div className="bg-card border border-border rounded-2xl p-8 text-center">
          {appliedSearch ? (
            <>
              <p className="text-sm text-foreground mb-1">검색 결과가 없습니다.</p>
              <p className="text-xs text-muted-foreground mb-4">다른 Collection 이름으로 검색해 보세요.</p>
              <button
                type="button"
                onClick={clearSearch}
                className="text-sm text-primary hover:underline"
              >
                검색어 지우기
              </button>
            </>
          ) : (
            <>
              <p className="text-sm text-foreground mb-1">등록된 Collection이 없습니다.</p>
              <p className="text-xs text-muted-foreground mb-4">새 컬렉션을 추가해 보세요.</p>
              <button
                type="button"
                onClick={openCreateModal}
                className="inline-flex items-center gap-1.5 text-sm text-primary border border-primary/25 px-4 py-2 rounded-xl hover:bg-blue-50 transition-colors"
              >
                <Plus size={14}/> 새 컬렉션
              </button>
            </>
          )}
        </div>
      ) : (
        <>
          <p className="text-xs text-muted-foreground mb-4">
            {total.toLocaleString("ko-KR")}개
            {appliedSearch ? ` · “${appliedSearch}” 검색` : ""}
            {isLoading ? " · 갱신 중…" : ""}
          </p>
          <div className={`relative grid sm:grid-cols-2 gap-4 ${isLoading ? "opacity-70" : ""}`}>
            {listItems.map((col) => (
              <button
                key={col.id}
                type="button"
                onClick={() =>
                  onSelectionChange({ collectionId: col.id, itemsPage: 1 })
                }
                className="bg-card border border-border rounded-2xl p-5 text-left hover:border-primary/30 hover:shadow-sm transition-all"
              >
                <div className="flex items-start justify-between mb-2 gap-2">
                  <div className="min-w-0">
                    <CollectionCategoryBadges categories={col.categories} sm/>
                    <h3 className="font-semibold text-foreground mt-2 text-sm truncate">{col.name}</h3>
                  </div>
                  <ChevronRight size={15} className="text-muted-foreground mt-1 flex-shrink-0"/>
                </div>
                <p className="text-xs text-muted-foreground mb-3">
                  {col.itemCount}개 · 예정 {col.plannedCount} · 완료 {col.completedCount}
                </p>
                <ProgressBar value={col.progressPercent} className="mb-1.5"/>
                <div className="flex justify-between text-[10px] text-muted-foreground">
                  <span>진행률 {col.progressPercent}%</span>
                  <span className="flex items-center gap-0.5">
                    <Star size={9} className="text-muted-foreground"/>—
                  </span>
                </div>
              </button>
            ))}
          </div>

          {totalPages > 1 && (
            <div className="flex items-center justify-between mt-5">
              <p className="text-xs text-muted-foreground">
                {rangeStart}–{rangeEnd} / {total.toLocaleString("ko-KR")}개
                {totalPages > 0 ? ` · ${page}/${totalPages}페이지` : ""}
              </p>
              <div className="flex items-center gap-1">
                <button
                  type="button"
                  onClick={() => setPage(1)}
                  disabled={!hasPrevious}
                  aria-label="첫 페이지"
                  className="p-1.5 rounded-lg border border-border text-muted-foreground hover:text-foreground disabled:opacity-30 transition-colors"
                >
                  <ChevronsLeft size={14}/>
                </button>
                <button
                  type="button"
                  onClick={() => setPage(page - 1)}
                  disabled={!hasPrevious}
                  aria-label="이전 페이지"
                  className="p-1.5 rounded-lg border border-border text-muted-foreground hover:text-foreground disabled:opacity-30 transition-colors"
                >
                  <ChevronLeft size={14}/>
                </button>
                {Array.from({ length: Math.min(5, totalPages) }, (_, i) => {
                  const p = Math.min(Math.max(page - 2, 1) + i, totalPages);
                  return (
                    <button
                      key={`${p}-${i}`}
                      type="button"
                      onClick={() => setPage(p)}
                      aria-label={`${p}페이지`}
                      aria-current={page === p ? "page" : undefined}
                      className={`w-7 h-7 rounded-lg text-xs font-medium border transition-colors ${page === p ? "border-primary bg-primary text-white" : "border-border text-foreground hover:bg-muted"}`}
                    >
                      {p}
                    </button>
                  );
                })}
                <button
                  type="button"
                  onClick={() => setPage(page + 1)}
                  disabled={!hasNext}
                  aria-label="다음 페이지"
                  className="p-1.5 rounded-lg border border-border text-muted-foreground hover:text-foreground disabled:opacity-30 transition-colors"
                >
                  <ChevronRight size={14}/>
                </button>
                <button
                  type="button"
                  onClick={() => setPage(totalPages)}
                  disabled={!hasNext}
                  aria-label="마지막 페이지"
                  className="p-1.5 rounded-lg border border-border text-muted-foreground hover:text-foreground disabled:opacity-30 transition-colors"
                >
                  <ChevronsRight size={14}/>
                </button>
              </div>
            </div>
          )}
        </>
      )}

      <CollectionFormModal
        open={showCreateModal}
        mode="create"
        name={createName}
        pending={createPending}
        validationError={createValidationError}
        serverError={createServerError}
        onNameChange={handleCreateNameChange}
        onSubmit={() => void handleCreateSubmit()}
        onClose={() => {
          if (!createPending) setShowCreateModal(false);
        }}
      />
    </div>
  );
}

function CollectionDetailInline({
  collectionId,
  itemsPage,
  onItemsPageChange,
  onBack,
  openItemDetail,
  openAddItem,
  onNavigateToSearch,
  itemWriteBusy,
  showToast,
  onCollectionDeleted,
  onCollectionUpdated,
  onCollectionMissing,
}: {
  collectionId: string;
  itemsPage: number;
  onItemsPageChange: (page: number) => void;
  onBack: () => void;
  openItemDetail: (
    itemId: string,
    context: { collectionId: string; collectionItemsPage: number },
  ) => void;
  openAddItem: (opts: {
    origin: "collections";
    lockedCollection: { id: string; name: string };
    collectionItemsPage?: number;
  }) => void;
  onNavigateToSearch: () => void;
  itemWriteBusy?: boolean;
  showToast: (m: string) => void;
  onCollectionDeleted: () => void;
  onCollectionUpdated: () => void;
  onCollectionMissing: () => void;
}) {
  const {
    collection,
    isLoading: isDetailLoading,
    error: detailError,
    isNotFound,
    reload: reloadDetail,
  } = useCollectionDetail(collectionId);

  const [showDeleteConfirm, setShowDeleteConfirm] = useState(false);
  const [deletePending, setDeletePending] = useState(false);
  const [showEditModal, setShowEditModal] = useState(false);
  const [editName, setEditName] = useState("");
  const [editPending, setEditPending] = useState(false);
  const [editValidationError, setEditValidationError] = useState<string | null>(null);
  const [editServerError, setEditServerError] = useState<string | null>(null);
  const [unlinkTarget, setUnlinkTarget] = useState<{
    itemId: string;
    itemTitle: string;
    isLastItem: boolean;
  } | null>(null);
  const [unlinkPending, setUnlinkPending] = useState(false);
  const [quickAction, setQuickAction] = useState<{
    itemId: string;
    action: "unlink" | "status";
  } | null>(null);

  const detailReady = Boolean(collection) && !detailError;
  const {
    items,
    page,
    pageSize,
    total,
    totalPages,
    hasNext,
    hasPrevious,
    isLoading: isItemsLoading,
    error: itemsError,
    setPage,
    reload: reloadItems,
  } = useCollectionItemsReadData(collectionId, {
    enabled: detailReady,
    page: itemsPage,
    onPageChange: onItemsPageChange,
  });

  const detailVm = useMemo(
    () => (collection ? mapApiCollectionToDetail(collection) : null),
    [collection],
  );
  const listItems = useMemo(
    () => items.map(mapApiItemToItemsListViewModel),
    [items],
  );

  const rangeStart = total === 0 ? 0 : (page - 1) * pageSize + 1;
  const rangeEnd = Math.min(page * pageSize, total);
  const collectionBusy =
    Boolean(itemWriteBusy)
    || deletePending
    || editPending
    || showDeleteConfirm
    || showEditModal
    || unlinkPending
    || Boolean(unlinkTarget)
    || Boolean(quickAction);

  const reloadCollectionViews = useCallback(async () => {
    await Promise.all([reloadDetail(), reloadItems()]);
    onCollectionUpdated();
  }, [onCollectionUpdated, reloadDetail, reloadItems]);

  const openUnlinkConfirm = (item: { id: string; title: string }) => {
    if (collectionBusy) return;
    setUnlinkTarget({
      itemId: item.id,
      itemTitle: item.title,
      isLastItem: total <= 1,
    });
  };

  const handleUnlinkConfirm = async () => {
    if (!unlinkTarget || unlinkPending) return;
    setUnlinkPending(true);
    setQuickAction({ itemId: unlinkTarget.itemId, action: "unlink" });
    try {
      const updated = await updateItem(unlinkTarget.itemId, {
        collection_id: null,
      });
      if (updated.collection !== null) {
        showToast(itemUnlinkFailureToast());
        await reloadCollectionViews();
        return;
      }
      setUnlinkTarget(null);
      await reloadCollectionViews();
      showToast(itemUnlinkSuccessToast());
    } catch (err) {
      if (err instanceof ApiError && err.status === 404) {
        setUnlinkTarget(null);
        try {
          await getCollection(collectionId);
          await reloadCollectionViews();
        } catch (reloadErr) {
          if (reloadErr instanceof ApiError && reloadErr.status === 404) {
            onCollectionMissing();
          } else {
            await reloadCollectionViews();
          }
        }
        showToast(ITEM_NOT_FOUND_TOAST);
      } else if (err instanceof ApiError && err.status === 409) {
        setUnlinkTarget(null);
        await reloadCollectionViews();
        showToast(itemUnlinkChangedToast());
      } else if (err instanceof ApiError && err.status === 422) {
        showToast(itemUnlinkValidationToast());
      } else {
        showToast(itemUnlinkFailureToast());
      }
    } finally {
      setUnlinkPending(false);
      setQuickAction(null);
    }
  };

  const handleQuickStatusToggle = async (item: {
    id: string;
    status: ApiItemStatus;
  }) => {
    if (collectionBusy) return;
    const nextStatus: ApiItemStatus =
      item.status === "PLANNED" ? "COMPLETED" : "PLANNED";
    setQuickAction({ itemId: item.id, action: "status" });
    try {
      await updateItem(item.id, { status: nextStatus });
      await reloadCollectionViews();
      showToast(itemStatusSuccessToast(nextStatus));
    } catch (err) {
      if (err instanceof ApiError && err.status === 404) {
        await reloadCollectionViews();
        showToast(ITEM_NOT_FOUND_TOAST);
      } else if (err instanceof ApiError && err.status === 409) {
        await reloadCollectionViews();
        showToast(itemUnlinkChangedToast());
      } else if (err instanceof ApiError && err.status === 422) {
        showToast(itemStatusValidationToast());
      } else {
        showToast(itemStatusUpdateFailureToast());
      }
    } finally {
      setQuickAction(null);
    }
  };

  const handleCollectionDeleteClick = () => {
    if (!detailVm) return;
    if (detailVm.itemCount > 0) {
      showToast(
        "항목이 있는 컬렉션은 삭제할 수 없습니다. 컬렉션의 항목을 모두 삭제한 뒤 다시 시도해 주세요.",
      );
      return;
    }
    setShowDeleteConfirm(true);
  };

  const handleCollectionDeleteConfirm = async () => {
    if (deletePending) return;
    setDeletePending(true);
    try {
      await deleteCollection(collectionId);
      setShowDeleteConfirm(false);
      showToast("컬렉션을 삭제했습니다.");
      onCollectionDeleted();
    } catch (err) {
      showToast(collectionDeleteErrorMessage(err));
      if (err instanceof ApiError && err.status === 409) {
        setShowDeleteConfirm(false);
        void reloadDetail();
        void reloadItems();
      } else if (err instanceof ApiError && err.status === 404) {
        setShowDeleteConfirm(false);
        onCollectionDeleted();
      }
    } finally {
      setDeletePending(false);
    }
  };

  const openEditModal = () => {
    if (!detailVm || showDeleteConfirm || collectionBusy) return;
    setEditName(detailVm.name);
    setEditPending(false);
    setEditValidationError(null);
    setEditServerError(null);
    setShowEditModal(true);
  };

  const handleEditNameChange = (value: string) => {
    setEditName(value);
    setEditValidationError(null);
    if (editServerError) setEditServerError(null);
  };

  const currentCollectionName = detailVm?.name ?? "";
  const normalizedEditName = normalizeCollectionNameInput(editName);
  const editUnchanged = Boolean(detailVm) && normalizedEditName === currentCollectionName;

  const handleEditSubmit = async () => {
    if (!detailVm || editPending) return;
    const normalizedName = normalizeCollectionNameInput(editName);
    const validationMessage = validateCollectionName(normalizedName);
    if (validationMessage) {
      setEditValidationError(validationMessage);
      setEditServerError(null);
      return;
    }
    if (normalizedName === currentCollectionName) {
      setShowEditModal(false);
      return;
    }
    setEditPending(true);
    setEditValidationError(null);
    setEditServerError(null);
    try {
      await updateCollection(collectionId, { name: normalizedName });
      setShowEditModal(false);
      showToast("컬렉션 이름을 수정했습니다.");
      void reloadDetail();
      onCollectionUpdated();
    } catch (err) {
      if (err instanceof ApiError && err.status === 404) {
        setShowEditModal(false);
        showToast(collectionPatchNotFoundToast());
        onCollectionMissing();
      } else if (err instanceof ApiError && err.status === 409) {
        setEditServerError(collectionWriteConflictInline());
      } else if (err instanceof ApiError && err.status === 422) {
        setEditServerError(collectionWriteValidationInline());
      } else if (isCollectionWriteNetworkOrServerError(err)) {
        showToast(collectionUpdateFailureToast());
      } else {
        showToast(collectionUpdateFailureToast());
      }
    } finally {
      setEditPending(false);
    }
  };

  if (isDetailLoading && !detailVm) {
    return (
      <div className="max-w-3xl mx-auto px-4 sm:px-6 py-6">
        <button
          type="button"
          onClick={onBack}
          aria-label="Collection 목록으로"
          className="flex items-center gap-1 text-sm text-muted-foreground hover:text-foreground mb-5"
        >
          <ChevronLeft size={16}/> Collection 목록
        </button>
        <div className="bg-card border border-border rounded-2xl p-6 mb-5 space-y-3">
          <div className="h-4 w-32 animate-pulse rounded bg-muted"/>
          <div className="h-8 w-2/3 animate-pulse rounded bg-muted"/>
          <div className="h-3 w-full animate-pulse rounded bg-muted"/>
        </div>
        <div className="bg-card border border-border rounded-2xl py-12 text-center text-sm text-muted-foreground">
          Collection을 불러오는 중…
        </div>
      </div>
    );
  }

  if (detailError || !detailVm) {
    return (
      <div className="max-w-3xl mx-auto px-4 sm:px-6 py-6">
        <button
          type="button"
          onClick={onBack}
          aria-label="Collection 목록으로"
          className="flex items-center gap-1 text-sm text-muted-foreground hover:text-foreground mb-5"
        >
          <ChevronLeft size={16}/> Collection 목록
        </button>
        <div className="bg-card border border-border rounded-2xl p-8 text-center">
          <p className="font-medium text-foreground mb-2">
            {isNotFound
              ? "Collection을 찾을 수 없습니다."
              : "Collection 정보를 불러오지 못했습니다."}
          </p>
          {isNotFound && (
            <p className="text-sm text-muted-foreground mb-5">
              삭제되었거나 접근할 수 없는 Collection입니다.
            </p>
          )}
          <div className="flex flex-wrap gap-2 justify-center">
            {!isNotFound && (
              <button
                type="button"
                onClick={() => void reloadDetail()}
                className="inline-flex items-center gap-1.5 text-sm bg-primary text-white px-4 py-2 rounded-xl hover:bg-blue-700 transition-colors font-medium"
              >
                <RefreshCw size={14}/> 다시 시도
              </button>
            )}
            <button
              type="button"
              onClick={onBack}
              className="inline-flex items-center gap-1.5 text-sm border border-border text-foreground px-4 py-2 rounded-xl hover:bg-muted transition-colors font-medium"
            >
              목록으로 돌아가기
            </button>
          </div>
        </div>
      </div>
    );
  }

  return (
    <div className="max-w-3xl mx-auto px-4 sm:px-6 py-6">
      <button
        type="button"
        onClick={onBack}
        aria-label="Collection 목록으로"
        className="flex items-center gap-1 text-sm text-muted-foreground hover:text-foreground mb-5"
      >
        <ChevronLeft size={16}/> Collection 목록
      </button>

      <div className="bg-card border border-border rounded-2xl p-6 mb-5">
        <div className="flex items-start justify-between gap-3">
          <div className="min-w-0">
            <div className="flex items-center gap-2 mb-1.5 flex-wrap">
              <CollectionCategoryBadges categories={detailVm.categories}/>
              <span className="text-[10px] bg-purple-100 text-purple-700 px-2 py-px rounded">Collection</span>
            </div>
            <h1 className="text-2xl font-bold text-foreground break-words">{detailVm.name}</h1>
            <p className="text-sm text-muted-foreground mt-0.5">{detailVm.itemCount}개 항목</p>
          </div>
          <div className="flex gap-2 flex-shrink-0">
            <button
              type="button"
              onClick={() => showToast("추천 API는 아직 연결되지 않았습니다.")}
              className="p-2 border border-border rounded-xl text-muted-foreground hover:text-foreground hover:bg-muted transition-colors"
              title="이 Collection에서 추천"
            >
              <Shuffle size={15}/>
            </button>
            <button
              type="button"
              onClick={openEditModal}
              disabled={collectionBusy}
              className="p-2 border border-border rounded-xl text-muted-foreground hover:text-foreground hover:bg-muted transition-colors disabled:opacity-50"
              title="수정"
            >
              <Edit2 size={15}/>
            </button>
            <button
              type="button"
              onClick={handleCollectionDeleteClick}
              disabled={collectionBusy}
              className="p-2 border border-red-200 rounded-xl text-red-500 hover:bg-red-50 transition-colors disabled:opacity-50"
              title="삭제"
            >
              <Trash2 size={15}/>
            </button>
          </div>
        </div>
        <div className="mt-4">
          <div className="flex justify-between text-xs mb-1">
            <span className="text-muted-foreground">진행률</span>
            <span className="font-semibold">{detailVm.progressPercent}%</span>
          </div>
          <ProgressBar value={detailVm.progressPercent}/>
          <div className="flex gap-4 mt-2 text-xs">
            <span className="text-blue-600">예정 {detailVm.plannedCount}</span>
            <span className="text-emerald-600">완료 {detailVm.completedCount}</span>
            <span className="flex items-center gap-0.5 text-muted-foreground">
              <Star size={10}/>—
            </span>
          </div>
        </div>
      </div>

      <div className="flex items-center justify-between mb-3">
        <h2 className="text-sm font-semibold text-foreground">항목 목록</h2>
        <div className="flex gap-2">
          <button
            type="button"
            onClick={onNavigateToSearch}
            className="text-xs text-primary border border-primary/25 px-3 py-1.5 rounded-lg hover:bg-blue-50 transition-colors flex items-center gap-1"
          >
            <Search size={12}/> TMDB 검색 후 추가
          </button>
          <button
            type="button"
            disabled={collectionBusy}
            onClick={() => {
              if (!collection) return;
              openAddItem({
                origin: "collections",
                lockedCollection: { id: collection.id, name: collection.name },
                collectionItemsPage: page,
              });
            }}
            className="text-xs text-primary border border-primary/25 px-3 py-1.5 rounded-lg hover:bg-blue-50 transition-colors flex items-center gap-1 disabled:opacity-50 disabled:cursor-not-allowed"
          >
            <Plus size={12}/> 직접 추가
          </button>
        </div>
      </div>

      {itemsError ? (
        <div className="bg-card border border-border rounded-2xl p-8 text-center">
          <p className="text-sm text-foreground mb-1">소속 Item을 불러오지 못했습니다.</p>
          <p className="text-xs text-muted-foreground mb-4">Collection 정보는 유지됩니다.</p>
          <button
            type="button"
            onClick={() => void reloadItems()}
            className="inline-flex items-center gap-1.5 text-sm text-primary border border-primary/25 px-4 py-2 rounded-xl hover:bg-blue-50 transition-colors"
          >
            <RefreshCw size={14}/> 다시 시도
          </button>
        </div>
      ) : isItemsLoading && listItems.length === 0 ? (
        <div className="bg-card border border-border rounded-2xl py-10 text-center text-sm text-muted-foreground">
          항목을 불러오는 중…
        </div>
      ) : total === 0 ? (
        <div className="bg-card border border-border rounded-2xl py-10 text-center text-sm text-muted-foreground">
          이 Collection에 등록된 항목이 없습니다.
        </div>
      ) : (
        <>
          <div className={`space-y-2 ${isItemsLoading ? "opacity-70" : ""}`}>
            {listItems.map((item) => {
              const Icon = item.presentation.icon;
              return (
                <div
                  key={item.id}
                  role="button"
                  tabIndex={0}
                  aria-label={`${item.title} 상세 보기`}
                  onClick={() =>
                    openItemDetail(item.id, {
                      collectionId,
                      collectionItemsPage: page,
                    })
                  }
                  onKeyDown={(e) => {
                    if (e.key === "Enter" || e.key === " ") {
                      e.preventDefault();
                      openItemDetail(item.id, {
                        collectionId,
                        collectionItemsPage: page,
                      });
                    }
                  }}
                  className="bg-card border border-border rounded-xl p-4 flex items-center gap-3 hover:border-primary/20 transition-colors cursor-pointer"
                >
                  <div
                    className="w-10 h-14 text-base rounded-lg flex items-center justify-center flex-shrink-0 text-white font-bold"
                    style={{ backgroundColor: item.presentation.color }}
                  >
                    {item.title.charAt(0)}
                  </div>
                  <div className="flex-1 min-w-0">
                    <div className="font-medium text-foreground text-sm truncate">{item.title}</div>
                    <div className="flex flex-wrap items-center gap-1.5 mt-1">
                      <span
                        className="inline-flex items-center gap-1 rounded font-medium text-[10px] px-1.5 py-px"
                        style={{
                          backgroundColor: item.presentation.bgColor,
                          color: item.presentation.color,
                        }}
                      >
                        <Icon size={10}/>{item.categoryName}
                      </span>
                      <StatusBadge status={item.status} sm/>
                      {item.progressNote && (
                        <span className="text-[10px] text-muted-foreground truncate max-w-[140px]">
                          {item.progressNote}
                        </span>
                      )}
                    </div>
                    <div className="mt-0.5">
                      <StarRating rating={displayItemRating(item.rating)} sm/>
                    </div>
                  </div>
                  <div className="flex gap-1.5 flex-shrink-0" onClick={(e) => e.stopPropagation()}>
                    <button
                      type="button"
                      disabled={collectionBusy}
                      onClick={() => void handleQuickStatusToggle({
                        id: item.id,
                        status: item.status,
                      })}
                      className="text-[10px] border border-emerald-200 text-emerald-700 px-2 py-1 rounded-lg hover:bg-emerald-50 transition-colors disabled:opacity-50 disabled:cursor-not-allowed"
                    >
                      {quickAction?.itemId === item.id && quickAction.action === "status"
                        ? "변경 중..."
                        : item.status === "PLANNED"
                          ? "완료"
                          : "예정"}
                    </button>
                    <button
                      type="button"
                      disabled={collectionBusy}
                      onClick={() => openUnlinkConfirm({ id: item.id, title: item.title })}
                      className="text-[10px] border border-border text-muted-foreground px-2 py-1 rounded-lg hover:bg-muted transition-colors disabled:opacity-50 disabled:cursor-not-allowed"
                    >
                      {quickAction?.itemId === item.id && quickAction.action === "unlink"
                        ? "제거 중..."
                        : "제거"}
                    </button>
                  </div>
                </div>
              );
            })}
          </div>

          {totalPages > 1 && (
            <div className="flex items-center justify-between mt-5">
              <p className="text-xs text-muted-foreground">
                {rangeStart}–{rangeEnd} / {total.toLocaleString("ko-KR")}건
                {totalPages > 0 ? ` · ${page}/${totalPages}페이지` : ""}
              </p>
              <div className="flex items-center gap-1">
                <button
                  type="button"
                  onClick={() => setPage(1)}
                  disabled={!hasPrevious}
                  aria-label="첫 페이지"
                  className="p-1.5 rounded-lg border border-border text-muted-foreground hover:text-foreground disabled:opacity-30 transition-colors"
                >
                  <ChevronsLeft size={14}/>
                </button>
                <button
                  type="button"
                  onClick={() => setPage(page - 1)}
                  disabled={!hasPrevious}
                  aria-label="이전 페이지"
                  className="p-1.5 rounded-lg border border-border text-muted-foreground hover:text-foreground disabled:opacity-30 transition-colors"
                >
                  <ChevronLeft size={14}/>
                </button>
                {Array.from({ length: Math.min(5, totalPages) }, (_, i) => {
                  const p = Math.min(Math.max(page - 2, 1) + i, totalPages);
                  return (
                    <button
                      key={`${p}-${i}`}
                      type="button"
                      onClick={() => setPage(p)}
                      aria-label={`${p}페이지`}
                      aria-current={page === p ? "page" : undefined}
                      className={`w-7 h-7 rounded-lg text-xs font-medium border transition-colors ${page === p ? "border-primary bg-primary text-white" : "border-border text-foreground hover:bg-muted"}`}
                    >
                      {p}
                    </button>
                  );
                })}
                <button
                  type="button"
                  onClick={() => setPage(page + 1)}
                  disabled={!hasNext}
                  aria-label="다음 페이지"
                  className="p-1.5 rounded-lg border border-border text-muted-foreground hover:text-foreground disabled:opacity-30 transition-colors"
                >
                  <ChevronRight size={14}/>
                </button>
                <button
                  type="button"
                  onClick={() => setPage(totalPages)}
                  disabled={!hasNext}
                  aria-label="마지막 페이지"
                  className="p-1.5 rounded-lg border border-border text-muted-foreground hover:text-foreground disabled:opacity-30 transition-colors"
                >
                  <ChevronsRight size={14}/>
                </button>
              </div>
            </div>
          )}
        </>
      )}

      {showDeleteConfirm && detailVm && (
        <ConfirmModal
          title="컬렉션 삭제"
          body={`"${detailVm.name}" 컬렉션을 삭제합니다.\n삭제된 컬렉션은 복구할 수 없습니다.`}
          danger
          confirmLabel="삭제"
          pending={deletePending}
          onConfirm={() => void handleCollectionDeleteConfirm()}
          onClose={() => {
            if (!deletePending) setShowDeleteConfirm(false);
          }}
        />
      )}

      {unlinkTarget && (
        <ConfirmModal
          title="컬렉션에서 항목 제거"
          body={buildCollectionUnlinkConfirmBody(unlinkTarget.itemTitle, {
            isLastItem: unlinkTarget.isLastItem,
          })}
          confirmLabel="제거"
          pending={unlinkPending}
          pendingLabel="제거 중..."
          onConfirm={() => void handleUnlinkConfirm()}
          onClose={() => {
            if (!unlinkPending) setUnlinkTarget(null);
          }}
        />
      )}

      <CollectionFormModal
        open={showEditModal}
        mode="edit"
        name={editName}
        pending={editPending}
        validationError={editValidationError}
        serverError={editServerError}
        submitDisabled={editUnchanged}
        onNameChange={handleEditNameChange}
        onSubmit={() => void handleEditSubmit()}
        onClose={() => {
          if (!editPending) setShowEditModal(false);
        }}
      />
    </div>
  );
}

// ─── Settings Page ────────────────────────────────────────────────────────────

function SettingsPage({ setPage }: { setPage: (p: Page) => void }) {
  return (
    <div className="max-w-xl mx-auto px-4 sm:px-6 py-6 space-y-4">
      <h1 className="text-xl font-bold text-foreground mb-5">설정</h1>
      <div className="bg-card border border-border rounded-2xl overflow-hidden">
        <button onClick={() => setPage("category-manage")}
          className="w-full flex items-center justify-between px-5 py-4 hover:bg-muted/40 transition-colors text-left">
          <div className="flex items-center gap-3">
            <Palette size={16} className="text-muted-foreground flex-shrink-0"/>
            <div>
              <div className="text-sm font-medium text-foreground">Category 보기</div>
              <p className="text-xs text-muted-foreground mt-0.5">
                현재 사용 중인 Category와 항목 수를 확인합니다.
              </p>
            </div>
          </div>
          <ChevronRight size={14} className="text-muted-foreground flex-shrink-0"/>
        </button>
      </div>
    </div>
  );
}

// ─── App ──────────────────────────────────────────────────────────────────────

interface ItemDetailSelection {
  itemId: string;
  origin: ItemDetailOrigin;
  collectionId?: string;
  collectionItemsPage?: number;
}

export default function App() {
  const [page, setPage]               = useState<Page>("home");
  const [itemDetailSelection, setItemDetailSelection] =
    useState<ItemDetailSelection | null>(null);
  const [itemsSnapshot, setItemsSnapshot] =
    useState<ItemsPageStateSnapshot | null>(null);
  const [collectionsSnapshot, setCollectionsSnapshot] =
    useState<CollectionsQuerySnapshot | null>(null);
  const [searchSnapshot, setSearchSnapshot] =
    useState<SearchPageSnapshot | null>(null);
  const [collectionDetailSelection, setCollectionDetailSelection] =
    useState<CollectionDetailSelection | null>(null);
  const [toast, setToast]                     = useState<string | null>(null);
  const [itemFormSession, setItemFormSession] = useState<ItemFormSession | null>(null);
  const [itemWriteBusy, setItemWriteBusy] = useState(false);
  const [itemDetailNonce, setItemDetailNonce] = useState(0);

  const showToast = useCallback((msg: string) => {
    setToast(msg);
    setTimeout(() => setToast(null), 2800);
  }, []);

  useEffect(() => {
    if (HIDDEN_PAGES.has(page)) {
      setPage("home");
    }
  }, [page]);

  const openItemDetail = useCallback((
    itemId: string,
    origin: ItemDetailOrigin,
    extras?: { collectionId?: string; collectionItemsPage?: number },
  ) => {
    setItemDetailSelection({
      itemId,
      origin,
      collectionId: extras?.collectionId,
      collectionItemsPage: extras?.collectionItemsPage,
    });
    setPage("item-detail");
  }, []);

  const closeItemForm = useCallback(() => {
    if (itemWriteBusy) return;
    setItemFormSession(null);
  }, [itemWriteBusy]);

  const openCreateItem = useCallback((
    options?: {
      origin?: ItemDetailOrigin;
      categoryId?: string | null;
      collectionId?: string | null;
      lockedCollection?: { id: string; name: string };
      collectionItemsPage?: number;
    },
  ) => {
    if (itemWriteBusy || itemFormSession) return;
    const origin = options?.origin
      ?? (page === "home" || page === "items" || page === "collections"
        ? page
        : "items");
    setItemFormSession({
      mode: "create",
      origin,
      initialCategoryId: options?.categoryId ?? null,
      initialCollectionId: options?.collectionId ?? null,
      lockedCollection: options?.lockedCollection,
      collectionItemsPage: options?.collectionItemsPage,
    });
  }, [itemFormSession, itemWriteBusy, page]);

  const openEditItem = useCallback((item: ApiItemDetail) => {
    if (itemWriteBusy || itemFormSession) return;
    const selection = itemDetailSelection;
    setItemFormSession({
      mode: "edit",
      item,
      origin: selection?.origin ?? "items",
      collectionId: selection?.collectionId,
      collectionItemsPage: selection?.collectionItemsPage,
    });
  }, [itemDetailSelection, itemFormSession, itemWriteBusy]);

  const handleItemCreated = useCallback(async (
    created: ApiItemDetail,
    session: Extract<ItemFormSession, { mode: "create" }>,
  ) => {
    setItemFormSession(null);
    if (session.origin === "collections" && session.lockedCollection) {
      setCollectionDetailSelection({
        collectionId: session.lockedCollection.id,
        itemsPage: session.collectionItemsPage ?? 1,
      });
      openItemDetail(created.id, "collections", {
        collectionId: session.lockedCollection.id,
        collectionItemsPage: session.collectionItemsPage ?? 1,
      });
    } else {
      openItemDetail(created.id, session.origin);
    }
    showToast("항목을 추가했습니다.");
  }, [openItemDetail, showToast]);

  const handleItemUpdated = useCallback(async (
    updated: ApiItemDetail,
    session: Extract<ItemFormSession, { mode: "edit" }>,
  ) => {
    setItemFormSession(null);
    setItemDetailSelection((prev) => (
      prev
        ? {
            ...prev,
            itemId: updated.id,
            origin: session.origin,
            collectionId: session.collectionId,
            collectionItemsPage: session.collectionItemsPage,
          }
        : {
            itemId: updated.id,
            origin: session.origin,
            collectionId: session.collectionId,
            collectionItemsPage: session.collectionItemsPage,
          }
    ));
    setPage("item-detail");
    setItemDetailNonce((value) => value + 1);
    showToast("항목을 수정했습니다.");
  }, [showToast]);

  const handleLockedCollectionMissing = useCallback(async () => {
    setItemFormSession(null);
    setCollectionDetailSelection(null);
    setPage("collections");
    showToast(ITEM_COLLECTION_NOT_FOUND_TOAST);
  }, [showToast]);

  const closeItemDetail = useCallback(() => {
    const selection = itemDetailSelection;
    if (selection?.origin === "collections" && selection.collectionId) {
      setCollectionDetailSelection({
        collectionId: selection.collectionId,
        itemsPage: selection.collectionItemsPage ?? 1,
      });
      setPage("collections");
      setItemDetailSelection(null);
      return;
    }
    if (selection?.origin === "search") {
      setPage("search");
      setItemDetailSelection(null);
      return;
    }
    const destination = selection?.origin ?? "items";
    setPage(destination === "collections" ? "collections" : destination);
    setItemDetailSelection(null);
  }, [itemDetailSelection]);

  const handleItemDeleteSuccess = useCallback(async (context: {
    origin: ItemDetailOrigin;
    collectionId?: string;
    collectionItemsPage?: number;
    deletedItem: ApiItemDetail;
  }) => {
    setSearchSnapshot((prev) =>
      unmarkDeletedItemInSearchSnapshot(prev, context.deletedItem),
    );

    if (context.origin === "collections" && context.collectionId) {
      try {
        await getCollection(context.collectionId);
        setCollectionDetailSelection({
          collectionId: context.collectionId,
          itemsPage: context.collectionItemsPage ?? 1,
        });
        setPage("collections");
        setItemDetailSelection(null);
        showToast("항목을 삭제했습니다.");
      } catch (err) {
        setItemDetailSelection(null);
        setPage("collections");
        if (err instanceof ApiError && err.status === 404) {
          setCollectionDetailSelection(null);
          showToast("항목과 빈 컬렉션을 삭제했습니다.");
        } else {
          setCollectionDetailSelection(null);
          showToast("항목은 삭제했지만 컬렉션 상태를 새로 불러오지 못했습니다.");
        }
      }
      return;
    }

    if (context.origin === "home") {
      setPage("home");
      setItemDetailSelection(null);
      showToast("항목을 삭제했습니다.");
      return;
    }

    if (context.origin === "search") {
      setPage("search");
      setItemDetailSelection(null);
      showToast("항목을 삭제했습니다.");
      return;
    }

    setPage("items");
    setItemDetailSelection(null);
    showToast("항목을 삭제했습니다.");
  }, [showToast]);

  const handleEditItemMissing = useCallback(async (
    session: Extract<ItemFormSession, { mode: "edit" }>,
  ) => {
    setItemFormSession(null);
    setItemDetailSelection(null);
    if (session.origin === "collections" && session.collectionId) {
      try {
        await getCollection(session.collectionId);
        setCollectionDetailSelection({
          collectionId: session.collectionId,
          itemsPage: session.collectionItemsPage ?? 1,
        });
        setPage("collections");
      } catch {
        setCollectionDetailSelection(null);
        setPage("collections");
      }
    } else if (session.origin === "home") {
      setPage("home");
    } else if (session.origin === "search") {
      setPage("search");
    } else {
      setPage("items");
    }
    showToast(ITEM_NOT_FOUND_TOAST);
  }, [showToast]);

  const navigateFromLayout = useCallback((next: Page) => {
    if (HIDDEN_PAGES.has(next)) {
      setPage("home");
      return;
    }
    if (next !== "item-detail") {
      setItemDetailSelection(null);
    }
    if (next !== "collections") {
      setCollectionDetailSelection(null);
    }
    setPage(next);
  }, []);

  const renderPage = () => {
    switch (page) {
      case "home":
        return (
          <HomePage
            setPage={setPage}
            openAddItem={() => openCreateItem({ origin: "home" })}
            openItemDetail={(id) => openItemDetail(id, "home")}
          />
        );
      case "search":
        return (
          <SearchPage
            showToast={showToast}
            openItemDetail={(id) => openItemDetail(id, "search")}
            initialSnapshot={searchSnapshot}
            onSnapshotChange={setSearchSnapshot}
          />
        );
      case "recommend":
      case "history":
      case "history-detail":
      case "data":
        return null;
      case "items":
        return (
          <ItemsPage
            showToast={showToast}
            openAddItem={(opts) =>
              openCreateItem({
                origin: "items",
                categoryId: opts?.categoryId,
              })
            }
            openItemDetail={(id) => openItemDetail(id, "items")}
            initialSnapshot={itemsSnapshot}
            onSnapshotChange={setItemsSnapshot}
          />
        );
      case "collections":
        return (
          <CollectionsPage
            showToast={showToast}
            initialSnapshot={collectionsSnapshot}
            onSnapshotChange={setCollectionsSnapshot}
            selection={collectionDetailSelection}
            onSelectionChange={setCollectionDetailSelection}
            openItemDetail={(itemId, context) =>
              openItemDetail(itemId, "collections", context)
            }
            openAddItem={(opts) => openCreateItem(opts)}
            onNavigateToSearch={() => setPage("search")}
            itemWriteBusy={itemWriteBusy || Boolean(itemFormSession)}
          />
        );
      case "settings":       return <SettingsPage setPage={setPage}/>;
      case "item-detail":
        return (
          <ItemDetailPage
            key={`${itemDetailSelection?.itemId ?? "none"}-${itemDetailNonce}`}
            itemId={itemDetailSelection?.itemId ?? null}
            onBack={closeItemDetail}
            showToast={showToast}
            origin={itemDetailSelection?.origin ?? "items"}
            collectionId={itemDetailSelection?.collectionId}
            collectionItemsPage={itemDetailSelection?.collectionItemsPage}
            onDeleteSuccess={handleItemDeleteSuccess}
            onEdit={openEditItem}
            writeBusy={itemWriteBusy || Boolean(itemFormSession)}
            backLabel={
              itemDetailSelection?.origin === "collections"
                ? "Collection으로"
                : "목록으로"
            }
          />
        );
      case "category-manage":return <CategoryManagePage onBack={() => setPage("settings")}/>;
    }
  };

  return (
    <div className="flex h-screen bg-background overflow-hidden">
      <AppLayout currentPage={page} onNavigate={navigateFromLayout} onAddItem={() => openCreateItem()}>
        {renderPage()}
      </AppLayout>

      {itemFormSession && (
        <ItemFormModal
          key={
            itemFormSession.mode === "edit"
              ? `edit-${itemFormSession.item.id}`
              : `create-${itemFormSession.origin}-${itemFormSession.lockedCollection?.id ?? "none"}`
          }
          session={itemFormSession}
          busy={itemWriteBusy}
          onBusyChange={setItemWriteBusy}
          onClose={closeItemForm}
          onCreated={handleItemCreated}
          onUpdated={handleItemUpdated}
          onItemMissing={handleEditItemMissing}
          onLockedCollectionMissing={handleLockedCollectionMissing}
          showToast={showToast}
        />
      )}

      {/* Global toast */}
      {toast && <Toast msg={toast}/>}
      <PwaUpdatePrompt />
    </div>
  );
}
