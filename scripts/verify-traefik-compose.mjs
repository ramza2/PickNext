import fs from "node:fs";
import path from "node:path";
import { fileURLToPath } from "node:url";

const __dirname = path.dirname(fileURLToPath(import.meta.url));
const root = path.resolve(__dirname, "..");

function fail(message) {
  console.error(`verify-traefik-compose: FAIL — ${message}`);
  process.exit(1);
}

function ok(message) {
  console.log(`verify-traefik-compose: ${message}`);
}

const traefikPath = path.join(root, "compose.traefik.yaml");
if (!fs.existsSync(traefikPath)) fail("compose.traefik.yaml missing");
const src = fs.readFileSync(traefikPath, "utf8");

function mustFile(label, pattern) {
  if (!pattern.test(src)) fail(label);
  ok(label);
}

if (!/^\s{2}frontend:\s*$/m.test(src)) fail("frontend service missing");
if (!/^\s{2}backend:\s*$/m.test(src)) fail("backend service missing");
if (!/^\s{2}postgres:\s*$/m.test(src)) fail("postgres service missing");

mustFile("frontend traefik.enable", /frontend:[\s\S]*traefik\.enable=true/);
mustFile(
  "frontend traefik.docker.network=proxy",
  /frontend:[\s\S]*traefik\.docker\.network=proxy/,
);
mustFile("frontend picknext-web router", /picknext-web/);
mustFile(
  "frontend Host var + default",
  /Host\(`\$\{PICKNEXT_HOST:-picknext\.ramza\.duckdns\.org\}`\)/,
);
mustFile("frontend entrypoints=websecure", /picknext-web\.entrypoints=websecure/);
mustFile("frontend tls=true", /picknext-web\.tls=true/);
mustFile(
  "frontend certresolver=myresolver",
  /picknext-web\.tls\.certresolver=myresolver/,
);
mustFile("frontend priority=10", /picknext-web\.priority=10/);
mustFile(
  "frontend service port 80",
  /picknext-web-service\.loadbalancer\.server\.port=80/,
);
mustFile(
  "frontend default+proxy networks",
  /frontend:[\s\S]*networks:[\s\S]*- default[\s\S]*- proxy/,
);

mustFile("backend traefik.enable", /backend:[\s\S]*traefik\.enable=true/);
mustFile(
  "backend traefik.docker.network=proxy",
  /backend:[\s\S]*traefik\.docker\.network=proxy/,
);
mustFile("backend picknext-api router", /picknext-api/);
mustFile(
  "backend /api rule",
  /Path\(`\/api`\).*PathPrefix\(`\/api\/`\)|PathPrefix\(`\/api\/`\).*Path\(`\/api`\)/,
);
mustFile("backend entrypoints=websecure", /picknext-api\.entrypoints=websecure/);
mustFile("backend tls=true", /picknext-api\.tls=true/);
mustFile(
  "backend certresolver=myresolver",
  /picknext-api\.tls\.certresolver=myresolver/,
);
mustFile("backend priority=100", /picknext-api\.priority=100/);
mustFile(
  "backend service port 8000",
  /picknext-api-service\.loadbalancer\.server\.port=8000/,
);
mustFile(
  "backend default+proxy networks",
  /backend:[\s\S]*networks:[\s\S]*- default[\s\S]*- proxy/,
);

{
  const beforeNetworks = src.split(/^networks:/m)[0];
  const pg =
    beforeNetworks.match(/^ {2}postgres:\r?\n([\s\S]*?)(?=^ {2}[a-zA-Z])/m)?.[1] ??
    "";
  if (/traefik\./i.test(pg)) fail("postgres must not have Traefik labels");
  if (/^\s*-\s*proxy\s*$/m.test(pg) || /networks:[\s\S]*proxy/.test(pg)) {
    fail("postgres must not join proxy network");
  }
}
ok("postgres no Traefik labels");
ok("postgres no proxy network");

if (/^\s*[^#\n]*StripPrefix|^\s*[^#\n]*ReplacePath/im.test(src)) {
  fail("StripPrefix / ReplacePath must not be used");
}
ok("no StripPrefix");

if (/5183|8012|15432/.test(src)) {
  fail("Traefik overlay must not include local loopback ports (5183/8012/15432)");
}
ok("no local host ports in Traefik overlay");

if (!/proxy:[\s\S]*external:\s*true[\s\S]*name:\s*proxy/.test(src)) {
  fail("external proxy network named proxy required");
}
ok("external proxy network");

console.log("verify-traefik-compose: ok");
console.log(
  "verify-traefik-compose: note — run `docker compose -f compose.yaml -f compose.traefik.yaml config` for merge validation",
);
