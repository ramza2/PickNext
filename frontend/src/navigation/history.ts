/** Browser History helpers for NAV-1 / COL-1 overlays. */

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
    }
  | {
      type: "item-collection-picker";
      itemId: string;
    }
  | {
      type: "collection-add-existing-items";
      collectionId: string;
    };

function isAppOverlay(value: unknown): value is AppOverlay {
  if (!value || typeof value !== "object") return false;
  const record = value as Record<string, unknown>;
  if (record.type === "item-edit" || record.type === "item-collection-picker") {
    return typeof record.itemId === "string" && isUuid(record.itemId);
  }
  if (record.type === "collection-add-existing-items") {
    return typeof record.collectionId === "string" && isUuid(record.collectionId);
  }
  return false;
}

export function overlaysEqual(a: AppOverlay, b: AppOverlay): boolean {
  if (a.type !== b.type) return false;
  if (a.type === "item-edit" || a.type === "item-collection-picker") {
    return (
      a.itemId
      === (b as { type: typeof a.type; itemId: string }).itemId
    );
  }
  if (a.type === "collection-add-existing-items") {
    return (
      a.collectionId
      === (b as { type: "collection-add-existing-items"; collectionId: string })
        .collectionId
    );
  }
  return false;
}

export function normalizeOverlayForRoute(
  route: AppRoute,
  overlay: AppOverlay | null | undefined,
): AppOverlay | null {
  if (!overlay) return null;
  if (overlay.type === "item-edit" || overlay.type === "item-collection-picker") {
    if (route.name !== "item-detail") return null;
    if (overlay.itemId !== route.itemId) return null;
    return overlay;
  }
  if (overlay.type === "collection-add-existing-items") {
    if (route.name !== "collections") return null;
    if (!route.collectionId || overlay.collectionId !== route.collectionId) {
      return null;
    }
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
