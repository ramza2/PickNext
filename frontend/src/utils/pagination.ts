/**
 * Build a contiguous, duplicate-free page number window.
 * Centers on `currentPage` when possible and slides the window
 * within `[1, totalPages]` near the edges.
 */
export function buildPageWindow(
  currentPage: number,
  totalPages: number,
  windowSize = 5,
): number[] {
  if (!Number.isFinite(totalPages) || totalPages < 1) return [];
  const size = Math.min(Math.max(1, windowSize), totalPages);
  const current = Math.min(Math.max(1, currentPage), totalPages);

  let start = current - Math.floor(size / 2);
  let end = start + size - 1;

  if (start < 1) {
    start = 1;
    end = size;
  }
  if (end > totalPages) {
    end = totalPages;
    start = end - size + 1;
  }

  const pages: number[] = [];
  for (let page = start; page <= end; page += 1) {
    pages.push(page);
  }
  return pages;
}
