<#
.SYNOPSIS
    Signs OpenLargePrint binaries and installers using a code signing certificate.
.DESCRIPTION
    Uses signtool.exe with the specified or auto-discovered certificate thumbprint.
#>

param(
    [string]$TargetFile,
    [string]$Thumbprint = $env:OLP_CODESIGN_THUMBPRINT,
    [string]$TimestampUrl = "http://timestamp.digicert.com"
)

$ErrorActionPreference = "Stop"
$RepoRoot = Split-Path -Parent $PSScriptRoot

# Locate signtool.exe
$SigntoolCandidates = @(
    "C:\Program Files (x86)\Windows Kits\10\bin\10.0.22621.0\x64\signtool.exe",
    "C:\Program Files (x86)\Windows Kits\10\bin\10.0.19041.0\x64\signtool.exe",
    "C:\Program Files (x86)\Windows Kits\10\bin\x64\signtool.exe"
)

$Signtool = $null
foreach ($cand in $SigntoolCandidates) {
    if (Test-Path $cand) {
        $Signtool = $cand
        break
    }
}

if (-not $Signtool) {
    $where = Get-Command signtool.exe -ErrorAction SilentlyContinue
    if ($where) {
        $Signtool = $where.Source
    }
}

if (-not $Signtool) {
    Write-Error "signtool.exe not found. Please install Windows SDK or BuildTools."
}

# Discover thumbprint if not provided
if (-not $Thumbprint) {
    $cert = Get-ChildItem "Cert:\CurrentUser\My" | Where-Object { $_.Subject -match "OpenLargePrint" } | Select-Object -First 1
    if ($cert) {
        $Thumbprint = $cert.Thumbprint
        Write-Host "Auto-discovered OpenLargePrint certificate: $Thumbprint" -ForegroundColor Green
    } else {
        Write-Error "No signing certificate thumbprint provided and no OpenLargePrint certificate found in Cert:\CurrentUser\My. Run packaging\create_self_signed_cert.ps1 first."
    }
}

# If no target specified, sign the built NSIS installer and sidecar
$FilesToSign = @()
if ($TargetFile) {
    if (Test-Path $TargetFile) {
        $FilesToSign += (Resolve-Path $TargetFile).Path
    } else {
        Write-Error "Target file does not exist: $TargetFile"
    }
} else {
    $sidecar = Join-Path $RepoRoot "src-tauri\binaries\openlargeprint-sidecar-x86_64-pc-windows-msvc.exe"
    if (Test-Path $sidecar) {
        $FilesToSign += $sidecar
    }
    $nsisDir = Join-Path $RepoRoot "src-tauri\target\release\bundle\nsis"
    if (Test-Path $nsisDir) {
        Get-ChildItem -Path $nsisDir -Filter "*.exe" | ForEach-Object { $FilesToSign += $_.FullName }
    }
}

if ($FilesToSign.Count -eq 0) {
    Write-Host "No binaries found to sign. Build the application first." -ForegroundColor Yellow
    return
}

Write-Host "Signing $($FilesToSign.Count) file(s) with thumbprint: $Thumbprint" -ForegroundColor Cyan

foreach ($file in $FilesToSign) {
    Write-Host "Signing: $file" -ForegroundColor Green
    & $Signtool sign /sha1 $Thumbprint /fd SHA256 /tr $TimestampUrl /td SHA256 "$file"
    if ($LASTEXITCODE -eq 0) {
        Write-Host "  Successfully signed: $file" -ForegroundColor Green
    } else {
        Write-Host "  Retrying without timestamp (offline fallback)..." -ForegroundColor Yellow
        & $Signtool sign /sha1 $Thumbprint /fd SHA256 "$file"
        if ($LASTEXITCODE -ne 0) {
            Write-Error "Failed to sign $file"
        }
    }
}

Write-Host "`nAll files signed successfully." -ForegroundColor Green
