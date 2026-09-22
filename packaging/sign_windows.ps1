<#
.SYNOPSIS
    Authenticode-signs one or more OpenLargePrint Windows binaries (PKG-001).

.DESCRIPTION
    Windows 11 Smart App Control blocks unsigned executables outright, with no
    user override ("If the app is unsigned, or the signature is invalid, Smart
    App Control will consider it untrusted and block it for protection").

    Every executable Windows evaluates must therefore be signed:
      * openlargeprint-desktop.exe   (the shell)
      * openlargeprint-sidecar.exe   (the bundled Python engine)
      * the NSIS installer

    This script fails closed: a signing or verification failure is an error,
    never a warning. Certificate lookup order:
      -Thumbprint  ->  $env:OLP_CODESIGN_THUMBPRINT  ->  a certificate in
      Cert:\CurrentUser\My whose subject matches 'OpenLargePrint'.

.PARAMETER Path
    One or more files to sign.

.PARAMETER Thumbprint
    SHA-1 thumbprint of the signing certificate in the Windows certificate store.

.PARAMETER TimestampUrl
    RFC 3161 timestamp authority. Timestamping keeps existing signatures valid
    after the certificate expires.

.EXAMPLE
    powershell -ExecutionPolicy Bypass -File packaging/sign_windows.ps1 `
        -Path src-tauri/target/release/openlargeprint-desktop.exe
#>
param(
    [Parameter(Mandatory = $true)][string[]]$Path,
    [string]$Thumbprint = $env:OLP_CODESIGN_THUMBPRINT,
    [string]$TimestampUrl = "http://timestamp.digicert.com"
)

$ErrorActionPreference = "Stop"

function Resolve-Signtool {
    $candidates = @()

    $kitsRoot = "C:\Program Files (x86)\Windows Kits\10\bin"
    if (Test-Path $kitsRoot) {
        $candidates += Get-ChildItem -Path $kitsRoot -Filter signtool.exe -Recurse -ErrorAction SilentlyContinue |
            Where-Object { $_.FullName -match '\\x64\\signtool\.exe$' } |
            Sort-Object -Property FullName -Descending |
            Select-Object -ExpandProperty FullName
    }

    $candidates += "C:\Program Files (x86)\Windows Kits\10\bin\x64\signtool.exe"

    $onPath = Get-Command signtool.exe -ErrorAction SilentlyContinue
    if ($onPath) { $candidates += $onPath.Source }

    $found = $candidates | Where-Object { $_ -and (Test-Path $_) } | Select-Object -First 1
    if (-not $found) {
        throw "signtool.exe was not found. Install the Windows SDK (Code Signing Tools)."
    }
    return $found
}

if (-not $Thumbprint) {
    $discovered = Get-ChildItem "Cert:\CurrentUser\My" -ErrorAction SilentlyContinue |
        Where-Object { $_.Subject -match "OpenLargePrint" } |
        Select-Object -First 1
    if ($discovered) {
        $Thumbprint = $discovered.Thumbprint
        Write-Host "Using certificate from the local store: $Thumbprint" -ForegroundColor DarkGray
    }
}

if (-not $Thumbprint) {
    throw "No signing certificate supplied. Set OLP_CODESIGN_THUMBPRINT, pass -Thumbprint, or create a development certificate with packaging/create_self_signed_cert.ps1."
}

$signtool = Resolve-Signtool
Write-Host "Using signtool: $signtool" -ForegroundColor DarkGray

foreach ($target in $Path) {
    if (-not (Test-Path $target)) {
        throw "Signing target does not exist: $target"
    }

    $resolved = (Resolve-Path $target).Path
    $signArgs = @(
        "sign",
        "/sha1", $Thumbprint,
        "/fd", "SHA256",
        "/tr", $TimestampUrl,
        "/td", "SHA256",
        "/v",
        $resolved
    )

    & $signtool @signArgs
    if ($LASTEXITCODE -ne 0) {
        throw "Signing failed for $resolved (signtool exit $LASTEXITCODE)"
    }

    & $signtool verify /pa /v $resolved | Out-Null
    if ($LASTEXITCODE -ne 0) {
        throw "Post-sign verification failed for $resolved"
    }

    Write-Host "Signed and verified: $resolved" -ForegroundColor Green
}

exit 0
