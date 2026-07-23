import { ApiError } from "./client";
import type { ApiItemDetail, ApiItemStatus } from "../types/api";
import type { ItemCreatePayload, ItemUpdatePayload } from "./catalog";

export const ITEM_TITLE_EMPTY_ERROR = "항목 제목을 입력해 주세요.";
export const ITEM_CATEGORY_REQUIRED_ERROR = "카테고리를 선택해 주세요.";
export const ITEM_CATEGORY_EMPTY_LIST_ERROR =
  "항목을 추가하려면 먼저 카테고리가 필요합니다.";
export const ITEM_PROGRESS_NOTE_TOO_LONG_ERROR =
  "진행 상황은 200자 이하여야 합니다.";
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
}

export function buildItemCreatePayload(values: ItemFormValues): ItemCreatePayload {
  return {
    title: normalizeItemTitleInput(values.title),
    category_id: values.categoryId,
    collection_id: values.collectionId,
    status: values.status,
    rating: values.rating,
    progress_note: normalizeNullableText(values.progressNote),
    memo: normalizeNullableText(values.memo),
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
  const sourceCollectionId = source.collection?.id ?? null;

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
  };
}

export function validateItemFormValues(
  values: ItemFormValues,
  options?: { requireCategory?: boolean; categoriesEmpty?: boolean },
): string | null {
  if (options?.categoriesEmpty) return ITEM_CATEGORY_EMPTY_LIST_ERROR;
  const titleError = validateItemTitle(normalizeItemTitleInput(values.title));
  if (titleError) return titleError;
  if (options?.requireCategory !== false && !values.categoryId) {
    return ITEM_CATEGORY_REQUIRED_ERROR;
  }
  const progressError = validateProgressNote(
    normalizeNullableText(values.progressNote),
  );
  if (progressError) return progressError;
  return null;
}
