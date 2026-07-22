/**
 * DELETE API client checks without a Frontend test framework.
 * Run: node scripts/verify-delete-api.mjs
 */
import assert from "node:assert/strict";

const API_BASE = "/api/v1";

function joinUrl(base, path) {
  const normalizedPath = path.startsWith("/") ? path : `/${path}`;
  return `${base}${normalizedPath}`;
}

class ApiError extends Error {
  constructor(status, message, detail) {
    super(message);
    this.name = "ApiError";
    this.status = status;
    this.detail = detail;
  }
}

async function apiRequest(path, options) {
  const response = await fetch(joinUrl(API_BASE, path), options);
  if (response.ok) {
    if (response.status === 204) {
      return undefined;
    }
    return response.json();
  }
  throw new ApiError(response.status, `Request failed (${response.status})`);
}

async function deleteItem(itemId) {
  return apiRequest(`/items/${encodeURIComponent(itemId)}`, {
    method: "DELETE",
  });
}

async function deleteCollection(collectionId) {
  return apiRequest(`/collections/${encodeURIComponent(collectionId)}`, {
    method: "DELETE",
  });
}

let lastUrl;
let lastInit;
let jsonCalled = false;
let nextStatus = 204;

globalThis.fetch = async (url, init) => {
  lastUrl = url;
  lastInit = init;
  jsonCalled = false;
  return {
    ok: nextStatus >= 200 && nextStatus < 300,
    status: nextStatus,
    headers: new Headers(),
    json: async () => {
      jsonCalled = true;
      return {};
    },
  };
};

nextStatus = 204;
const itemResult = await deleteItem("item-uuid");
assert.equal(itemResult, undefined);
assert.equal(lastInit.method, "DELETE");
assert.match(lastUrl, /\/api\/v1\/items\/item-uuid$/);
assert.equal(jsonCalled, false);

nextStatus = 204;
const collectionResult = await deleteCollection("col/id");
assert.equal(collectionResult, undefined);
assert.match(lastUrl, /\/api\/v1\/collections\/col%2Fid$/);
assert.equal(jsonCalled, false);

nextStatus = 404;
await assert.rejects(deleteItem("missing"), (err) => {
  assert.equal(err.status, 404);
  return true;
});

nextStatus = 409;
await assert.rejects(deleteCollection("busy"), (err) => {
  assert.equal(err.status, 409);
  return true;
});

console.log("verify-delete-api: ok");
