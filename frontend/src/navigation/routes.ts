/** NAV-1 App routes — parse/build only (no React). */

export type ItemsListQuery = {
  q?: string;
  category?: string;
  status?: "PLANNED" | "COMPLETED" | "ALL";
  page?: number;
};

export type AppRoute =
  | { name: "home" }
  | { name: "items"; query?: ItemsListQuery }
  | { name: "item-detail"; itemId: string }
  | { name: "collections"; collectionId?: string }
  | { name: "categories" }
  | { name: "search"; collectionId?: string }
  | { name: "recommend" }
  | { name: "recommendation-history"; page?: number }
  | { name: "recommendation-history-detail"; historyId: string }
  | { name: "settings" }
  | { name: "login"; next?: string }
  | { name: "signup" }
  | { name: "find-id" }
  | { name: "password-reset" }
  | { name: "not-found" };

export type ProtectedRouteName = Exclude<
  AppRoute["name"],
  "login" | "signup" | "find-id" | "password-reset" | "not-found"
>;

export const UUID_RE =
  /^[0-9a-f]{8}-[0-9a-f]{4}-[1-8][0-9a-f]{3}-[89ab][0-9a-f]{3}-[0-9a-f]{12}$/i;

export function isUuid(value: string): boolean {
  return UUID_RE.test(value);
}

/** Allow only same-origin relative paths (open-redirect safe). */
export function sanitizeNextPath(raw: string | null | undefined): string | undefined {
  if (raw == null) return undefined;
  let decoded = raw;
  try {
    decoded = decodeURIComponent(raw);
  } catch {
    return undefined;
  }
  const trimmed = decoded.trim();
  if (!trimmed.startsWith("/")) return undefined;
  if (trimmed.startsWith("//")) return undefined;
  if (trimmed.includes("://")) return undefined;
  if (/^[a-z][a-z0-9+.-]*:/i.test(trimmed)) return undefined;
  if (trimmed.includes("\\")) return undefined;
  return trimmed;
}

export function isAuthRoute(route: AppRoute): boolean {
  return (
    route.name === "login" ||
    route.name === "signup" ||
    route.name === "find-id" ||
    route.name === "password-reset"
  );
}

export function isProtectedRoute(route: AppRoute): boolean {
  if (route.name === "not-found") return false;
  return !isAuthRoute(route);
}

export function routesEqual(a: AppRoute, b: AppRoute): boolean {
  return buildPath(a) === buildPath(b);
}

export function buildPath(route: AppRoute): string {
  switch (route.name) {
    case "home":
      return "/";
    case "items": {
      const params = new URLSearchParams();
      const q = route.query;
      if (q?.q) params.set("q", q.q);
      if (q?.category) params.set("category", q.category);
      if (q?.status && q.status !== "ALL") params.set("status", q.status);
      if (q?.page && q.page > 1) params.set("page", String(q.page));
      const qs = params.toString();
      return qs ? `/items?${qs}` : "/items";
    }
    case "item-detail":
      return `/items/${encodeURIComponent(route.itemId)}`;
    case "collections":
      return route.collectionId
        ? `/collections/${encodeURIComponent(route.collectionId)}`
        : "/collections";
    case "categories":
      return "/categories";
    case "search": {
      if (route.collectionId) {
        return `/search?collection_id=${encodeURIComponent(route.collectionId)}`;
      }
      return "/search";
    }
    case "recommend":
      return "/recommend";
    case "recommendation-history": {
      if (route.page && route.page > 1) {
        return `/recommendation-history?page=${route.page}`;
      }
      return "/recommendation-history";
    }
    case "recommendation-history-detail":
      return `/recommendation-history/${encodeURIComponent(route.historyId)}`;
    case "settings":
      return "/settings";
    case "login": {
      if (route.next) {
        return `/login?next=${encodeURIComponent(route.next)}`;
      }
      return "/login";
    }
    case "signup":
      return "/signup";
    case "find-id":
      return "/find-id";
    case "password-reset":
      return "/password-reset";
    case "not-found":
      return "/not-found";
    default: {
      const _exhaustive: never = route;
      return _exhaustive;
    }
  }
}

function parseItemsQuery(search: string): ItemsListQuery | undefined {
  const params = new URLSearchParams(search);
  const q = params.get("q")?.trim() || undefined;
  const category = params.get("category")?.trim() || undefined;
  const statusRaw = params.get("status");
  const status =
    statusRaw === "PLANNED" || statusRaw === "COMPLETED" || statusRaw === "ALL"
      ? statusRaw
      : undefined;
  const pageRaw = params.get("page");
  const page = pageRaw && /^\d+$/.test(pageRaw) ? Math.max(1, Number(pageRaw)) : undefined;
  if (!q && !category && !status && page == null) return undefined;
  return { q, category, status, page };
}

export function parseLocation(pathname: string, search = ""): AppRoute {
  const path = pathname.replace(/\/+$/, "") || "/";
  const query = search.startsWith("?") ? search.slice(1) : search;

  if (path === "/") return { name: "home" };
  if (path === "/items") return { name: "items", query: parseItemsQuery(query) };
  if (path === "/collections") return { name: "collections" };
  if (path === "/categories") return { name: "categories" };
  if (path === "/search") {
    const params = new URLSearchParams(query);
    const collectionIdRaw = params.get("collection_id")?.trim() || undefined;
    const collectionId =
      collectionIdRaw && isUuid(collectionIdRaw) ? collectionIdRaw : undefined;
    return { name: "search", collectionId };
  }
  if (path === "/recommend") return { name: "recommend" };
  if (path === "/recommendation-history") {
    const params = new URLSearchParams(query);
    const pageRaw = params.get("page");
    const page = pageRaw && /^\d+$/.test(pageRaw) ? Math.max(1, Number(pageRaw)) : undefined;
    return { name: "recommendation-history", page };
  }
  if (path === "/settings") return { name: "settings" };
  if (path === "/login") {
    const params = new URLSearchParams(query);
    return { name: "login", next: sanitizeNextPath(params.get("next")) };
  }
  if (path === "/signup") return { name: "signup" };
  if (path === "/find-id") return { name: "find-id" };
  if (path === "/password-reset") return { name: "password-reset" };
  if (path === "/not-found") return { name: "not-found" };

  const itemMatch = path.match(/^\/items\/([^/]+)$/);
  if (itemMatch) {
    const itemId = decodeURIComponent(itemMatch[1]);
    if (!isUuid(itemId)) return { name: "not-found" };
    return { name: "item-detail", itemId };
  }

  const collectionMatch = path.match(/^\/collections\/([^/]+)$/);
  if (collectionMatch) {
    const collectionId = decodeURIComponent(collectionMatch[1]);
    if (!isUuid(collectionId)) return { name: "not-found" };
    return { name: "collections", collectionId };
  }

  const historyMatch = path.match(/^\/recommendation-history\/([^/]+)$/);
  if (historyMatch) {
    const historyId = decodeURIComponent(historyMatch[1]);
    if (!isUuid(historyId)) return { name: "not-found" };
    return { name: "recommendation-history-detail", historyId };
  }

  // Legacy aliases
  if (path === "/history") return { name: "recommendation-history" };

  return { name: "not-found" };
}

export function parseCurrentLocation(): AppRoute {
  return parseLocation(window.location.pathname, window.location.search);
}

/** Fallback when no internal history (direct entry). */
export function fallbackFor(route: AppRoute): AppRoute {
  switch (route.name) {
    case "item-detail":
      return { name: "items" };
    case "recommendation-history-detail":
      return { name: "recommendation-history" };
    case "collections":
      return route.collectionId ? { name: "collections" } : { name: "home" };
    case "categories":
      return { name: "settings" };
    case "not-found":
      return { name: "home" };
    default:
      return { name: "home" };
  }
}

/** Map route → legacy Page id for AppLayout active state. */
export function routeToNavPage(route: AppRoute): string {
  switch (route.name) {
    case "home":
      return "home";
    case "items":
    case "item-detail":
      return "items";
    case "collections":
      return "collections";
    case "categories":
      return "category-manage";
    case "search":
      return "search";
    case "recommend":
      return "recommend";
    case "recommendation-history":
    case "recommendation-history-detail":
      return "history";
    case "settings":
      return "settings";
    default:
      return "home";
  }
}

export function routeTitle(route: AppRoute): string {
  switch (route.name) {
    case "home":
      return "홈";
    case "items":
      return "전체 항목";
    case "item-detail":
      return "항목 상세";
    case "collections":
      return "Collection";
    case "categories":
      return "Category";
    case "search":
      return "영화·드라마 검색";
    case "recommend":
      return "랜덤 추천";
    case "recommendation-history":
      return "추천 이력";
    case "recommendation-history-detail":
      return "추천 이력 상세";
    case "settings":
      return "설정";
    case "login":
      return "로그인";
    case "signup":
      return "회원가입";
    case "find-id":
      return "아이디 찾기";
    case "password-reset":
      return "비밀번호 재설정";
    case "not-found":
      return "페이지 없음";
    default:
      return "PickNext";
  }
}
