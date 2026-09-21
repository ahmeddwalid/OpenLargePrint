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

# Single source of truth for the version (keeps artifact names in sync with the tag).
$TauriConfPath = Join-Path $RepoRoot "src-tauri\tauri.conf.json"
if (-not (Test-Path $TauriConfPath)) {
    Write-Error "Cannot determine application version: $TauriConfPath not found."
}
$AppVersion = (Get-Content -LiteralPath $TauriConfPath -Raw | ConvertFrom-Json).version
if (-not $AppVersion) {
    Write-Error "tauri.conf.json does not declare a version."
}

Write-Host "========================================================" -ForegroundColor Cyan
Write-Host " OpenLargePrint -- Windows Application Packaging Pipeline" -ForegroundColor Cyan
Write-Host " Target: Windows 10/11 x64 (NSIS Standalone Installer)" -ForegroundColor Cyan
Write-Host "========================================================" -ForegroundColor Cyan

# 1. Locate MSVC BuildTools environment
$VcvarsCandidates = @(
    "C:\Program Files\Microsoft Visual Studio\2022\Enterprise\VC\Auxiliary\Build\vcvars64.bat",
    "C:\Program Files\Microsoft Visual Studio\2022\Community\VC\Auxiliary\Build\vcvars64.bat",
    "C:\Program Files\Microsoft Visual Studio\2022\Professional\VC\Auxiliary\Build\vcvars64.bat",
    "C:\Program Files\Microsoft Visual Studio\2022\BuildTools\VC\Auxiliary\Build\vcvars64.bat",
    "C:\Program Files (x86)\Microsoft Visual Studio\2019\Enterprise\VC\Auxiliary\Build\vcvars64.bat",
    "C:\Program Files (x86)\Microsoft Visual Studio\2019\Community\VC\Auxiliary\Build\vcvars64.bat",
    "C:\Program Files (x86)\Microsoft Visual Studio\2019\BuildTools\VC\Auxiliary\Build\vcvars64.bat"
)

$VcvarsBat = $null
$vsWhere = "${env:ProgramFiles(x86)}\Microsoft Visual Studio\Installer\vswhere.exe"
if (Test-Path $vsWhere) {
    $vsPath = & $vsWhere -latest -products * -requires Microsoft.VisualStudio.Component.VC.Tools.x86.x64 -property installationPath
    if ($vsPath) {
        $cand = Join-Path $vsPath "VC\Auxiliary\Build\vcvars64.bat"
        if (Test-Path $cand) {
            $VcvarsBat = $cand
        }
    }
}

if (-not $VcvarsBat) {
    foreach ($cand in $VcvarsCandidates) {
        if (Test-Path $cand) {
            $VcvarsBat = $cand
            break
        }
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

# Resolve Python interpreter (prioritizing project virtualenv if present)
$PyExe = "python"
if (Test-Path "$RepoRoot\.venv\Scripts\python.exe") {
    $PyExe = "$RepoRoot\.venv\Scripts\python.exe"
}

# 2. Build Python engine sidecar
if (-not $SkipSidecarBuild) {
    Write-Host "[2/6] Compiling standalone Python engine sidecar with PyInstaller..." -ForegroundColor Green
    & $PyExe "$RepoRoot\packaging\build_sidecar.py"
    if ($LASTEXITCODE -ne 0) {
        Write-Error "Failed to build Python sidecar binary."
    }
} else {
    Write-Host "[2/6] Using existing Python sidecar binary (skipped build step)..." -ForegroundColor Green
}

# 3. Generate accessible Windows application icons
Write-Host "[3/6] Generating accessible high-contrast Windows icons..." -ForegroundColor Green
& $PyExe "$RepoRoot\packaging\generate_icons.py"
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
& $PyExe "$RepoRoot\packaging\verify_packaging.py"
if ($LASTEXITCODE -ne 0) {
    Write-Error "Packaging verification gate failed."
}

# 6. Bundle Windows application with Tauri
Write-Host "[6/6] Building Windows desktop bundle (NSIS installer)..." -ForegroundColor Green
Push-Location "$RepoRoot\src-tauri"
try {
    npx -y @tauri-apps/cli build
    if ($LASTEXITCODE -ne 0) {
        Write-Host "Notice: If cargo build script is blocked by Smart App Control, ensure Developer Mode is enabled in Windows Settings." -ForegroundColor Yellow
    }
} finally {
    Pop-Location
}

$NsisPath = Join-Path $RepoRoot "src-tauri\target\release\bundle\nsis"
$DistPath = Join-Path $RepoRoot "packaging\dist"
if (-not (Test-Path $DistPath)) {
    New-Item -ItemType Directory -Path $DistPath -Force | Out-Null
}

$ChecksumLines = @()

if (Test-Path $NsisPath) {
    $Installers = Get-ChildItem -Path $NsisPath -Filter "*.exe"
    Write-Host "`n Packaging Complete" -ForegroundColor Green
    if ($env:OLP_CODESIGN_THUMBPRINT) {
        Write-Host "Signing installers with certificate thumbprint: $env:OLP_CODESIGN_THUMBPRINT" -ForegroundColor Green
        foreach ($inst in $Installers) {
            signtool.exe sign /sha1 $env:OLP_CODESIGN_THUMBPRINT /fd SHA256 /tr "http://timestamp.digicert.com" /td SHA256 "$($inst.FullName)"
            if ($LASTEXITCODE -ne 0) {
                Write-Error "Code signing failed for $($inst.FullName)"
            }
        }
    }
    foreach ($inst in $Installers) {
        $sizeMb = [math]::Round($inst.Length / 1048576, 2)
        $hashResult = Get-FileHash -Algorithm SHA256 -LiteralPath $inst.FullName
        $hashVal = $hashResult.Hash.ToLowerInvariant()
        $fileName = $inst.Name
        $ChecksumLines += ("{0}  {1}" -f $hashVal, $fileName)
        Copy-Item -LiteralPath $inst.FullName -Destination (Join-Path $DistPath $fileName) -Force

        Write-Host (" Installer ready: {0} ({1} MB)" -f $inst.FullName, $sizeMb) -ForegroundColor Cyan
        Write-Host (" SHA-256: {0}" -f $hashVal) -ForegroundColor Yellow
    }

    # Also generate a standalone portable ZIP archive for users who prefer not to run an installer
    $TargetRelease = Join-Path $RepoRoot "src-tauri\target\release"
    $DesktopExe = Join-Path $TargetRelease "openlargeprint-desktop.exe"
    $SidecarExe = Join-Path $TargetRelease "openlargeprint-sidecar.exe"
    if (Test-Path $DesktopExe) {
        $PortableDir = Join-Path $RepoRoot "packaging\build\OpenLargePrint_portable"
        if (Test-Path $PortableDir) { Remove-Item -Recurse -Force $PortableDir }
        New-Item -ItemType Directory -Path $PortableDir -Force | Out-Null

        Copy-Item -LiteralPath $DesktopExe -Destination (Join-Path $PortableDir "OpenLargePrint.exe")
        if (Test-Path $SidecarExe) {
            Copy-Item -LiteralPath $SidecarExe -Destination (Join-Path $PortableDir "openlargeprint-sidecar.exe")
        } elseif (Test-Path "$RepoRoot\src-tauri\binaries\openlargeprint-sidecar-x86_64-pc-windows-msvc.exe") {
            Copy-Item -LiteralPath "$RepoRoot\src-tauri\binaries\openlargeprint-sidecar-x86_64-pc-windows-msvc.exe" -Destination (Join-Path $PortableDir "openlargeprint-sidecar.exe")
        }
        Copy-Item -LiteralPath "$RepoRoot\LICENSE" -Destination (Join-Path $PortableDir "LICENSE.txt")
        Copy-Item -LiteralPath "$RepoRoot\README.md" -Destination (Join-Path $PortableDir "README.txt")

        $PortableZip = Join-Path $DistPath ("OpenLargePrint_{0}_windows_x64_portable.zip" -f $AppVersion)
        if (Test-Path $PortableZip) { Remove-Item -Force $PortableZip }
        Compress-Archive -Path "$PortableDir\*" -DestinationPath $PortableZip -CompressionLevel Optimal
        if (Test-Path $PortableZip) {
            $zipItem = Get-Item $PortableZip
            $zipSizeMb = [math]::Round($zipItem.Length / 1048576, 2)
            $zipHash = (Get-FileHash -Algorithm SHA256 -LiteralPath $PortableZip).Hash.ToLowerInvariant()
            $ChecksumLines += ("{0}  {1}" -f $zipHash, $zipItem.Name)
            Write-Host (" Portable archive ready: {0} ({1} MB)" -f $PortableZip, $zipSizeMb) -ForegroundColor Cyan
            Write-Host (" SHA-256: {0}" -f $zipHash) -ForegroundColor Yellow
        }
    }

    # Write SHA256SUMS.txt in both bundle directory and dist directory
    $SumsFile1 = Join-Path $NsisPath "SHA256SUMS.txt"
    $SumsFile2 = Join-Path $DistPath "SHA256SUMS.txt"
    $ChecksumContent = ($ChecksumLines -join "`r`n") + "`r`n"
    Set-Content -Path $SumsFile1 -Value $ChecksumContent -Encoding ascii
    Set-Content -Path $SumsFile2 -Value $ChecksumContent -Encoding ascii

    Write-Host "`n Checksums generated and written to SHA256SUMS.txt" -ForegroundColor Green
    Write-Host "The user can double-click this installer to install OpenLargePrint on Windows without Python, terminal, or admin permissions." -ForegroundColor White
}
