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
    [string]$ExpectedPublisherMatch = "",
    [string]$ExpectedThumbprint = "",
    [switch]$RequirePublicTrust
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
    if ($ExpectedThumbprint -and $signature.SignerCertificate.Thumbprint -ne $ExpectedThumbprint) {
        $failed += "$leaf -> unexpected signing identity"
    }

    if (-not $signature.TimeStamperCertificate) {
        $failed += "$leaf -> missing trusted timestamp"
    }

    if ($RequirePublicTrust) {
        # Microsoft's current SAC guidance accepts RSA and ECC. Local roots must never
        # satisfy the public-release gate merely because they were installed locally.
        if ($signature.SignerCertificate.PublicKey.Oid.Value -notin '1.2.840.113549.1.1.1', '1.2.840.10045.2.1') {
            $failed += "$leaf -> unsupported signing key algorithm"
        }
        $chain = New-Object System.Security.Cryptography.X509Certificates.X509Chain
        try {
            $chain.ChainPolicy.RevocationMode = 'Online'
            # WinTrust above verifies the signing time against the trusted
            # timestamp. A vendor certificate may now be expired but still valid
            # for its timestamped binary; chain trust is checked independently.
            $chain.ChainPolicy.VerificationFlags = 'IgnoreNotTimeValid'
            if (-not $chain.Build($signature.SignerCertificate)) {
                $failed += "$leaf -> certificate chain verification failed"
            } else {
                $root = $chain.ChainElements[$chain.ChainElements.Count - 1].Certificate
                $publicRoot = "HKLM:\SOFTWARE\Microsoft\SystemCertificates\AuthRoot\Certificates\$($root.Thumbprint)"
                if (-not (Test-Path -LiteralPath $publicRoot)) {
                    $failed += "$leaf -> root is absent from Microsoft's AuthRoot store"
                }
            }
        } finally { $chain.Dispose() }
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
