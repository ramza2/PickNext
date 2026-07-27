/** Browser History helpers for NAV-1. */

import {
  buildPath,
  isUuid,
  parseCurrentLocation,
  type AppRoute,
} from "./routes";

export type AppOverlay =
  | {
      type: "item-edit";
      itemId: string;
    };

function isAppOverlay(value: unknown): value is AppOverlay {
  if (!value || typeof value !== "object") return false;
  const record = value as Record<string, unknown>;
  if (record.type !== "item-edit") return false;
  return typeof record.itemId === "string" && isUuid(record.itemId);
}

export function normalizeOverlayForRoute(
  route: AppRoute,
  overlay: AppOverlay | null | undefined,
): AppOverlay | null {
  if (!overlay) return null;
  if (overlay.type === "item-edit") {
    if (route.name !== "item-detail") return null;
    if (overlay.itemId !== route.itemId) return null;
    return overlay;
  }
  return null;
}

export interface PickNextHistoryState {
  picknext: true;
  entryId: string;
  navIndex: number;
  routeName: AppRoute["name"];
  overlay?: AppOverlay;
}

export function isPickNextHistoryState(
  value: unknown,
): value is PickNextHistoryState {
  if (!value || typeof value !== "object") return false;
  const record = value as Record<string, unknown>;
  return (
    record.picknext === true &&
    typeof record.entryId === "string" &&
    typeof record.navIndex === "number" &&
    typeof record.routeName === "string" &&
    (
      record.overlay == null
      || isAppOverlay(record.overlay)
    )
  );
}

export function createEntryId(): string {
  if (typeof crypto !== "undefined" && "randomUUID" in crypto) {
    return crypto.randomUUID();
  }
  return `e-${Date.now()}-${Math.random().toString(36).slice(2, 10)}`;
}

export function readHistoryState(): PickNextHistoryState | null {
  return isPickNextHistoryState(window.history.state) ? window.history.state : null;
}

export function applyHistory(
  method: "push" | "replace",
  route: AppRoute,
  meta: PickNextHistoryState,
): void {
  const url = buildPath(route);
  const state: PickNextHistoryState = {
    ...meta,
    routeName: route.name,
  };
  if (method === "push") {
    window.history.pushState(state, "", url);
  } else {
    window.history.replaceState(state, "", url);
  }
}

/** Initial load: keep entry, only attach metadata. */
export function ensureInitialHistoryMeta(route: AppRoute): PickNextHistoryState {
  const existing = readHistoryState();
  if (existing) {
    if (existing.overlay) {
      const cleaned: PickNextHistoryState = {
        ...existing,
        routeName: route.name,
        overlay: undefined,
      };
      applyHistory("replace", route, cleaned);
      return cleaned;
    }
    return existing;
  }
  const meta: PickNextHistoryState = {
    picknext: true,
    entryId: createEntryId(),
    navIndex: 0,
    routeName: route.name,
  };
  applyHistory("replace", route, meta);
  return meta;
}

export function currentRouteFromLocation(): AppRoute {
  return parseCurrentLocation();
}
