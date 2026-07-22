import { ApiError } from "./client";

export const COLLECTION_NAME_EMPTY_ERROR =
  "컬렉션 이름을 입력해 주세요.";
export const COLLECTION_NAME_TOO_LONG_ERROR =
  "컬렉션 이름은 200자 이하여야 합니다.";
export const COLLECTION_NAME_DUPLICATE_ERROR =
  "같은 이름의 컬렉션이 이미 있습니다.";
export const COLLECTION_WRITE_VALIDATION_ERROR =
  "컬렉션 이름을 확인해 주세요.";

export function normalizeCollectionNameInput(value: string): string {
  return value.trim();
}

export function validateCollectionName(normalizedName: string): string | null {
  if (!normalizedName) return COLLECTION_NAME_EMPTY_ERROR;
  if (normalizedName.length > 200) return COLLECTION_NAME_TOO_LONG_ERROR;
  return null;
}

export function collectionCreateFailureToast(): string {
  return "컬렉션을 만들지 못했습니다. 잠시 후 다시 시도해 주세요.";
}

export function collectionUpdateFailureToast(): string {
  return "컬렉션 이름을 수정하지 못했습니다. 잠시 후 다시 시도해 주세요.";
}

export function collectionPatchNotFoundToast(): string {
  return "이미 삭제되었거나 찾을 수 없는 컬렉션입니다.";
}

export function collectionWriteConflictInline(): string {
  return COLLECTION_NAME_DUPLICATE_ERROR;
}

export function collectionWriteValidationInline(): string {
  return COLLECTION_WRITE_VALIDATION_ERROR;
}

export function isCollectionWriteNetworkOrServerError(err: unknown): boolean {
  return (
    err instanceof ApiError &&
    (err.status === 0 || err.status >= 500)
  );
}
