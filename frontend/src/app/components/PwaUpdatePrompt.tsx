import { useRegisterSW } from "virtual:pwa-register/react";

/**
 * Prompt when a new Service Worker is waiting.
 * Does not claim offline data readiness — API remains network-only.
 */
export default function PwaUpdatePrompt() {
  const {
    needRefresh: [needRefresh, setNeedRefresh],
    updateServiceWorker,
  } = useRegisterSW({
    onRegisterError(error) {
      console.error("Service Worker registration failed", error);
    },
  });

  if (!needRefresh) return null;

  return (
    <div
      className="fixed z-[65] left-3 right-3 sm:left-auto sm:right-4 bottom-24 sm:bottom-6 sm:max-w-sm"
      role="status"
      aria-live="polite"
    >
      <div className="bg-card border border-border rounded-2xl shadow-xl p-4">
        <p className="text-sm font-semibold text-foreground break-words">
          새 버전이 있습니다.
        </p>
        <p className="text-sm text-muted-foreground mt-1 break-words">
          업데이트하면 최신 기능이 적용됩니다.
        </p>
        <div className="flex gap-2 mt-4">
          <button
            type="button"
            onClick={() => setNeedRefresh(false)}
            className="flex-1 border border-border text-foreground py-2.5 rounded-xl font-medium hover:bg-muted transition-colors text-sm"
          >
            나중에
          </button>
          <button
            type="button"
            onClick={() => {
              void updateServiceWorker(true);
            }}
            className="flex-1 bg-primary hover:bg-blue-700 text-white py-2.5 rounded-xl font-medium transition-colors text-sm"
          >
            업데이트
          </button>
        </div>
      </div>
    </div>
  );
}
