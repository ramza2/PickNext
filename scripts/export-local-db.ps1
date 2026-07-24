#Requires -Version 5.1
<#
.SYNOPSIS
  Export local PickNext PostgreSQL to custom-format dump + manifest + SHA-256.

.DESCRIPTION
  Read-only against the local DB (SELECT / pg_dump / pg_restore --list only).
  Does not print passwords, SECRET_KEY, or TMDB tokens.

  Default Compose file is compose.yaml (the stack that holds Seed/RC data).
  Pass -UseLocalOverride only when the intentional target is the DPL-2 overlay.

.EXAMPLE
  powershell -File scripts/export-local-db.ps1
#>
[CmdletBinding()]
param(
    [switch]$UseLocalOverride,
    [string]$TransferRoot = (Join-Path $env:TEMP "picknext-db-transfer"),
    [string]$SeedEmailExpected = "jchramza@gmail.com"
)

Set-StrictMode -Version Latest
$ErrorActionPreference = "Stop"

function Write-Info([string]$Message) {
    Write-Host $Message
}

function Get-EnvValue([string]$Key) {
    $path = Join-Path (Get-Location) ".env"
    if (-not (Test-Path $path)) {
        return $null
    }
    foreach ($line in Get-Content -Path $path) {
        if ($line -match '^\s*#' -or $line -match '^\s*$') { continue }
        $parts = $line -split "=", 2
        if ($parts.Count -lt 2) { continue }
        if ($parts[0].Trim() -eq $Key) {
            return $parts[1].Trim()
        }
    }
    return $null
}

function Invoke-Compose {
    param([Parameter(ValueFromRemainingArguments = $true)][string[]]$ComposeArgs)
    & docker @("compose") @script:ComposeFileArgs @ComposeArgs
    if ($LASTEXITCODE -ne 0) {
        throw "docker compose $($ComposeArgs -join ' ') failed with exit $LASTEXITCODE"
    }
}

$RepoRoot = (Resolve-Path (Join-Path $PSScriptRoot "..")).Path
Set-Location $RepoRoot

if (-not (Test-Path (Join-Path $RepoRoot "compose.yaml"))) {
    throw "compose.yaml not found. Run from PickNext repo."
}

$ComposeFileArgs = @("-f", "compose.yaml")
if ($UseLocalOverride) {
    if (-not (Test-Path (Join-Path $RepoRoot "compose.local.yaml"))) {
        throw "compose.local.yaml not found."
    }
    $ComposeFileArgs += @("-f", "compose.local.yaml")
    Write-Info "Using compose.yaml + compose.local.yaml"
}
else {
    Write-Info "Using compose.yaml (default local Seed/RC stack)"
}

Write-Info "===== local postgres status ====="
Invoke-Compose @("ps")

$PostgresContainer = ((& docker @("compose") @ComposeFileArgs @("ps", "-q", "postgres")) | Out-String).Trim()
if ([string]::IsNullOrWhiteSpace($PostgresContainer)) {
    throw "Local PostgreSQL container was not found. Start the existing stack first (do not create a new volume)."
}

$DbName = Get-EnvValue "POSTGRES_DB"
if ([string]::IsNullOrWhiteSpace($DbName)) { $DbName = "picknext" }
$SeedEmailLocal = Get-EnvValue "SEED_USER_EMAIL"
if ([string]::IsNullOrWhiteSpace($SeedEmailLocal)) {
    throw "SEED_USER_EMAIL missing from .env"
}
if ($SeedEmailLocal -ne $SeedEmailExpected) {
    throw "SEED_USER_EMAIL in .env ('$SeedEmailLocal') != expected ('$SeedEmailExpected')"
}

Write-Info "===== identify database ====="
& docker exec $PostgresContainer `
    psql -U picknext -d $DbName -v ON_ERROR_STOP=1 `
    -c "SELECT current_database() AS db, current_user AS usr;" `
    -c "SHOW server_version;"
if ($LASTEXITCODE -ne 0) { throw "psql identify failed" }

$PgMajor = (
    & docker exec $PostgresContainer `
        sh -lc "psql --version" |
        Select-String -Pattern '([0-9]+)\.' |
        ForEach-Object { $_.Matches[0].Groups[1].Value }
)
if ([string]::IsNullOrWhiteSpace($PgMajor)) {
    throw "Could not parse PostgreSQL major version"
}

Write-Info "===== tables ====="
$Tables = & docker exec $PostgresContainer `
    psql -U picknext -d $DbName -At `
    -c "SELECT tablename FROM pg_tables WHERE schemaname = 'public' ORDER BY tablename;"
if ($LASTEXITCODE -ne 0) { throw "table list failed" }
$Tables | ForEach-Object { Write-Info "  $_" }

foreach ($required in @("users", "categories", "collections", "items", "alembic_version")) {
    if ($Tables -notcontains $required) {
        throw "Required table missing: $required"
    }
}

Write-Info "===== alembic ====="
$AlembicCurrent = (
    & docker @("compose") @ComposeFileArgs @("exec", "-T", "backend", "alembic", "current") 2>&1 |
        Where-Object { $_ -match '^\S' -and $_ -notmatch '^INFO' } |
        Select-Object -First 1
)
$AlembicCurrent = ("$AlembicCurrent" -replace '\s*\(head\)\s*$', '').Trim()
$AlembicHeads = (
    & docker @("compose") @ComposeFileArgs @("exec", "-T", "backend", "alembic", "heads") 2>&1 |
        Where-Object { $_ -match '^\S' -and $_ -notmatch '^INFO' } |
        Select-Object -First 1
)
$AlembicHeads = ("$AlembicHeads" -replace '\s*\(head\)\s*$', '').Trim()
Write-Info "alembic current=$AlembicCurrent"
Write-Info "alembic heads=$AlembicHeads"
if ([string]::IsNullOrWhiteSpace($AlembicCurrent) -or $AlembicCurrent -ne $AlembicHeads) {
    throw "Alembic current != heads (will not dump / will not migrate)."
}

Write-Info "===== counts ====="
$CountSql = @"
SELECT
  (SELECT COUNT(*) FROM users) AS users,
  (SELECT COUNT(*) FROM categories) AS categories,
  (SELECT COUNT(*) FROM collections) AS collections,
  (SELECT COUNT(*) FROM items) AS items,
  (SELECT COUNT(*) FROM recommendation_history) AS histories,
  (SELECT COUNT(*) FROM recommendation_history_items) AS history_items,
  (SELECT COUNT(*) FROM legacy_import_runs) AS legacy_runs,
  (SELECT COUNT(*) FROM legacy_import_items) AS legacy_items,
  (SELECT COUNT(*) FROM legacy_import_collections) AS legacy_collections;
"@
$CountLine = (
    & docker exec $PostgresContainer `
        psql -U picknext -d $DbName -At -F "|" `
        -c $CountSql
).Trim()
if ($LASTEXITCODE -ne 0 -or [string]::IsNullOrWhiteSpace($CountLine)) {
    throw "count query failed"
}
$Counts = $CountLine -split "\|"
if ($Counts.Count -lt 9) { throw "unexpected count columns: $CountLine" }

$Users = [int]$Counts[0]
$Categories = [int]$Counts[1]
$Collections = [int]$Counts[2]
$Items = [int]$Counts[3]
$Histories = [int]$Counts[4]
$HistoryItems = [int]$Counts[5]
$LegacyRuns = [int]$Counts[6]
$LegacyItems = [int]$Counts[7]
$LegacyCollections = [int]$Counts[8]

Write-Info "users=$Users categories=$Categories collections=$Collections items=$Items"
Write-Info "histories=$Histories history_items=$HistoryItems"
Write-Info "legacy_runs=$LegacyRuns legacy_items=$LegacyItems legacy_collections=$LegacyCollections"

if ($Collections -le 0 -or $Items -le 0) {
    throw "collections/items empty — refusing to dump (wrong DB?)."
}

Write-Info "===== users (no password_hash) ====="
& docker exec $PostgresContainer `
    psql -U picknext -d $DbName -v ON_ERROR_STOP=1 `
    -c "SELECT id, email, display_name, is_active FROM users ORDER BY created_at, id;"
if ($LASTEXITCODE -ne 0) { throw "users query failed" }

$SeedCount = (
    & docker exec $PostgresContainer `
        psql -U picknext -d $DbName -At `
        -c "SELECT COUNT(*) FROM users WHERE email = '$SeedEmailExpected';"
).Trim()
if ($SeedCount -ne "1") {
    throw "SEED user email count must be 1, got $SeedCount"
}

Write-Info "===== image/path columns ====="
$pathCols = & docker exec $PostgresContainer `
    psql -U picknext -d $DbName -At -F "|" `
    -c @"
SELECT table_name || '.' || column_name
FROM information_schema.columns
WHERE table_schema = 'public'
  AND (
    column_name ILIKE '%path%'
    OR column_name ILIKE '%url%'
    OR column_name ILIKE '%image%'
    OR column_name ILIKE '%poster%'
    OR column_name ILIKE '%file%'
    OR column_name ILIKE '%thumb%'
  )
ORDER BY 1;
"@
if ($pathCols) {
    $pathCols | ForEach-Object { Write-Info "  $_" }
}
else {
    Write-Info "  (none)"
}

New-Item -ItemType Directory -Path $TransferRoot -Force | Out-Null
$Timestamp = Get-Date -Format "yyyyMMdd-HHmmss"
$DumpName = "picknext-local-$Timestamp.dump"
$DumpPath = Join-Path $TransferRoot $DumpName
$ManifestPath = Join-Path $TransferRoot "picknext-local-$Timestamp.manifest.env"
$ChecksumPath = Join-Path $TransferRoot "picknext-local-$Timestamp.sha256"

Write-Info "===== pg_dump (custom) via container /tmp + docker cp ====="
& docker exec $PostgresContainer sh -lc @'
set -eu
rm -f /tmp/picknext-local.dump
pg_dump \
  -U "$POSTGRES_USER" \
  -d "$POSTGRES_DB" \
  --format=custom \
  --no-owner \
  --no-privileges \
  --file=/tmp/picknext-local.dump
test -s /tmp/picknext-local.dump
'@
if ($LASTEXITCODE -ne 0) { throw "pg_dump failed" }

& docker cp "${PostgresContainer}:/tmp/picknext-local.dump" $DumpPath
if ($LASTEXITCODE -ne 0) { throw "docker cp dump failed" }
& docker exec $PostgresContainer rm -f /tmp/picknext-local.dump

$DumpFile = Get-Item $DumpPath
if ($DumpFile.Length -le 0) { throw "Database dump is empty." }
Write-Info "dump=$($DumpFile.FullName)"
Write-Info "size=$($DumpFile.Length)"
Write-Info "mtime=$($DumpFile.LastWriteTime.ToString('o'))"

Write-Info "===== pg_restore --list ====="
& docker cp $DumpPath "${PostgresContainer}:/tmp/picknext-local-check.dump"
& docker exec $PostgresContainer sh -lc @'
set -eu
pg_restore --list /tmp/picknext-local-check.dump > /tmp/picknext-local-check.list
grep -E "TABLE .* users$" /tmp/picknext-local-check.list
grep -E "TABLE .* categories$" /tmp/picknext-local-check.list
grep -E "TABLE .* collections$" /tmp/picknext-local-check.list
grep -E "TABLE .* items$" /tmp/picknext-local-check.list
grep -E "TABLE DATA .* users$" /tmp/picknext-local-check.list
grep -E "TABLE DATA .* categories$" /tmp/picknext-local-check.list
grep -E "TABLE DATA .* collections$" /tmp/picknext-local-check.list
grep -E "TABLE DATA .* items$" /tmp/picknext-local-check.list
wc -l /tmp/picknext-local-check.list
'@
if ($LASTEXITCODE -ne 0) { throw "pg_restore --list verification failed" }
& docker exec $PostgresContainer rm -f /tmp/picknext-local-check.dump /tmp/picknext-local-check.list

$Hash = (Get-FileHash -Algorithm SHA256 $DumpPath).Hash.ToLowerInvariant()
"$Hash  $DumpName" | Set-Content -Encoding ascii $ChecksumPath

$GitCommit = (git rev-parse HEAD).Trim()
$CreatedAt = [DateTime]::UtcNow.ToString("yyyy-MM-ddTHH:mm:ssZ")
$Manifest = @"
BACKUP_FORMAT=custom
SOURCE_DATABASE=$DbName
SOURCE_POSTGRES_MAJOR=$PgMajor
SOURCE_ALEMBIC_REVISION=$AlembicCurrent
SOURCE_USERS=$Users
SOURCE_CATEGORIES=$Categories
SOURCE_COLLECTIONS=$Collections
SOURCE_ITEMS=$Items
SOURCE_HISTORIES=$Histories
SOURCE_RECOMMENDATION_HISTORY_ITEMS=$HistoryItems
SOURCE_LEGACY_IMPORT_RUNS=$LegacyRuns
SOURCE_LEGACY_IMPORT_ITEMS=$LegacyItems
SOURCE_LEGACY_IMPORT_COLLECTIONS=$LegacyCollections
SOURCE_SEED_USER_EMAIL=$SeedEmailExpected
SOURCE_GIT_COMMIT=$GitCommit
BACKUP_FILENAME=$DumpName
BACKUP_SHA256=$Hash
CREATED_AT_UTC=$CreatedAt
"@
Set-Content -Path $ManifestPath -Value $Manifest.TrimEnd() -Encoding ascii

Write-Info "===== done ====="
Write-Info "DUMP=$($DumpFile.FullName)"
Write-Info "MANIFEST=$ManifestPath"
Write-Info "CHECKSUM=$ChecksumPath"
Write-Info "SHA256=$Hash"
Write-Info "ALEMBIC=$AlembicCurrent"
Write-Info "COUNTS users=$Users categories=$Categories collections=$Collections items=$Items histories=$Histories"
