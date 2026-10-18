param(
    [string]$MigrationDirectory = (Join-Path $PSScriptRoot 'migrations')
)

$ErrorActionPreference = 'Stop'

if (-not (Test-Path -LiteralPath $MigrationDirectory -PathType Container)) {
    throw "No existe el directorio de migraciones: $MigrationDirectory"
}

$migrationFiles = @(Get-ChildItem -LiteralPath $MigrationDirectory -Filter '*.sql' -File | Sort-Object Name)
if ($migrationFiles.Count -eq 0) {
    throw 'No se encontraron archivos .sql de migración.'
}

$expectedVersions = @('000_bootstrap', '001_core_schema', '002_indexes')
$actualVersions = @()
$previousName = $null

foreach ($migration in $migrationFiles) {
    if ($migration.Name -notmatch '^\d{3}_[a-z0-9_]+\.sql$') {
        throw "Nombre de migración inválido: $($migration.Name)"
    }

    if ($null -ne $previousName -and $migration.Name -le $previousName) {
        throw "Las migraciones no están ordenadas: $previousName, $($migration.Name)"
    }
    $previousName = $migration.Name

    $content = Get-Content -LiteralPath $migration.FullName -Raw
    $matches = [regex]::Matches($content, "VALUES\s*\('([^']+)'\)")
    foreach ($match in $matches) {
        $actualVersions += $match.Groups[1].Value
    }

    if ($content -notmatch '(?i)BEGIN\s*;') {
        throw "$($migration.Name) debe iniciar una transacción explícita."
    }
    if ($content -notmatch '(?i)COMMIT\s*;') {
        throw "$($migration.Name) debe cerrar la transacción explícita."
    }
}

if (@($actualVersions | Select-Object -Unique).Count -ne $expectedVersions.Count -or
    @($expectedVersions | Where-Object { $_ -notin $actualVersions }).Count -gt 0) {
    throw "Versiones registradas inválidas. Esperadas: $($expectedVersions -join ', '); encontradas: $($actualVersions -join ', ')"
}

$allSql = ($migrationFiles | ForEach-Object { Get-Content -LiteralPath $_.FullName -Raw }) -join "`n"
$requiredPatterns = @{
    'tabla users' = '(?i)CREATE TABLE IF NOT EXISTS users'
    'tabla post_labels' = '(?i)CREATE TABLE IF NOT EXISTS post_labels'
    'contrato normalizado de etiquetas' = '(?i)normalized_label\s+citext'
    'origen de etiqueta' = '(?i)source_label\s+varchar'
    'índice de solicitudes pendientes' = '(?i)friend_requests_one_pending_pair_idx'
    'índice de feed' = '(?i)posts_author_created_id_idx'
    'índice de conversación' = '(?i)messages_conversation_created_id_idx'
}

foreach ($entry in $requiredPatterns.GetEnumerator()) {
    if ($allSql -notmatch $entry.Value) {
        throw "No se encontró $($entry.Key) en las migraciones."
    }
}

foreach ($legacyName in @('label_name', 'source_name')) {
    if ($allSql -match "(?i)\b$legacyName\b") {
        throw "El contrato legado '$legacyName' todavía aparece en las migraciones."
    }
}

Write-Host "Migration preflight passed: $($migrationFiles.Count) archivos, $($expectedVersions.Count) versiones y contrato PRO-12 alineado."
Write-Host 'No se abrió ninguna conexión, no se leyó DATABASE_URL y no se invocó AWS.'
