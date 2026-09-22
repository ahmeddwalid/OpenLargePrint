<#
.SYNOPSIS
    Verifies that every released Windows binary carries a valid Authenticode signature (PKG-001).

.DESCRIPTION
    Windows 11 Smart App Control blocks unsigned executables outright. This gate
    inspects the real Authenticode state of each artifact and exits non-zero if
    anything distributed to users is unsigned, tampered with, or signed by an
    unexpected publisher. Run it over the installer *and* the executables it
    installs - signing only the installer is not enough.

.PARAMETER Path
    Artifact paths to verify.

.PARAMETER ExpectedPublisherMatch
    Optional substring that must appear in the signing certificate subject,
    e.g. "SignPath Foundation". Leave empty while validating a development
    certificate.

.EXAMPLE
    powershell -ExecutionPolicy Bypass -File packaging/verify_signatures.ps1 `
        -Path packaging/dist/OpenLargePrint_0.2.0_x64-setup.exe `
        -ExpectedPublisherMatch "SignPath Foundation"
#>
param(
    [Parameter(Mandatory = $true)][string[]]$Path,
    [string]$ExpectedPublisherMatch = ""
)

$ErrorActionPreference = "Stop"
$failed = @()

foreach ($target in $Path) {
    if (-not (Test-Path $target)) {
        throw "Artifact missing: $target"
    }

    $signature = Get-AuthenticodeSignature -FilePath $target
    $leaf = Split-Path -Leaf $target
    $subject = if ($signature.SignerCertificate) { $signature.SignerCertificate.Subject } else { "<none>" }

    Write-Host ("{0}: {1} (publisher: {2})" -f $leaf, $signature.Status, $subject)

    if ($signature.Status -ne 'Valid') {
        $failed += "$leaf -> $($signature.Status)"
        continue
    }

    if ($ExpectedPublisherMatch -and ($subject -notmatch [regex]::Escape($ExpectedPublisherMatch))) {
        $failed += "$leaf -> unexpected publisher: $subject"
    }

    if (-not $signature.TimeStamperCertificate) {
        Write-Host ("  warning: {0} has no trusted timestamp; it will expire with the certificate." -f $leaf) -ForegroundColor Yellow
    }
}

if ($failed.Count -gt 0) {
    Write-Host "Signature verification FAILED:" -ForegroundColor Red
    $failed | ForEach-Object { Write-Host "  $_" -ForegroundColor Red }
    Write-Host "Unsigned artifacts are blocked by Smart App Control on Windows 11." -ForegroundColor Red
    exit 1
}

Write-Host "All artifacts are validly signed." -ForegroundColor Green
exit 0
