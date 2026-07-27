import {
  createContext,
  useCallback,
  useContext,
  useEffect,
  useMemo,
  useRef,
  useState,
  type ReactNode,
} from "react";
import {
  applyHistory,
  createEntryId,
  ensureInitialHistoryMeta,
  isPickNextHistoryState,
  readHistoryState,
  type PickNextHistoryState,
} from "./history";
import {
  clearRouteCache,
  createEmptyRouteCache,
  type RouteSessionCache,
} from "./routeCache";
import {
  buildPath,
  fallbackFor,
  parseCurrentLocation,
  routesEqual,
  type AppRoute,
} from "./routes";

export interface NavigateOptions {
  replace?: boolean;
}

interface NavigationContextValue {
  route: AppRoute;
  entryId: string;
  navIndex: number;
  cache: RouteSessionCache;
  navigate: (route: AppRoute, options?: NavigateOptions) => void;
  replace: (route: AppRoute) => void;
  goBack: (fallback?: AppRoute) => void;
  clearSessionCaches: () => void;
  bumpCacheVersion: () => void;
  cacheVersion: number;
}

const NavigationContext = createContext<NavigationContextValue | null>(null);

function getScrollRoot(): HTMLElement | null {
  return document.querySelector<HTMLElement>("[data-picknext-scroll-root]");
}

function rememberScroll(cache: RouteSessionCache, entryId: string): void {
  const root = getScrollRoot();
  const y = root ? root.scrollTop : window.scrollY || window.pageYOffset || 0;
  cache.scrollByEntryId.set(entryId, y);
}

function restoreScroll(cache: RouteSessionCache, entryId: string): void {
  const y = cache.scrollByEntryId.get(entryId);
  if (y == null) return;
  requestAnimationFrame(() => {
    const root = getScrollRoot();
    if (root) {
      root.scrollTop = y;
    } else {
      window.scrollTo(0, y);
    }
  });
}

export function NavigationProvider({ children }: { children: ReactNode }) {
  const cacheRef = useRef<RouteSessionCache>(createEmptyRouteCache());
  const [cacheVersion, setCacheVersion] = useState(0);
  const bumpCacheVersion = useCallback(() => {
    setCacheVersion((v) => v + 1);
  }, []);

  const initialRoute = useMemo(() => parseCurrentLocation(), []);
  const initialMeta = useMemo(
    () => ensureInitialHistoryMeta(initialRoute),
    [initialRoute],
  );

  const [route, setRoute] = useState<AppRoute>(initialRoute);
  const [entryId, setEntryId] = useState(initialMeta.entryId);
  const [navIndex, setNavIndex] = useState(initialMeta.navIndex);
  const navIndexRef = useRef(initialMeta.navIndex);
  const entryIdRef = useRef(initialMeta.entryId);
  const routeRef = useRef(initialRoute);

  useEffect(() => {
    routeRef.current = route;
  }, [route]);

  useEffect(() => {
    try {
      window.history.scrollRestoration = "manual";
    } catch {
      // ignore
    }
  }, []);

  const applyRoute = useCallback(
    (next: AppRoute, meta: PickNextHistoryState, restore = false) => {
      setRoute(next);
      setEntryId(meta.entryId);
      setNavIndex(meta.navIndex);
      navIndexRef.current = meta.navIndex;
      entryIdRef.current = meta.entryId;
      if (restore) {
        restoreScroll(cacheRef.current, meta.entryId);
      }
    },
    [],
  );

  const navigate = useCallback(
    (next: AppRoute, options?: NavigateOptions) => {
      const method = options?.replace ? "replace" : "push";
      if (routesEqual(routeRef.current, next) && method === "push") {
        return;
      }
      if (routesEqual(routeRef.current, next) && method === "replace") {
        const current = readHistoryState();
        if (current) {
          applyHistory("replace", next, current);
        }
        setRoute(next);
        return;
      }

      rememberScroll(cacheRef.current, entryIdRef.current);

      if (method === "replace") {
        const meta: PickNextHistoryState = {
          picknext: true,
          entryId: entryIdRef.current,
          navIndex: navIndexRef.current,
          routeName: next.name,
        };
        applyHistory("replace", next, meta);
        applyRoute(next, meta, false);
        return;
      }

      const meta: PickNextHistoryState = {
        picknext: true,
        entryId: createEntryId(),
        navIndex: navIndexRef.current + 1,
        routeName: next.name,
      };
      applyHistory("push", next, meta);
      applyRoute(next, meta, false);
    },
    [applyRoute],
  );

  const replace = useCallback(
    (next: AppRoute) => {
      navigate(next, { replace: true });
    },
    [navigate],
  );

  const goBack = useCallback(
    (fallback?: AppRoute) => {
      rememberScroll(cacheRef.current, entryIdRef.current);
      if (navIndexRef.current > 0) {
        window.history.back();
        return;
      }
      const target = fallback ?? fallbackFor(routeRef.current);
      replace(target);
    },
    [replace],
  );

  const clearSessionCaches = useCallback(() => {
    clearRouteCache(cacheRef.current);
    bumpCacheVersion();
  }, [bumpCacheVersion]);

  useEffect(() => {
    const onPopState = (event: PopStateEvent) => {
      const nextRoute = parseCurrentLocation();
      const state = isPickNextHistoryState(event.state)
        ? event.state
        : {
            picknext: true as const,
            entryId: createEntryId(),
            navIndex: 0,
            routeName: nextRoute.name,
          };
      if (!isPickNextHistoryState(event.state)) {
        applyHistory("replace", nextRoute, state);
      }
      applyRoute(nextRoute, state, true);
    };
    window.addEventListener("popstate", onPopState);
    return () => window.removeEventListener("popstate", onPopState);
  }, [applyRoute]);

  const value = useMemo<NavigationContextValue>(
    () => ({
      route,
      entryId,
      navIndex,
      cache: cacheRef.current,
      navigate,
      replace,
      goBack,
      clearSessionCaches,
      bumpCacheVersion,
      cacheVersion,
    }),
    [
      route,
      entryId,
      navIndex,
      navigate,
      replace,
      goBack,
      clearSessionCaches,
      bumpCacheVersion,
      cacheVersion,
    ],
  );

  return (
    <NavigationContext.Provider value={value}>
      {children}
    </NavigationContext.Provider>
  );
}

export function useAppNavigation(): NavigationContextValue {
  const ctx = useContext(NavigationContext);
  if (!ctx) {
    throw new Error("useAppNavigation must be used within NavigationProvider");
  }
  return ctx;
}

/** Path helper for callers that only need URL string. */
export function pathFor(route: AppRoute): string {
  return buildPath(route);
}
