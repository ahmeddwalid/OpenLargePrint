<#
.SYNOPSIS
    One-step development setup and launcher for OpenLargePrint on Windows (PKG-001, PKG-002).
.DESCRIPTION
    Verifies development prerequisites, synchronizes Python and UI dependencies,
    ensures the development sidecar binary is built, and launches Tauri dev mode
    or runs the test suites.
.PARAMETER Test
    Run Python, UI, and Rust test suites instead of launching the app.
.PARAMETER SkipSidecar
    Skip rebuilding the Python sidecar binary if it already exists.
.PARAMETER RebuildSidecar
    Force re-compiling the Python sidecar binary.
.PARAMETER NoLaunch
    Prepare dependencies and sidecar without starting the desktop application.
.EXAMPLE
    .\dev_windows.ps1
.EXAMPLE
    .\dev_windows.ps1 -Test
#>

param(
    [switch]$Test,
    [switch]$SkipSidecar,
    [switch]$RebuildSidecar,
    [switch]$NoLaunch
)

$ErrorActionPreference = "Stop"
$RepoRoot = $PSScriptRoot

Write-Host "==========================================================" -ForegroundColor Cyan
Write-Host " OpenLargePrint -- Windows Development Environment Setup " -ForegroundColor Cyan
Write-Host "==========================================================" -ForegroundColor Cyan

# 1. Verify Prerequisites
function Check-Command($cmd, $helpUrl) {
    if (-not (Get-Command $cmd -ErrorAction SilentlyContinue)) {
        Write-Error "Required tool '$cmd' is not installed or not in PATH.`nPlease install it from: $helpUrl"
    }
}

Check-Command "uv" "https://astral.sh/uv"
Check-Command "node" "https://nodejs.org/"
Check-Command "npm" "https://nodejs.org/"
Check-Command "cargo" "https://rustup.rs/"

Write-Host "[1/4] Prerequisites verified (uv, node, npm, cargo)." -ForegroundColor Green

# 2. Sync Python environment
Write-Host "[2/4] Synchronizing Python environment with uv..." -ForegroundColor Green
& uv sync --locked --dev --extra dev --python 3.12
if ($LASTEXITCODE -ne 0) {
    Write-Error "Failed to synchronize Python dependencies via uv."
}

# 3. Install UI dependencies
Write-Host "[3/4] Checking frontend dependencies in ui/..." -ForegroundColor Green
Push-Location "$RepoRoot\ui"
try {
    if (-not (Test-Path "node_modules")) {
        Write-Host "Installing npm packages in ui/..." -ForegroundColor Gray
        npm install
        if ($LASTEXITCODE -ne 0) {
            Write-Error "Failed to install npm dependencies in ui/."
        }
    } else {
        Write-Host "Frontend dependencies present." -ForegroundColor Gray
    }
} finally {
    Pop-Location
}

# 4. Check or Build Development Sidecar Binary
$SidecarTarget = Join-Path $RepoRoot "src-tauri\binaries\openlargeprint-sidecar-x86_64-pc-windows-msvc.exe"
$NeedsSidecarBuild = $RebuildSidecar -or (-not (Test-Path $SidecarTarget))

if ($NeedsSidecarBuild -and (-not $SkipSidecar)) {
    Write-Host "[4/4] Building standalone Python sidecar for development..." -ForegroundColor Green
    & uv run python "$RepoRoot\packaging\build_sidecar.py"
    if ($LASTEXITCODE -ne 0 -or -not (Test-Path $SidecarTarget)) {
        Write-Error "Failed to build development sidecar binary: $SidecarTarget"
    }
    Write-Host "Sidecar ready at: $SidecarTarget" -ForegroundColor Green
} else {
    Write-Host "[4/4] Sidecar binary is present: $SidecarTarget" -ForegroundColor Green
}

# Mode execution: Tests or Launch Dev
if ($Test) {
    Write-Host "`nRunning test suites..." -ForegroundColor Cyan
    
    Write-Host "`n-- Python Tests (pytest) --" -ForegroundColor Yellow
    & uv run python -m pytest "$RepoRoot\tests" -q
    if ($LASTEXITCODE -ne 0) {
        Write-Error "Python tests failed."
    }

    Write-Host "`n-- Frontend Tests (vitest) --" -ForegroundColor Yellow
    Push-Location "$RepoRoot\ui"
    try {
        $env:NODE_ENV = "test"
        npx vitest run
        if ($LASTEXITCODE -ne 0) {
            Write-Error "Frontend tests failed."
        }
        Write-Host "`n-- Frontend Typecheck (tsc) --" -ForegroundColor Yellow
        npx tsc --noEmit
        if ($LASTEXITCODE -ne 0) {
            Write-Error "TypeScript check failed."
        }
    } finally {
        Pop-Location
    }

    Write-Host "`n-- Rust Tauri Checks --" -ForegroundColor Yellow
    Push-Location "$RepoRoot\src-tauri"
    try {
        cargo check
        if ($LASTEXITCODE -ne 0) {
            Write-Error "Cargo check failed."
        }
        cargo test
        if ($LASTEXITCODE -ne 0) {
            Write-Error "Cargo test failed."
        }
    } finally {
        Pop-Location
    }

    Write-Host "`nAll test suites passed cleanly." -ForegroundColor Green
    exit 0
}

if ($NoLaunch) {
    Write-Host "`nSetup complete! You can run tests with: .\dev_windows.ps1 -Test" -ForegroundColor Green
    Write-Host "Or start the app with: cd src-tauri; npx @tauri-apps/cli dev" -ForegroundColor Green
    exit 0
}

Write-Host "`nStarting OpenLargePrint desktop application in development mode..." -ForegroundColor Cyan
Push-Location "$RepoRoot\src-tauri"
try {
    npx -y @tauri-apps/cli@2 dev
} finally {
    Pop-Location
}
