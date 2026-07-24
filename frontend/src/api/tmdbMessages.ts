import { ApiError } from "./client";

const TMDB_CODE_MESSAGES: Record<string, string> = {
  TMDB_NOT_CONFIGURED: "TMDB API가 설정되지 않았습니다. 서버 환경 변수를 확인해 주세요.",
  TMDB_AUTH_FAILED: "TMDB 인증에 실패했습니다. API 토큰을 확인해 주세요.",
  TMDB_NOT_FOUND: "TMDB에서 해당 콘텐츠를 찾을 수 없습니다.",
  TMDB_RATE_LIMITED: "TMDB 요청 한도를 초과했습니다. 잠시 후 다시 시도해 주세요.",
  TMDB_UNAVAILABLE: "TMDB에 일시적으로 연결할 수 없습니다.",
  TMDB_UPSTREAM_ERROR: "TMDB 응답을 처리하지 못했습니다.",
  TMDB_ITEM_ALREADY_EXISTS: "이미 등록된 TMDB 콘텐츠입니다.",
};

export function messageForTmdbCode(code: string): string | null {
  return TMDB_CODE_MESSAGES[code] ?? null;
}

export function tmdbErrorMessage(err: unknown, fallback: string): string {
  if (err instanceof ApiError) {
    if (typeof err.detail === "string") {
      const mapped = messageForTmdbCode(err.detail);
      if (mapped) return mapped;
    }
    if (err.detail && typeof err.detail === "object" && "code" in err.detail) {
      const code = (err.detail as { code: unknown }).code;
      if (typeof code === "string") {
        const mapped = messageForTmdbCode(code);
        if (mapped) return mapped;
      }
    }
    if (err.status === 0) {
      return "네트워크 오류가 발생했습니다. 연결을 확인해 주세요.";
    }
    if (err.message && err.message !== `Request failed (${err.status})`) {
      const mapped = messageForTmdbCode(err.message);
      if (mapped) return mapped;
      return err.message;
    }
  }
  return fallback;
}

export function tmdbStatusUnavailableMessage(): string {
  return "TMDB를 사용할 수 없습니다. 잠시 후 다시 시도해 주세요.";
}

export function tmdbNotConfiguredMessage(): string {
  return TMDB_CODE_MESSAGES.TMDB_NOT_CONFIGURED;
}

export function tmdbSearchFailureMessage(): string {
  return "검색에 실패했습니다. 잠시 후 다시 시도해 주세요.";
}

export function tmdbDetailFailureMessage(): string {
  return "상세 정보를 불러오지 못했습니다.";
}

export function tmdbRegisterSuccessToast(): string {
  return "항목을 추가했습니다.";
}

export function tmdbAlreadyRegisteredToast(): string {
  return "이미 등록된 콘텐츠입니다.";
}
