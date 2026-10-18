param(
    [string]$TemplatePath = (Join-Path $PSScriptRoot 'user-pool.yaml')
)

$ErrorActionPreference = 'Stop'

if (-not (Test-Path -LiteralPath $TemplatePath -PathType Leaf)) {
    throw "No existe la plantilla de Cognito: $TemplatePath"
}

$template = Get-Content -LiteralPath $TemplatePath -Raw

function Assert-TemplatePattern {
    param(
        [string]$Name,
        [string]$Pattern
    )

    if ($template -notmatch $Pattern) {
        throw "Falta la configuración requerida: $Name"
    }
}

Assert-TemplatePattern 'login por correo' '(?m)^\s+UsernameAttributes:\s*\r?\n\s+- email\s*$'
Assert-TemplatePattern 'verificación de correo' '(?m)^\s+AutoVerifiedAttributes:\s*\r?\n\s+- email\s*$'
Assert-TemplatePattern 'cliente público sin secreto' '(?m)^\s+GenerateSecret:\s*false\s*$'
Assert-TemplatePattern 'flujo de contraseña' '(?m)^\s+- ALLOW_USER_PASSWORD_AUTH\s*$'
Assert-TemplatePattern 'flujo SRP' '(?m)^\s+- ALLOW_USER_SRP_AUTH\s*$'
Assert-TemplatePattern 'flujo de refresh' '(?m)^\s+- ALLOW_REFRESH_TOKEN_AUTH\s*$'
Assert-TemplatePattern 'flujo custom para PRO-31' '(?m)^\s+- ALLOW_CUSTOM_AUTH\s*$'
Assert-TemplatePattern 'atributo DPI requerido' '(?m)^\s+- Name: dpi\s*$[\s\S]*?^\s+Required:\s*true\s*$'
Assert-TemplatePattern 'output del issuer' '(?m)^\s+Issuer:\s*$[\s\S]*?cognito-idp\.\$\{AWS::Region\}'
Assert-TemplatePattern 'output JWKS' '(?m)^\s+JwksUri:\s*$[\s\S]*?\.well-known/jwks\.json'

if ($template -match '(?im)^\s*GenerateSecret:\s*true\s*$') {
    throw 'La plantilla no puede crear un secreto para el cliente público.'
}

foreach ($forbidden in @('AWS::SES::', 'ProviderDetails:', 'AWS::Cognito::UserPoolIdentityProvider')) {
    if ($template -match [regex]::Escape($forbidden)) {
        throw "Configuración fuera del alcance gratuito detectada: $forbidden"
    }
}

Write-Host 'Cognito template validation passed: pool email, DPI, public client, auth flows and issuer/JWKS outputs.'
Write-Host 'No se desplegó CloudFormation, no se crearon recursos y no se invocó AWS.'
