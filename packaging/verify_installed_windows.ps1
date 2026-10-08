<# Verifies the actual installed native payload, including uninstall.exe (PKG-001).
   Run on the SAC acceptance VM after installation. Does not change security settings. #>
param(
    [Parameter(Mandatory = $true)][string]$InstallDirectory,
    [Parameter(Mandatory = $true)][string]$ExpectedPublisherMatch
)
$ErrorActionPreference = 'Stop'
$root = (Resolve-Path -LiteralPath $InstallDirectory).Path
$uninstaller = Join-Path $root 'uninstall.exe'
if (-not (Test-Path -LiteralPath $uninstaller)) { throw 'The installed uninstall.exe is missing.' }
$targets = Get-ChildItem -LiteralPath $root -Recurse -File |
    Where-Object { $_.Extension -in '.exe', '.dll', '.pyd' } |
    Select-Object -ExpandProperty FullName
if (-not $targets) { throw 'The installed native payload is missing.' }
& "$PSScriptRoot\verify_signatures.ps1" -Path $targets -RequirePublicTrust
if ($LASTEXITCODE -ne 0) { throw 'Installed payload signature verification failed.' }
# Vendor runtime publishers may differ. The three application-owned executables
# must match the release identity, rather than accepting any trusted signer.
$owned = @((Join-Path $root 'openlargeprint-desktop.exe'),
           (Join-Path $root 'openlargeprint-sidecar.exe'), $uninstaller)
& "$PSScriptRoot\verify_signatures.ps1" -Path $owned -RequirePublicTrust -ExpectedPublisherMatch $ExpectedPublisherMatch
if ($LASTEXITCODE -ne 0) { throw 'Installed application publisher verification failed.' }
Write-Host 'Installed payload and generated uninstaller signatures verified.'
