param(
    [string]$DatabaseUrl = $env:DATABASE_URL
)

$ErrorActionPreference = 'Stop'

if ([string]::IsNullOrWhiteSpace($DatabaseUrl)) {
    throw 'Defina DATABASE_URL o use -DatabaseUrl. No guarde credenciales en archivos versionados.'
}

if (-not (Get-Command psql -ErrorAction SilentlyContinue)) {
    throw 'psql no está disponible en PATH.'
}

$migrationDirectory = Join-Path $PSScriptRoot 'migrations'
$migrationFiles = Get-ChildItem -LiteralPath $migrationDirectory -Filter '*.sql' |
    Sort-Object Name

foreach ($migration in $migrationFiles) {
    Write-Host "Aplicando $($migration.Name)..."
    & psql $DatabaseUrl -X -v ON_ERROR_STOP=1 -f $migration.FullName
    if ($LASTEXITCODE -ne 0) {
        throw "Falló la migración $($migration.Name)."
    }
}

Write-Host 'Migraciones aplicadas correctamente.'
