import { useCallback, useEffect, useRef, useState } from "react";
import type { FormEvent } from "react";
import { X } from "lucide-react";
import {
  getAllCollectionsForSelect,
  getCategories,
} from "../../api/catalog";
import {
  createItemFromTmdb,
  tmdbAlreadyExistsItemId,
} from "../../api/tmdb";
import {
  tmdbAlreadyRegisteredToast,
  tmdbErrorMessage,
  tmdbRegisterSuccessToast,
} from "../../api/tmdbMessages";
import {
  ITEM_CATEGORY_EMPTY_LIST_ERROR,
  RATING_OPTIONS,
  collectItemFormFieldErrors,
  hasItemFormFieldErrors,
  isItemWriteNetworkOrServerError,
  normalizeNullableText,
  type ItemFormFieldErrors,
  type ItemFormValues,
} from "../../api/itemWriteMessages";
import { ApiError } from "../../api/client";
import type { ApiCategory, ApiCollection, ApiItemDetail } from "../../types/api";
import type { TmdbDetailResponse, TmdbMediaType } from "../../types/tmdb";
import { getCategoryPresentation } from "../presentation/categoryPresentation";

function emptyValues(title: string): ItemFormValues {
  return {
    title,
    categoryId: "",
    collectionId: null,
    status: "PLANNED",
    rating: 0,
    progressNote: "",
    memo: "",
  };
}

export function TmdbRegisterForm({
  detail,
  mediaType,
  tmdbId,
  onClose,
  onRegistered,
  onAlreadyExists,
  showToast,
}: {
  detail: TmdbDetailResponse;
  mediaType: TmdbMediaType;
  tmdbId: number;
  onClose: () => void;
  onRegistered: (item: ApiItemDetail) => void;
  onAlreadyExists: (itemId: string) => void;
  showToast: (message: string) => void;
}) {
  const [values, setValues] = useState<ItemFormValues>(() =>
    emptyValues(detail.title),
  );
  const [categories, setCategories] = useState<ApiCategory[]>([]);
  const [collections, setCollections] = useState<ApiCollection[]>([]);
  const [optionsLoading, setOptionsLoading] = useState(true);
  const [optionsError, setOptionsError] = useState<string | null>(null);
  const [fieldErrors, setFieldErrors] = useState<ItemFormFieldErrors>({});
  const [serverError, setServerError] = useState<string | null>(null);
  const [pending, setPending] = useState(false);
  const titleRef = useRef<HTMLInputElement>(null);

  const reloadOptions = useCallback(async () => {
    setOptionsLoading(true);
    setOptionsError(null);
    try {
      const [categoriesResponse, collectionRows] = await Promise.all([
        getCategories(),
        getAllCollectionsForSelect(),
      ]);
      setCategories(categoriesResponse.categories);
      setCollections(collectionRows);
      if (categoriesResponse.categories.length === 0) {
        setOptionsError(ITEM_CATEGORY_EMPTY_LIST_ERROR);
      }
    } catch {
      setOptionsError("카테고리·컬렉션을 불러오지 못했습니다.");
    } finally {
      setOptionsLoading(false);
    }
  }, []);

  useEffect(() => {
    void reloadOptions();
  }, [reloadOptions]);

  useEffect(() => {
    const timer = window.setTimeout(() => titleRef.current?.focus(), 0);
    return () => window.clearTimeout(timer);
  }, []);

  useEffect(() => {
    if (pending) return undefined;
    const onKeyDown = (event: KeyboardEvent) => {
      if (event.key === "Escape") onClose();
    };
    window.addEventListener("keydown", onKeyDown);
    return () => window.removeEventListener("keydown", onKeyDown);
  }, [pending, onClose]);

  const onSubmit = async (event: FormEvent) => {
    event.preventDefault();
    if (pending || optionsLoading) return;

    const errors = collectItemFormFieldErrors(values, {
      requireCategory: true,
      categoriesEmpty: categories.length === 0,
    });
    setFieldErrors(errors);
    setServerError(null);
    if (hasItemFormFieldErrors(errors)) return;

    setPending(true);
    try {
      const title = values.title.trim();
      const payload = {
        media_type: mediaType,
        tmdb_id: tmdbId,
        category_id: values.categoryId,
        collection_id: values.collectionId,
        status: values.status,
        rating: values.rating,
        progress_note: normalizeNullableText(values.progressNote),
        memo: normalizeNullableText(values.memo),
        title: title === detail.title ? undefined : title,
      };
      const created = await createItemFromTmdb(payload);
      showToast(tmdbRegisterSuccessToast());
      onRegistered(created);
    } catch (err) {
      const existingId = tmdbAlreadyExistsItemId(err);
      if (existingId) {
        showToast(tmdbAlreadyRegisteredToast());
        onAlreadyExists(existingId);
        return;
      }
      if (err instanceof ApiError && err.status === 404) {
        setServerError("선택한 카테고리 또는 컬렉션을 찾을 수 없습니다.");
      } else if (err instanceof ApiError && err.status === 422) {
        setServerError("입력한 항목 정보를 확인해 주세요.");
      } else if (isItemWriteNetworkOrServerError(err)) {
        showToast(tmdbErrorMessage(err, "항목을 추가하지 못했습니다."));
      } else {
        setServerError(tmdbErrorMessage(err, "항목을 추가하지 못했습니다."));
      }
    } finally {
      setPending(false);
    }
  };

  const formError = fieldErrors.form ?? serverError ?? optionsError;

  return (
    <div
      className="fixed inset-0 bg-black/50 z-[60] flex items-end sm:items-center justify-center p-0 sm:p-4"
      role="dialog"
      aria-modal="true"
      aria-labelledby="tmdb-register-title"
      onClick={() => {
        if (!pending) onClose();
      }}
    >
      <div
        className="bg-card w-full sm:max-w-lg sm:rounded-2xl rounded-t-2xl shadow-2xl max-h-[min(92vh,calc(100dvh-1rem))] overflow-y-auto"
        onClick={(event) => event.stopPropagation()}
      >
        <div className="sticky top-0 bg-card border-b border-border px-5 py-4 flex items-center justify-between z-10">
          <div>
            <h2 id="tmdb-register-title" className="text-base font-bold text-foreground">
              항목으로 등록
            </h2>
            <p className="text-xs text-muted-foreground mt-0.5">
              TMDB {mediaType.toUpperCase()} · #{tmdbId}
            </p>
          </div>
          <button
            type="button"
            onClick={onClose}
            disabled={pending}
            className="p-2 rounded-xl text-muted-foreground hover:bg-muted disabled:opacity-50"
            aria-label="닫기"
          >
            <X size={18} />
          </button>
        </div>

        <form onSubmit={(event) => void onSubmit(event)} className="px-5 py-4 space-y-4">
          <div>
            <label className="block text-xs font-medium text-muted-foreground mb-1.5">
              제목
            </label>
            <input
              ref={titleRef}
              value={values.title}
              onChange={(event) =>
                setValues((prev) => ({ ...prev, title: event.target.value }))
              }
              disabled={pending}
              className="w-full border border-border rounded-xl px-3 py-2.5 text-sm bg-background"
            />
            {fieldErrors.title ? (
              <p className="text-xs text-red-500 mt-1">{fieldErrors.title}</p>
            ) : null}
          </div>

          <div>
            <div className="text-xs font-medium text-muted-foreground mb-1.5">카테고리</div>
            {optionsLoading ? (
              <p className="text-sm text-muted-foreground">불러오는 중...</p>
            ) : (
              <div className="flex flex-wrap gap-2">
                {categories.map((cat) => {
                  const presentation = getCategoryPresentation(cat.name);
                  const Icon = presentation.icon;
                  const selected = values.categoryId === cat.id;
                  return (
                    <button
                      key={cat.id}
                      type="button"
                      disabled={pending}
                      onClick={() =>
                        setValues((prev) => ({ ...prev, categoryId: cat.id }))
                      }
                      className={`inline-flex items-center gap-1.5 px-3 py-1.5 rounded-xl text-xs font-medium border transition-colors ${
                        selected
                          ? "border-primary bg-blue-50 text-primary"
                          : "border-border text-foreground hover:bg-muted"
                      }`}
                    >
                      <Icon size={12} style={{ color: presentation.color }} />
                      {cat.name}
                    </button>
                  );
                })}
              </div>
            )}
            {fieldErrors.categoryId ? (
              <p className="text-xs text-red-500 mt-1">{fieldErrors.categoryId}</p>
            ) : null}
          </div>

          <div className="grid grid-cols-2 gap-3">
            <div>
              <div className="text-xs font-medium text-muted-foreground mb-1.5">상태</div>
              <div className="flex gap-2">
                {(["PLANNED", "COMPLETED"] as const).map((status) => (
                  <button
                    key={status}
                    type="button"
                    disabled={pending}
                    onClick={() => setValues((prev) => ({ ...prev, status }))}
                    className={`flex-1 py-2 rounded-xl text-xs font-medium border ${
                      values.status === status
                        ? "border-primary bg-blue-50 text-primary"
                        : "border-border text-muted-foreground"
                    }`}
                  >
                    {status === "PLANNED" ? "볼 예정" : "완료"}
                  </button>
                ))}
              </div>
            </div>
            <div>
              <label className="block text-xs font-medium text-muted-foreground mb-1.5">
                평점
              </label>
              <select
                value={values.rating}
                disabled={pending}
                onChange={(event) =>
                  setValues((prev) => ({
                    ...prev,
                    rating: Number(event.target.value),
                  }))
                }
                className="w-full border border-border rounded-xl px-3 py-2 text-sm bg-background"
              >
                {RATING_OPTIONS.map((rating) => (
                  <option key={rating} value={rating}>
                    {rating === 0 ? "미평가" : rating.toFixed(1)}
                  </option>
                ))}
              </select>
            </div>
          </div>

          <div>
            <label className="block text-xs font-medium text-muted-foreground mb-1.5">
              컬렉션 (선택)
            </label>
            <select
              value={values.collectionId ?? ""}
              disabled={pending || optionsLoading}
              onChange={(event) =>
                setValues((prev) => ({
                  ...prev,
                  collectionId: event.target.value || null,
                }))
              }
              className="w-full border border-border rounded-xl px-3 py-2.5 text-sm bg-background"
            >
              <option value="">없음</option>
              {collections.map((collection) => (
                <option key={collection.id} value={collection.id}>
                  {collection.name}
                </option>
              ))}
            </select>
          </div>

          <div>
            <label className="block text-xs font-medium text-muted-foreground mb-1.5">
              진행 상황
            </label>
            <input
              value={values.progressNote}
              disabled={pending}
              maxLength={200}
              onChange={(event) =>
                setValues((prev) => ({
                  ...prev,
                  progressNote: event.target.value,
                }))
              }
              className="w-full border border-border rounded-xl px-3 py-2.5 text-sm bg-background"
              placeholder="예: 2화까지 시청"
            />
            {fieldErrors.progressNote ? (
              <p className="text-xs text-red-500 mt-1">{fieldErrors.progressNote}</p>
            ) : null}
          </div>

          <div>
            <label className="block text-xs font-medium text-muted-foreground mb-1.5">
              메모
            </label>
            <textarea
              value={values.memo}
              disabled={pending}
              rows={3}
              onChange={(event) =>
                setValues((prev) => ({ ...prev, memo: event.target.value }))
              }
              className="w-full border border-border rounded-xl px-3 py-2.5 text-sm bg-background resize-y"
            />
          </div>

          {formError ? (
            <p className="text-sm text-red-500">{formError}</p>
          ) : null}

          <div className="flex gap-3 pt-1 pb-2">
            <button
              type="button"
              onClick={onClose}
              disabled={pending}
              className="flex-1 border border-border py-2.5 rounded-xl text-sm font-medium disabled:opacity-50"
            >
              취소
            </button>
            <button
              type="submit"
              disabled={pending || optionsLoading || categories.length === 0}
              className="flex-1 bg-primary hover:bg-blue-700 text-white py-2.5 rounded-xl text-sm font-medium disabled:opacity-50"
            >
              {pending ? "등록 중..." : "등록"}
            </button>
          </div>
        </form>
      </div>
    </div>
  );
}
