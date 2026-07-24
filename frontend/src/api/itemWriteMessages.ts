import { ApiError } from "./client";
import type { ApiItemDetail, ApiItemStatus } from "../types/api";
import type { ItemCreatePayload, ItemUpdatePayload } from "./catalog";

export const ITEM_TITLE_EMPTY_ERROR = "항목 제목을 입력해 주세요.";
export const ITEM_CATEGORY_REQUIRED_ERROR = "카테고리를 선택해 주세요.";
export const ITEM_CATEGORY_EMPTY_LIST_ERROR =
  "항목을 추가하려면 먼저 카테고리가 필요합니다.";
export const ITEM_PROGRESS_NOTE_TOO_LONG_ERROR =
  "진행 상황은 200자 이하여야 합니다.";
export const ITEM_RELEASE_YEAR_INVALID_ERROR =
  "출시년도는 4자리 숫자로 입력해 주세요.";
export const ITEM_WRITE_VALIDATION_ERROR =
  "입력한 항목 정보를 확인해 주세요.";
export const ITEM_RELATED_NOT_FOUND_ERROR =
  "선택한 카테고리 또는 컬렉션을 찾을 수 없습니다.";
export const ITEM_RELATED_CHANGED_ERROR =
  "선택한 카테고리 또는 컬렉션이 변경되었습니다. 목록을 새로 불러온 후 다시 시도해 주세요.";
export const ITEM_PATCH_CONFLICT_ERROR =
  "선택한 카테고리 또는 컬렉션이 변경되었습니다. 다시 확인해 주세요.";
export const ITEM_NOT_FOUND_TOAST =
  "이미 삭제되었거나 찾을 수 없는 항목입니다.";
export const ITEM_COLLECTION_NOT_FOUND_TOAST =
  "이미 삭제되었거나 찾을 수 없는 컬렉션입니다.";
export const ITEM_STATUS_CHECK_FAILED_TOAST =
  "항목 상태를 확인하지 못했습니다. 잠시 후 다시 시도해 주세요.";

export const RATING_OPTIONS: number[] = Array.from(
  { length: 11 },
  (_, index) => index * 0.5,
);

export function normalizeItemTitleInput(value: string): string {
  return value.trim();
}

export function normalizeNullableText(value: string): string | null {
  const trimmed = value.trim();
  return trimmed ? trimmed : null;
}

export function validateItemTitle(normalizedTitle: string): string | null {
  if (!normalizedTitle) return ITEM_TITLE_EMPTY_ERROR;
  return null;
}

export function validateProgressNote(normalizedNote: string | null): string | null {
  if (normalizedNote && normalizedNote.length > 200) {
    return ITEM_PROGRESS_NOTE_TOO_LONG_ERROR;
  }
  return null;
}

/** Empty input → null. Otherwise must be 1000–9999 integer text. */
export function parseReleaseYearInput(raw: string): {
  value: number | null;
  error: string | null;
} {
  const trimmed = raw.trim();
  if (!trimmed) {
    return { value: null, error: null };
  }
  if (!/^\d{4}$/.test(trimmed)) {
    return { value: null, error: ITEM_RELEASE_YEAR_INVALID_ERROR };
  }
  const year = Number(trimmed);
  if (year < 1000 || year > 9999) {
    return { value: null, error: ITEM_RELEASE_YEAR_INVALID_ERROR };
  }
  return { value: year, error: null };
}

export function validateReleaseYearInput(raw: string): string | null {
  return parseReleaseYearInput(raw).error;
}

export function itemCreateFailureToast(): string {
  return "항목을 추가하지 못했습니다. 잠시 후 다시 시도해 주세요.";
}

export function itemUpdateFailureToast(): string {
  return "항목을 수정하지 못했습니다. 잠시 후 다시 시도해 주세요.";
}

export function itemStatusUpdateFailureToast(): string {
  return "항목 상태를 변경하지 못했습니다. 잠시 후 다시 시도해 주세요.";
}

export function itemStatusConflictToast(): string {
  return "항목 상태를 변경하지 못했습니다. 관련 정보가 변경되었습니다.";
}

export function itemStatusValidationToast(): string {
  return "항목 상태 값이 올바르지 않습니다.";
}

export function itemStatusSuccessToast(next: ApiItemStatus): string {
  return next === "COMPLETED"
    ? "완료 상태로 변경했습니다."
    : "볼 예정 상태로 변경했습니다.";
}

export function itemUnlinkSuccessToast(): string {
  return "컬렉션에서 항목을 제거했습니다.";
}

export function itemUnlinkFailureToast(): string {
  return "컬렉션에서 항목을 제거하지 못했습니다. 잠시 후 다시 시도해 주세요.";
}

export function itemUnlinkChangedToast(): string {
  return "항목 정보가 변경되었습니다. 목록을 새로 불러왔습니다.";
}

export function itemUnlinkValidationToast(): string {
  return "항목 정보가 올바르지 않습니다.";
}

export function buildCollectionUnlinkConfirmBody(
  itemTitle: string,
  options: { isLastItem: boolean },
): string {
  const lines = [
    `“${itemTitle}” 항목을 이 컬렉션에서 제거할까요?`,
    "",
    "항목 자체는 삭제되지 않으며,",
    "전체 항목 목록에서 계속 확인할 수 있습니다.",
  ];
  if (options.isLastItem) {
    lines.push("", "이 항목을 제거하면 컬렉션은 빈 상태로 유지됩니다.");
  }
  return lines.join("\n");
}

export function isItemWriteNetworkOrServerError(err: unknown): boolean {
  return err instanceof ApiError && (err.status === 0 || err.status >= 500);
}

export interface ItemFormValues {
  title: string;
  categoryId: string;
  collectionId: string | null;
  status: ApiItemStatus;
  rating: number;
  progressNote: string;
  memo: string;
  /** Raw form text; empty means null. */
  releaseYear: string;
  synopsis: string;
}

export function buildItemCreatePayload(values: ItemFormValues): ItemCreatePayload {
  const release = parseReleaseYearInput(values.releaseYear);
  return {
    title: normalizeItemTitleInput(values.title),
    category_id: values.categoryId,
    collection_id: values.collectionId,
    status: values.status,
    rating: values.rating,
    progress_note: normalizeNullableText(values.progressNote),
    memo: normalizeNullableText(values.memo),
    release_year: release.value,
    synopsis: normalizeNullableText(values.synopsis),
  };
}

export function buildItemUpdatePayload(
  values: ItemFormValues,
  source: ApiItemDetail,
): ItemUpdatePayload {
  const payload: ItemUpdatePayload = {};
  const title = normalizeItemTitleInput(values.title);
  const progressNote = normalizeNullableText(values.progressNote);
  const memo = normalizeNullableText(values.memo);
  const synopsis = normalizeNullableText(values.synopsis);
  const sourceCollectionId = source.collection?.id ?? null;
  const release = parseReleaseYearInput(values.releaseYear);
  const sourceYear = source.release_year ?? null;
  const sourceSynopsis = source.synopsis ?? null;

  if (title !== source.title) payload.title = title;
  if (values.categoryId !== source.category.id) {
    payload.category_id = values.categoryId;
  }
  if (values.collectionId !== sourceCollectionId) {
    payload.collection_id = values.collectionId;
  }
  if (values.status !== source.status) payload.status = values.status;
  if (values.rating !== source.rating) payload.rating = values.rating;
  if (progressNote !== source.progress_note) {
    payload.progress_note = progressNote;
  }
  if (memo !== source.memo) payload.memo = memo;
  if (release.value !== sourceYear) {
    payload.release_year = release.value;
  }
  if (synopsis !== sourceSynopsis) {
    payload.synopsis = synopsis;
  }

  return payload;
}

export function itemFormValuesFromDetail(item: ApiItemDetail): ItemFormValues {
  return {
    title: item.title,
    categoryId: item.category.id,
    collectionId: item.collection?.id ?? null,
    status: item.status,
    rating: item.rating,
    progressNote: item.progress_note ?? "",
    memo: item.memo ?? "",
    releaseYear:
      typeof item.release_year === "number" ? String(item.release_year) : "",
    synopsis: item.synopsis ?? "",
  };
}

export type ItemFormFieldErrors = {
  title?: string;
  categoryId?: string;
  progressNote?: string;
  releaseYear?: string;
  form?: string;
};

export function collectItemFormFieldErrors(
  values: ItemFormValues,
  options?: { requireCategory?: boolean; categoriesEmpty?: boolean },
): ItemFormFieldErrors {
  const errors: ItemFormFieldErrors = {};
  if (options?.categoriesEmpty) {
    errors.form = ITEM_CATEGORY_EMPTY_LIST_ERROR;
  }
  const titleError = validateItemTitle(normalizeItemTitleInput(values.title));
  if (titleError) errors.title = titleError;
  if (
    !options?.categoriesEmpty
    && options?.requireCategory !== false
    && !values.categoryId
  ) {
    errors.categoryId = ITEM_CATEGORY_REQUIRED_ERROR;
  }
  const progressError = validateProgressNote(
    normalizeNullableText(values.progressNote),
  );
  if (progressError) errors.progressNote = progressError;
  const yearError = validateReleaseYearInput(values.releaseYear);
  if (yearError) errors.releaseYear = yearError;
  return errors;
}

export function hasItemFormFieldErrors(errors: ItemFormFieldErrors): boolean {
  return Boolean(
    errors.title
    || errors.categoryId
    || errors.progressNote
    || errors.releaseYear
    || errors.form,
  );
}

/** @deprecated Prefer collectItemFormFieldErrors for field-level UX. */
export function validateItemFormValues(
  values: ItemFormValues,
  options?: { requireCategory?: boolean; categoriesEmpty?: boolean },
): string | null {
  const errors = collectItemFormFieldErrors(values, options);
  return (
    errors.form
    ?? errors.title
    ?? errors.categoryId
    ?? errors.progressNote
    ?? errors.releaseYear
    ?? null
  );
}
