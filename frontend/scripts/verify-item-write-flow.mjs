/**
 * Static checks for Item write UI wiring (string/flow heuristics).
 * Run: node scripts/verify-item-write-flow.mjs
 */
import assert from "node:assert/strict";
import fs from "node:fs";
import path from "node:path";
import { fileURLToPath } from "node:url";

const root = path.resolve(path.dirname(fileURLToPath(import.meta.url)), "..");
const appPath = path.join(root, "src/app/App.tsx");
const catalogPath = path.join(root, "src/api/catalog.ts");
const messagesPath = path.join(root, "src/api/itemWriteMessages.ts");

const app = fs.readFileSync(appPath, "utf8");
const catalog = fs.readFileSync(catalogPath, "utf8");
const messages = fs.readFileSync(messagesPath, "utf8");

assert.match(catalog, /export function createItem\(/);
assert.match(catalog, /export function updateItem\(/);
assert.match(catalog, /method:\s*"POST"/);
assert.match(catalog, /method:\s*"PATCH"/);
assert.match(catalog, /getAllCollectionsForSelect/);

assert.match(messages, /buildItemUpdatePayload/);
assert.match(messages, /collection_id/);
assert.match(messages, /progress_note/);
assert.match(messages, /memo/);

assert.match(app, /function ItemFormModal/);
assert.match(app, /createItem\(/);
assert.match(app, /updateItem\(/);
assert.match(app, /openCreateItem/);
assert.match(app, /openEditItem/);
assert.match(app, /lockedCollection/);
assert.match(app, /buildItemUpdatePayload/);
assert.match(app, /Object\.keys\(payload\)\.length === 0/);
assert.match(app, /handleStatusToggle/);
assert.match(app, /항목을 추가했습니다/);
assert.match(app, /항목을 수정했습니다/);

// Collection row "제거" = PATCH collection_id:null (not deleteItem).
assert.match(app, /handleUnlinkConfirm/);
assert.match(app, /컬렉션에서 항목 제거/);
assert.doesNotMatch(app, /컬렉션에서 항목 제거 기능은 아직 지원하지 않습니다/);
const unlinkIdx = app.indexOf("handleUnlinkConfirm");
assert.ok(unlinkIdx > 0);
const unlinkWindow = app.slice(unlinkIdx, unlinkIdx + 900);
assert.match(unlinkWindow, /collection_id:\s*null/);
assert.match(unlinkWindow, /updateItem\(/);
assert.doesNotMatch(unlinkWindow, /deleteItem\(/);

assert.match(app, /직접 추가/);
assert.match(app, /완료 처리/);
assert.match(app, /볼 예정으로 변경/);

// Items list checkbox must be controlled with onChange (not click-only).
const cardCheckboxIdx = app.indexOf("checked={selected.has(item.id)}");
assert.ok(cardCheckboxIdx > 0, "Items Card checkbox missing");
const cardCheckboxWindow = app.slice(cardCheckboxIdx, cardCheckboxIdx + 280);
assert.match(cardCheckboxWindow, /onChange=\{/);
assert.doesNotMatch(cardCheckboxWindow, /onChange=\{\(\)\s*=>\s*\{\s*\}\}/);

// Item Form field-level validation UX.
assert.match(messages, /collectItemFormFieldErrors/);
assert.match(messages, /hasItemFormFieldErrors/);
assert.match(messages, /ItemFormFieldErrors/);
assert.match(app, /collectItemFormFieldErrors/);
assert.match(app, /fieldErrors\.title/);
assert.match(app, /fieldErrors\.categoryId/);
assert.match(app, /fieldErrors\.progressNote/);
assert.match(app, /titleErrorId|item-form-title-error/);
assert.match(app, /categoryErrorId|item-form-category-error/);
assert.match(app, /progressErrorId|item-form-progress-error/);
assert.match(app, /focusFirstFieldError/);
assert.match(app, /role="alert"/);

console.log("verify-item-write-flow: ok");
