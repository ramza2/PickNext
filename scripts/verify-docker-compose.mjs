import fs from "node:fs";
import path from "node:path";
import { fileURLToPath } from "node:url";

const __dirname = path.dirname(fileURLToPath(import.meta.url));
const root = path.resolve(__dirname, "..");

function fail(message) {
  console.error(`verify-docker-compose: FAIL — ${message}`);
  process.exit(1);
}

function ok(message) {
  console.log(`verify-docker-compose: ${message}`);
}

function read(rel) {
  return fs.readFileSync(path.join(root, rel), "utf8");
}

const basePath = ["compose.yaml", "compose.yml", "docker-compose.yml"].find(
  (name) => fs.existsSync(path.join(root, name)),
);
if (!basePath) fail("base compose file not found");

const localPath = ["compose.local.yaml", "docker-compose.local.yml"].find(
  (name) => fs.existsSync(path.join(root, name)),
);
if (!localPath) fail("local override compose file not found");

const base = read(basePath);
const local = read(localPath);

if (!/^\s*frontend:\s*$/m.test(base)) fail(`${basePath} missing frontend service`);
ok(`frontend service in ${basePath}`);

if (!/context:\s*\.\/frontend/.test(base)) fail("frontend build context must be ./frontend");
if (!/dockerfile:\s*Dockerfile/.test(base)) fail("frontend must use Dockerfile");
ok("frontend Dockerfile build");

if (!/VITE_API_BASE_URL:\s*\$\{VITE_API_BASE_URL:-\/api\/v1\}/.test(base)) {
  fail("VITE_API_BASE_URL default must be /api/v1");
}
ok("VITE_API_BASE_URL default /api/v1");

const frontendMatch = base.match(
  /^ {2}frontend:\r?\n([\s\S]*?)(?=^ {2}[a-zA-Z0-9_-]+:|^\s*volumes:)/m,
);
const frontendBlock = frontendMatch?.[1] ?? "";
if (!frontendBlock) fail("could not parse frontend service block");

if (/^ {4}ports:\s*$/m.test(frontendBlock)) {
  fail("base compose frontend must not publish host ports");
}
ok("base frontend has no host ports");

if (!/healthcheck:/m.test(frontendBlock)) fail("frontend healthcheck missing");
if (!/\/health/.test(frontendBlock)) fail("frontend healthcheck must hit /health");
ok("frontend healthcheck");

if (/depends_on:/m.test(frontendBlock)) {
  fail("frontend must not depend_on backend/postgres");
}
ok("frontend has no depends_on");

if (/traefik\./i.test(base) || /traefik\./i.test(local)) {
  fail("Traefik labels must not be present (DPL-3)");
}
ok("no Traefik labels");

if (/proxy:\s*[\s\S]*external:\s*true/.test(base) || /proxy:\s*[\s\S]*external:\s*true/.test(local)) {
  fail("external proxy network must not be present (DPL-3)");
}
ok("no external proxy network");

if (!/127\.0\.0\.1:\$\{PICKNEXT_FRONTEND_PORT:-5183\}:80/.test(local)) {
  fail("local override must bind frontend to 127.0.0.1:5183");
}
ok("local frontend loopback port");

if (!/ports:\s*!override/.test(local)) {
  fail("local override should !override postgres/backend ports for isolation");
}
ok("local port overrides present");

console.log("verify-docker-compose: ok");
console.log(
  "verify-docker-compose: note — run `docker compose -f compose.yaml -f compose.local.yaml config` for merge validation",
);
