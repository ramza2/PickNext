import type { Page } from "../pageTypes";

export const DESKTOP_NAV_DEFAULT_ORDER = [
  "home",
  "items",
  "collections",
  "search",
  "recommend",
  "history",
  "settings",
] as const satisfies readonly Page[];

export type DesktopNavId = (typeof DESKTOP_NAV_DEFAULT_ORDER)[number];

export const DESKTOP_NAV_LABELS: Record<DesktopNavId, string> = {
  home: "홈",
  items: "전체 항목",
  collections: "Collection",
  search: "콘텐츠 검색",
  recommend: "랜덤 추천",
  history: "추천 이력",
  settings: "설정",
};

export const NAV_ORDER_CHANGED_EVENT = "picknext:nav-order-changed";

const STORAGE_PREFIX = "picknext.nav-order.v1:";

function storageKey(userKey: string): string {
  return `${STORAGE_PREFIX}${encodeURIComponent(userKey)}`;
}

export function normalizeDesktopNavOrder(value: unknown): DesktopNavId[] {
  const allowed = new Set<DesktopNavId>(DESKTOP_NAV_DEFAULT_ORDER);
  const normalized: DesktopNavId[] = [];

  if (Array.isArray(value)) {
    for (const entry of value) {
      if (
        typeof entry === "string"
        && allowed.has(entry as DesktopNavId)
        && !normalized.includes(entry as DesktopNavId)
      ) {
        normalized.push(entry as DesktopNavId);
      }
    }
  }

  for (const id of DESKTOP_NAV_DEFAULT_ORDER) {
    if (!normalized.includes(id)) normalized.push(id);
  }

  return normalized;
}

export function loadDesktopNavOrder(userKey?: string | null): DesktopNavId[] {
  if (!userKey || typeof window === "undefined") {
    return [...DESKTOP_NAV_DEFAULT_ORDER];
  }

  try {
    const raw = window.localStorage.getItem(storageKey(userKey));
    if (!raw) return [...DESKTOP_NAV_DEFAULT_ORDER];
    return normalizeDesktopNavOrder(JSON.parse(raw));
  } catch {
    return [...DESKTOP_NAV_DEFAULT_ORDER];
  }
}

export function saveDesktopNavOrder(
  userKey: string,
  order: readonly DesktopNavId[],
): DesktopNavId[] {
  const normalized = normalizeDesktopNavOrder(order);
  try {
    window.localStorage.setItem(storageKey(userKey), JSON.stringify(normalized));
  } catch {
    // Keep the current-session order even when browser storage is unavailable.
  }
  window.dispatchEvent(new CustomEvent(NAV_ORDER_CHANGED_EVENT, {
    detail: { userKey },
  }));
  return normalized;
}

export function resetDesktopNavOrder(userKey: string): DesktopNavId[] {
  try {
    window.localStorage.removeItem(storageKey(userKey));
  } catch {
    // Reset still applies for the current session when storage is unavailable.
  }
  window.dispatchEvent(new CustomEvent(NAV_ORDER_CHANGED_EVENT, {
    detail: { userKey },
  }));
  return [...DESKTOP_NAV_DEFAULT_ORDER];
}
