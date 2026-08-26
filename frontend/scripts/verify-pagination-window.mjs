/**
 * UI-PAGE-1: verify page-number window logic (mirrors src/utils/pagination.ts).
 * Run: node frontend/scripts/verify-pagination-window.mjs
 */
import assert from "node:assert/strict";

function buildPageWindow(currentPage, totalPages, windowSize = 5) {
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

  const pages = [];
  for (let page = start; page <= end; page += 1) {
    pages.push(page);
  }
  return pages;
}

function assertWindow(page, total, expected, size = 5) {
  const actual = buildPageWindow(page, total, size);
  assert.deepEqual(
    actual,
    expected,
    `page=${page} total=${total} size=${size} => ${JSON.stringify(actual)}`,
  );
  assert.equal(new Set(actual).size, actual.length, "duplicate pages");
  if (actual.length > 0) {
    assert.equal(
      actual[actual.length - 1] - actual[0] + 1,
      actual.length,
      "contiguous",
    );
  }
}

assertWindow(289, 289, [285, 286, 287, 288, 289]);
assertWindow(1, 289, [1, 2, 3, 4, 5]);
assertWindow(2, 289, [1, 2, 3, 4, 5]);
assertWindow(3, 289, [1, 2, 3, 4, 5]);
assertWindow(145, 289, [143, 144, 145, 146, 147]);
assertWindow(287, 289, [285, 286, 287, 288, 289]);
assertWindow(288, 289, [285, 286, 287, 288, 289]);
assertWindow(1, 3, [1, 2, 3]);
assertWindow(2, 3, [1, 2, 3]);
assertWindow(3, 3, [1, 2, 3]);
assertWindow(1, 1, [1]);
assertWindow(5, 0, []);
assertWindow(-1, 10, [1, 2, 3, 4, 5]);

console.log("verify-pagination-window: ok");
