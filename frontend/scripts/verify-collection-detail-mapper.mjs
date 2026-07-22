/**
 * Collection detail mapper / Item query contract checks.
 * Run: node scripts/verify-collection-detail-mapper.mjs
 */
import assert from "node:assert/strict";

function computeCollectionProgressPercent(itemCount, completedCount) {
  if (!Number.isFinite(itemCount) || itemCount <= 0) return 0;
  if (!Number.isFinite(completedCount) || completedCount <= 0) return 0;
  return Math.round((completedCount / itemCount) * 100);
}

function mapApiCollectionToDetail(collection) {
  return {
    id: collection.id,
    name: collection.name,
    itemCount: collection.item_count,
    plannedCount: collection.planned_count,
    completedCount: collection.completed_count,
    categories: collection.categories.map((c) => ({
      id: c.id,
      name: c.name,
      itemCount: c.item_count,
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

function buildCollectionItemsQueryParams(collectionId, page) {
  return {
    collection_id: collectionId,
    sort: "title",
    order: "asc",
    page,
  };
}

function resolveCollectionReturnState(selection) {
  if (selection?.origin !== "collections" || !selection.collectionId) {
    return null;
  }
  return {
    collectionId: selection.collectionId,
    itemsPage: selection.collectionItemsPage ?? 1,
  };
}

assert.equal(computeCollectionProgressPercent(0, 0), 0);
assert.equal(computeCollectionProgressPercent(29, 6), 21);

const detail = mapApiCollectionToDetail({
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
  updated_at: "2026-07-21T01:00:00+00:00",
});
assert.equal(detail.categories.length, 3);
assert.equal(detail.averageRating, null);
assert.equal(detail.createdAt, "2026-07-21T00:00:00+00:00");
assert.equal(
  detail.categories.reduce((s, c) => s + c.itemCount, 0),
  detail.itemCount,
);

const empty = mapApiCollectionToDetail({
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

const params = buildCollectionItemsQueryParams("col-1", 2);
assert.equal(params.collection_id, "col-1");
assert.equal(params.sort, "title");
assert.equal(params.order, "asc");
assert.equal(params.page, 2);
assert.equal("page_size" in params, false);

assert.deepEqual(
  resolveCollectionReturnState({
    itemId: "i1",
    origin: "collections",
    collectionId: "col-1",
    collectionItemsPage: 2,
  }),
  { collectionId: "col-1", itemsPage: 2 },
);
assert.equal(
  resolveCollectionReturnState({ itemId: "i1", origin: "items" }),
  null,
);

console.log("verify-collection-detail-mapper: ok");
