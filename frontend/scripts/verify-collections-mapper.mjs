/**
 * Lightweight mapper checks without introducing a Frontend test framework.
 * Run: node scripts/verify-collections-mapper.mjs
 */
import assert from "node:assert/strict";

function computeCollectionProgressPercent(itemCount, completedCount) {
  if (!Number.isFinite(itemCount) || itemCount <= 0) return 0;
  if (!Number.isFinite(completedCount) || completedCount <= 0) return 0;
  return Math.round((completedCount / itemCount) * 100);
}

function mapApiCollectionToListItem(collection) {
  return {
    id: collection.id,
    name: collection.name,
    itemCount: collection.item_count,
    plannedCount: collection.planned_count,
    completedCount: collection.completed_count,
    categories: collection.categories.map((category) => ({
      id: category.id,
      name: category.name,
      itemCount: category.item_count,
    })),
    progressPercent: computeCollectionProgressPercent(
      collection.item_count,
      collection.completed_count,
    ),
    averageRating: null,
    createdAt: collection.created_at,
    updatedAt: collection.updated_at,
  };
}

assert.equal(computeCollectionProgressPercent(0, 0), 0);
assert.equal(computeCollectionProgressPercent(7, 5), 71);
assert.equal(computeCollectionProgressPercent(29, 6), 21);

const mixed = mapApiCollectionToListItem({
  id: "c1",
  name: "드래곤볼",
  item_count: 29,
  planned_count: 23,
  completed_count: 6,
  categories: [
    { id: "a", name: "애니메이션", item_count: 13 },
    { id: "b", name: "애니 영화", item_count: 9 },
    { id: "c", name: "만화책", item_count: 7 },
  ],
  created_at: "2026-07-21T00:00:00+00:00",
  updated_at: "2026-07-21T00:00:00+00:00",
});

assert.equal(mixed.itemCount, 29);
assert.equal(mixed.categories.length, 3);
assert.equal(mixed.averageRating, null);
assert.equal(
  mixed.categories.reduce((sum, c) => sum + c.itemCount, 0),
  mixed.itemCount,
);

const empty = mapApiCollectionToListItem({
  id: "c0",
  name: "빈",
  item_count: 0,
  planned_count: 0,
  completed_count: 0,
  categories: [],
  created_at: "2026-07-21T00:00:00+00:00",
  updated_at: "2026-07-21T00:00:00+00:00",
});
assert.equal(empty.progressPercent, 0);
assert.deepEqual(empty.categories, []);

console.log("verify-collections-mapper: ok");
