import { useEffect, useState } from "react";
import { ChevronDown, ChevronUp, RotateCcw } from "lucide-react";
import {
  DESKTOP_NAV_LABELS,
  loadDesktopNavOrder,
  resetDesktopNavOrder,
  saveDesktopNavOrder,
  type DesktopNavId,
} from "./navigationOrder";

export function NavigationOrderSettings({
  userKey,
}: {
  userKey: string;
}) {
  const [order, setOrder] = useState<DesktopNavId[]>(() =>
    loadDesktopNavOrder(userKey),
  );

  useEffect(() => {
    setOrder(loadDesktopNavOrder(userKey));
  }, [userKey]);

  const move = (index: number, direction: -1 | 1) => {
    const nextIndex = index + direction;
    if (nextIndex < 0 || nextIndex >= order.length) return;

    const next = [...order];
    [next[index], next[nextIndex]] = [next[nextIndex], next[index]];
    const saved = saveDesktopNavOrder(userKey, next);
    setOrder(saved);
  };

  const reset = () => {
    setOrder(resetDesktopNavOrder(userKey));
  };

  return (
    <div className="bg-card border border-border rounded-2xl overflow-hidden">
      <div className="px-5 py-4 border-b border-border flex items-start justify-between gap-3">
        <div>
          <div className="text-sm font-semibold text-foreground">메뉴 순서</div>
          <p className="text-xs text-muted-foreground mt-1">
            데스크톱 좌측 메뉴 순서를 변경합니다. 모바일 하단 메뉴 순서는 유지됩니다.
          </p>
        </div>
        <button
          type="button"
          onClick={reset}
          className="shrink-0 inline-flex items-center gap-1.5 text-xs text-muted-foreground border border-border px-2.5 py-1.5 rounded-lg hover:bg-muted hover:text-foreground"
        >
          <RotateCcw size={13} />
          기본 순서
        </button>
      </div>

      <div className="divide-y divide-border">
        {order.map((id, index) => (
          <div
            key={id}
            className="px-5 py-3 flex items-center gap-3"
          >
            <span className="w-5 text-xs text-muted-foreground tabular-nums">
              {index + 1}
            </span>
            <span className="flex-1 text-sm font-medium text-foreground">
              {DESKTOP_NAV_LABELS[id]}
            </span>
            <div className="flex items-center gap-1">
              <button
                type="button"
                aria-label={`${DESKTOP_NAV_LABELS[id]} 위로 이동`}
                title="위로 이동"
                disabled={index === 0}
                onClick={() => move(index, -1)}
                className="p-1.5 rounded-lg border border-border text-muted-foreground hover:text-foreground hover:bg-muted disabled:opacity-30 disabled:cursor-not-allowed"
              >
                <ChevronUp size={14} />
              </button>
              <button
                type="button"
                aria-label={`${DESKTOP_NAV_LABELS[id]} 아래로 이동`}
                title="아래로 이동"
                disabled={index === order.length - 1}
                onClick={() => move(index, 1)}
                className="p-1.5 rounded-lg border border-border text-muted-foreground hover:text-foreground hover:bg-muted disabled:opacity-30 disabled:cursor-not-allowed"
              >
                <ChevronDown size={14} />
              </button>
            </div>
          </div>
        ))}
      </div>
    </div>
  );
}
