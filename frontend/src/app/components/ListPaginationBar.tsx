import { ChevronLeft, ChevronRight, ChevronsLeft, ChevronsRight } from "lucide-react";
import type { ReactNode } from "react";
import { buildPageWindow } from "../../utils/pagination";

export function ListPaginationBar({
  page,
  totalPages,
  hasPrevious,
  hasNext,
  onPageChange,
  summary,
  windowSize = 5,
}: {
  page: number;
  totalPages: number;
  hasPrevious: boolean;
  hasNext: boolean;
  onPageChange: (page: number) => void;
  summary: ReactNode;
  windowSize?: number;
}) {
  if (totalPages <= 1) return null;

  const pages = buildPageWindow(page, totalPages, windowSize);

  return (
    <div className="flex items-center justify-between mt-5">
      <p className="text-xs text-muted-foreground">{summary}</p>
      <div className="flex items-center gap-1">
        <button
          type="button"
          onClick={() => onPageChange(1)}
          disabled={!hasPrevious}
          aria-label="첫 페이지"
          className="p-1.5 rounded-lg border border-border text-muted-foreground hover:text-foreground disabled:opacity-30 transition-colors"
        >
          <ChevronsLeft size={14} />
        </button>
        <button
          type="button"
          onClick={() => onPageChange(page - 1)}
          disabled={!hasPrevious}
          aria-label="이전 페이지"
          className="p-1.5 rounded-lg border border-border text-muted-foreground hover:text-foreground disabled:opacity-30 transition-colors"
        >
          <ChevronLeft size={14} />
        </button>
        {pages.map((p) => (
          <button
            key={p}
            type="button"
            onClick={() => onPageChange(p)}
            aria-label={`${p}페이지`}
            aria-current={page === p ? "page" : undefined}
            className={`w-7 h-7 rounded-lg text-xs font-medium border transition-colors ${
              page === p
                ? "border-primary bg-primary text-white"
                : "border-border text-foreground hover:bg-muted"
            }`}
          >
            {p}
          </button>
        ))}
        <button
          type="button"
          onClick={() => onPageChange(page + 1)}
          disabled={!hasNext}
          aria-label="다음 페이지"
          className="p-1.5 rounded-lg border border-border text-muted-foreground hover:text-foreground disabled:opacity-30 transition-colors"
        >
          <ChevronRight size={14} />
        </button>
        <button
          type="button"
          onClick={() => onPageChange(totalPages)}
          disabled={!hasNext}
          aria-label="마지막 페이지"
          className="p-1.5 rounded-lg border border-border text-muted-foreground hover:text-foreground disabled:opacity-30 transition-colors"
        >
          <ChevronsRight size={14} />
        </button>
      </div>
    </div>
  );
}
