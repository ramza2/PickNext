import { ApiError } from "./client";

function isNetworkError(err: unknown): boolean {
  return err instanceof ApiError && err.status === 0;
}

export function itemDeleteErrorMessage(err: unknown): string {
  if (err instanceof ApiError) {
    if (err.status === 404) {
      return "이미 삭제되었거나 찾을 수 없는 항목입니다.";
    }
    if (err.status === 409) {
      return "다른 작업과 충돌했습니다. 화면을 새로고침한 후 다시 시도해 주세요.";
    }
    if (err.status === 422) {
      return "잘못된 항목 정보입니다.";
    }
    if (err.status >= 500 || isNetworkError(err)) {
      return "항목을 삭제하지 못했습니다. 잠시 후 다시 시도해 주세요.";
    }
  }
  return "항목을 삭제하지 못했습니다. 잠시 후 다시 시도해 주세요.";
}

export function collectionDeleteErrorMessage(err: unknown): string {
  if (err instanceof ApiError) {
    if (err.status === 404) {
      return "이미 삭제되었거나 찾을 수 없는 컬렉션입니다.";
    }
    if (err.status === 409) {
      return "항목이 있는 컬렉션은 삭제할 수 없습니다.";
    }
    if (err.status === 422) {
      return "잘못된 컬렉션 정보입니다.";
    }
    if (err.status >= 500 || isNetworkError(err)) {
      return "컬렉션을 삭제하지 못했습니다. 잠시 후 다시 시도해 주세요.";
    }
  }
  return "컬렉션을 삭제하지 못했습니다. 잠시 후 다시 시도해 주세요.";
}
