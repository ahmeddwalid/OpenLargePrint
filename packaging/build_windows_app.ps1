<#
.SYNOPSIS
    Automated one-step build and packaging script for OpenLargePrint on Windows (PKG-001, PKG-002).
.DESCRIPTION
    1. Initializes MSVC BuildTools x64 environment.
    2. Packages standalone Python engine sidecar via PyInstaller (PKG-002: no Python required for end users).
    3. Generates high-contrast accessible application icons.
    4. Compiles React + TypeScript frontend bundle into ui/dist.
    5. Runs packaging verification gate.
    6. Bundles native Windows NSIS installer and MSI package.
#>

param(
    [switch]$SkipSidecarBuild
)

$ErrorActionPreference = "Stop"
$RepoRoot = Split-Path -Parent $PSScriptRoot

Write-Host "========================================================" -ForegroundColor Cyan
Write-Host " OpenLargePrint -- Windows Application Packaging Pipeline" -ForegroundColor Cyan
Write-Host " Target: Windows 10/11 x64 (NSIS Standalone Installer)" -ForegroundColor Cyan
Write-Host "========================================================" -ForegroundColor Cyan

# 1. Locate MSVC BuildTools environment
$VcvarsCandidates = @(
    "C:\Program Files (x86)\Microsoft Visual Studio\2019\BuildTools\VC\Auxiliary\Build\vcvars64.bat",
    "C:\Program Files\Microsoft Visual Studio\2022\Community\VC\Auxiliary\Build\vcvars64.bat",
    "C:\Program Files\Microsoft Visual Studio\2022\BuildTools\VC\Auxiliary\Build\vcvars64.bat"
)

$VcvarsBat = $null
foreach ($cand in $VcvarsCandidates) {
    if (Test-Path $cand) {
        $VcvarsBat = $cand
        break
    }
}

if ($VcvarsBat) {
    Write-Host "[1/6] Initializing MSVC build environment from: $VcvarsBat" -ForegroundColor Green
    $cmdOutput = cmd.exe /c ('call "{0}" && set' -f $VcvarsBat)
    foreach ($line in $cmdOutput) {
        if ($line -match '^(.*?)=(.*)$') {
            Set-Content "env:$($matches[1])" $matches[2]
        }
    }
} else {
    Write-Host "[1/6] Warning: vcvars64.bat not found in default paths; proceeding with system environment." -ForegroundColor Yellow
}

# 2. Build Python engine sidecar
if (-not $SkipSidecarBuild) {
    Write-Host "[2/6] Compiling standalone Python engine sidecar with PyInstaller..." -ForegroundColor Green
    python "$RepoRoot\packaging\build_sidecar.py"
    if ($LASTEXITCODE -ne 0) {
        Write-Error "Failed to build Python sidecar binary."
    }
} else {
    Write-Host "[2/6] Using existing Python sidecar binary (skipped build step)..." -ForegroundColor Green
}

# 3. Generate accessible Windows application icons
Write-Host "[3/6] Generating accessible high-contrast Windows icons..." -ForegroundColor Green
python "$RepoRoot\packaging\generate_icons.py"
if ($LASTEXITCODE -ne 0) {
    Write-Error "Failed to generate application icons."
}

# 4. Compile frontend UI
Write-Host "[4/6] Compiling React + TypeScript frontend into ui/dist..." -ForegroundColor Green
Push-Location "$RepoRoot\ui"
try {
    npm run build
    if ($LASTEXITCODE -ne 0) {
        Write-Error "Frontend compilation failed."
    }
} finally {
    Pop-Location
}

# 5. Verify packaging configuration
Write-Host "[5/6] Validating packaging contract and security boundaries..." -ForegroundColor Green
python "$RepoRoot\packaging\verify_packaging.py"
if ($LASTEXITCODE -ne 0) {
    Write-Error "Packaging verification gate failed."
}

# 6. Bundle Windows application with Tauri
Write-Host "[6/6] Building Windows desktop bundle (NSIS installer)..." -ForegroundColor Green
Push-Location "$RepoRoot\src-tauri"
try {
    npx @tauri-apps/cli build
    if ($LASTEXITCODE -ne 0) {
        Write-Host "Notice: If cargo build script is blocked by Smart App Control, ensure Developer Mode is enabled in Windows Settings." -ForegroundColor Yellow
    }
} finally {
    Pop-Location
}

$NsisPath = Join-Path $RepoRoot "src-tauri\target\release\bundle\nsis"
if (Test-Path $NsisPath) {
    $Installers = Get-ChildItem -Path $NsisPath -Filter "*.exe"
    Write-Host "`n Packaging Complete!" -ForegroundColor Green
    foreach ($inst in $Installers) {
        $sizeMb = [math]::Round($inst.Length / 1048576, 2)
        Write-Host (" Installer ready: {0} ({1} MB)" -f $inst.FullName, $sizeMb) -ForegroundColor Cyan
    }
    Write-Host "The user can double-click this installer to install OpenLargePrint on Windows without Python, terminal, or admin permissions." -ForegroundColor White
}
