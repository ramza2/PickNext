import fs from "node:fs";
import path from "node:path";
import { fileURLToPath } from "node:url";

const __dirname = path.dirname(fileURLToPath(import.meta.url));
const root = path.resolve(__dirname, "..");

function fail(message) {
  console.error(`verify-pwa-build: FAIL — ${message}`);
  process.exit(1);
}

function ok(message) {
  console.log(`verify-pwa-build: ${message}`);
}

function read(rel) {
  return fs.readFileSync(path.join(root, rel), "utf8");
}

function exists(rel) {
  return fs.existsSync(path.join(root, rel));
}

const viteConfig = read("vite.config.ts");
if (!viteConfig.includes("VitePWA")) fail("vite.config.ts missing VitePWA");
if (!/registerType:\s*['"]prompt['"]/.test(viteConfig)) {
  fail("registerType must be prompt");
}
if (!/devOptions:\s*\{[\s\S]*enabled:\s*false/.test(viteConfig)) {
  fail("devOptions.enabled must be false");
}
if (
  !viteConfig.includes("navigateFallbackDenylist") ||
  !/\\\/api/.test(viteConfig)
) {
  fail("navigateFallbackDenylist must include /api");
}
ok("vite.config PWA policy");

const promptSrc = read("src/app/components/PwaUpdatePrompt.tsx");
if (!promptSrc.includes("useRegisterSW")) fail("PwaUpdatePrompt missing useRegisterSW");
if (!promptSrc.includes("updateServiceWorker(true)")) {
  fail("PwaUpdatePrompt missing updateServiceWorker(true)");
}
if (!promptSrc.includes("setNeedRefresh(false)")) {
  fail("PwaUpdatePrompt missing later dismiss (setNeedRefresh(false))");
}
const appSrc = read("src/app/App.tsx");
if (!appSrc.includes("<PwaUpdatePrompt")) fail("App.tsx must mount PwaUpdatePrompt");
ok("update prompt wiring");

const requiredPublic = [
  "public/pwa-source.svg",
  "public/pwa-64x64.png",
  "public/pwa-192x192.png",
  "public/pwa-512x512.png",
  "public/maskable-icon-512x512.png",
  "public/apple-touch-icon-180x180.png",
  "public/favicon.ico",
];
for (const file of requiredPublic) {
  if (!exists(file)) fail(`missing ${file}`);
}
ok("public PWA assets");

const distDir = path.join(root, "dist");
if (!fs.existsSync(distDir)) {
  fail("dist/ missing — run npm run build first");
}

const requiredDist = [
  "dist/index.html",
  "dist/manifest.webmanifest",
  "dist/sw.js",
  "dist/pwa-192x192.png",
  "dist/pwa-512x512.png",
  "dist/maskable-icon-512x512.png",
  "dist/apple-touch-icon-180x180.png",
  "dist/favicon.ico",
];
for (const file of requiredDist) {
  if (!exists(file)) fail(`missing ${file}`);
}

const swFiles = fs.readdirSync(distDir).filter((name) => /^workbox-.*\.js$/.test(name));
if (swFiles.length === 0 && !exists("dist/registerSW.js")) {
  // registerSW.js is optional naming; sw.js is required above
  ok("workbox bundle optional-name check skipped (sw.js present)");
} else {
  ok(`service worker artifacts (${swFiles.join(", ") || "sw.js"})`);
}

const manifest = JSON.parse(read("dist/manifest.webmanifest"));
if (manifest.name !== "PickNext" || manifest.short_name !== "PickNext") {
  fail("manifest name/short_name");
}
if (manifest.id !== "/" || manifest.start_url !== "/" || manifest.scope !== "/") {
  fail("manifest id/start_url/scope");
}
if (manifest.display !== "standalone") fail("manifest display");
if (manifest.lang !== "ko-KR") fail("manifest lang");
if (!manifest.theme_color || !manifest.background_color) {
  fail("manifest theme/background color");
}

const icons = manifest.icons || [];
const has192 = icons.some((i) => i.sizes === "192x192");
const has512 = icons.some((i) => i.sizes === "512x512" && (!i.purpose || String(i.purpose).includes("any")));
const hasMaskable = icons.some(
  (i) => i.sizes === "512x512" && String(i.purpose || "").includes("maskable"),
);
if (!has192 || !has512 || !hasMaskable) fail("manifest icons 192/512/maskable");
ok("manifest.webmanifest");

const sw = read("dist/sw.js");
if (/BackgroundSyncPlugin|workbox-background-sync/.test(sw)) {
  fail("Background Sync must not be configured");
}
if (!sw.includes("precache") && !sw.includes("Precache") && !sw.includes("precacheAndRoute")) {
  // minified may still include precacheAndRoute string
  if (!/precache/i.test(sw)) fail("sw.js missing precache");
}
ok("sw.js policy checks");

console.log("verify-pwa-build: ok");
