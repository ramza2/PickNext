/**
 * Static checks for UI quick actions, search clear control, and desktop nav order.
 * Run: node scripts/verify-ui-quick-actions-nav.mjs
 */
import assert from "node:assert/strict";
import fs from "node:fs";
import path from "node:path";
import { fileURLToPath } from "node:url";

const root = path.resolve(path.dirname(fileURLToPath(import.meta.url)), "..");
const read = (relative) => fs.readFileSync(path.join(root, relative), "utf8");

const app = read("src/app/App.tsx");
const quickMenu = read("src/app/components/ItemQuickActionsMenu.tsx");
const clearable = read("src/app/components/ClearableSearchInput.tsx");
const appLayout = read("src/app/layout/AppLayout.tsx");
const navOrder = read("src/app/layout/navigationOrder.ts");
const navSettings = read("src/app/layout/NavigationOrderSettings.tsx");
const history = read("src/navigation/history.ts");

// Browser-native search cancel must not render beside the custom clear button.
assert.match(clearable, /type="text"/);
assert.match(clearable, /inputMode="search"/);
assert.doesNotMatch(clearable, /type="search"/);
assert.match(clearable, /<X size=\{16\}/);

// Items list ellipsis is a real menu with exactly the intended quick actions.
assert.match(app, /ItemQuickActionsMenu/);
assert.match(quickMenu, />\s*수정\s*</);
assert.match(quickMenu, /완료 처리/);
assert.match(quickMenu, /볼 예정으로 변경/);
assert.match(quickMenu, />\s*삭제\s*</);
assert.doesNotMatch(app, /<MoreVertical/);
assert.match(app, /handleQuickStatusToggle/);
assert.match(app, /handleQuickDeleteConfirm/);
assert.match(app, /openQuickEditItem/);

// Quick edit from the list participates in the existing history overlay contract.
assert.match(app, /returnToItemsList/);
assert.match(app, /openOverlay\(\{ type: "item-edit", itemId: item\.id \}\)/);
assert.match(history, /overlay\.type === "item-edit"/);
assert.match(history, /route\.name === "items"/);

// Requested desktop default order.
const orderedIds = [
  '"home"',
  '"items"',
  '"collections"',
  '"search"',
  '"recommend"',
  '"history"',
  '"settings"',
];
let previous = -1;
for (const id of orderedIds) {
  const current = navOrder.indexOf(id, previous + 1);
  assert.ok(current > previous, `desktop nav order missing/out of order: ${id}`);
  previous = current;
}

// User-specific persistence + settings controls.
assert.match(navOrder, /picknext\.nav-order\.v1:/);
assert.match(navOrder, /localStorage\.setItem/);
assert.match(navSettings, /메뉴 순서/);
assert.match(navSettings, /위로 이동/);
assert.match(navSettings, /아래로 이동/);
assert.match(navSettings, /기본 순서/);
assert.match(appLayout, /desktopNavOrder/);

// Mobile navigation intentionally stays fixed.
assert.match(
  appLayout,
  /const MOBILE_PRIMARY:[\s\S]*NAV_BY_ID\.home,[\s\S]*NAV_BY_ID\.recommend,[\s\S]*NAV_BY_ID\.items/,
);

console.log("verify-ui-quick-actions-nav: ok");
