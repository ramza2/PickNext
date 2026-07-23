import fs from "node:fs";
import path from "node:path";
import { fileURLToPath } from "node:url";

const __dirname = path.dirname(fileURLToPath(import.meta.url));
const root = path.resolve(__dirname, "..");
const nginxPath = path.join(root, "nginx.conf");

function fail(message) {
  console.error(`verify-pwa-nginx: FAIL — ${message}`);
  process.exit(1);
}

function ok(message) {
  console.log(`verify-pwa-nginx: ${message}`);
}

const conf = fs.readFileSync(nginxPath, "utf8");

function mustInclude(label, pattern) {
  if (!pattern.test(conf)) fail(label);
  ok(label);
}

mustInclude(
  "manifest.webmanifest exact location",
  /location\s*=\s*\/manifest\.webmanifest\s*\{/,
);
mustInclude(
  "manifest MIME application/manifest+json",
  /default_type\s+application\/manifest\+json;/,
);
mustInclude(
  "manifest no-cache",
  /location\s*=\s*\/manifest\.webmanifest[\s\S]*?Cache-Control\s+"no-cache,\s*must-revalidate"/,
);

mustInclude("sw.js exact location", /location\s*=\s*\/sw\.js\s*\{/);
mustInclude(
  "sw.js no-store cache",
  /location\s*=\s*\/sw\.js[\s\S]*?Cache-Control\s+"[^"]*no-store[^"]*no-cache[^"]*max-age=0"/,
);

const hasRegisterLocation = /location\s*=\s*\/registerSW\.js\s*\{/.test(conf);
const registerExists = fs.existsSync(path.join(root, "dist", "registerSW.js"));
if (registerExists && !hasRegisterLocation) {
  fail("dist/registerSW.js exists but nginx location missing");
}
if (!registerExists && hasRegisterLocation) {
  fail("registerSW.js location present but file not in build");
}
ok(
  registerExists
    ? "registerSW.js location present"
    : "registerSW.js absent — location correctly omitted",
);

mustInclude(
  "workbox hash long-term immutable",
  /location\s*~\s*\^\/workbox-[^\{]+\{[\s\S]*?max-age=31536000,\s*immutable/,
);

mustInclude(
  "PWA icon short cache",
  /location\s*~\s*\^\/\(pwa-[\s\S]*?max-age=86400,\s*must-revalidate/,
);

mustInclude(
  "/assets immutable",
  /location\s*\/assets\/\s*\{[\s\S]*?max-age=31536000,\s*immutable/,
);

mustInclude(
  "index.html no-store",
  /location\s*=\s*\/index\.html[\s\S]*?no-store,\s*no-cache,\s*must-revalidate/,
);

mustInclude(
  "SPA fallback try_files",
  /location\s*\/\s*\{[\s\S]*?try_files\s+\$uri\s+\$uri\/\s+\/index\.html;/,
);

mustInclude("health location", /location\s*=\s*\/health\s*\{/);

if (/location\s*~\s*\^\/workbox[\s\S]*sw\.js/.test(conf)) {
  fail("workbox regex must not include sw.js");
}

console.log("verify-pwa-nginx: ok");
console.log(
  "verify-pwa-nginx: note — static config check only; Docker curl smoke is authoritative for headers",
);
