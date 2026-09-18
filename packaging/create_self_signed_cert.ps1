<#
.SYNOPSIS
    Generates a self-signed code signing certificate for OpenLargePrint on Windows.
.DESCRIPTION
    1. Creates a 3072-bit RSA Code Signing certificate in Cert:\CurrentUser\My.
    2. Exports the certificate (.cer and .pfx) to packaging/certs/.
    3. Sets OLP_CODESIGN_THUMBPRINT in process and user environment variables.
#>

param(
    [string]$Subject = "CN=OpenLargePrint, O=OpenLargePrint Contributors",
    [string]$Password = "OpenLargePrint123!",
    [switch]$Force
)

$ErrorActionPreference = "Stop"
$ScriptDir = Split-Path -Parent $MyInvocation.MyCommand.Path
$CertDir = Join-Path $ScriptDir "certs"

if (-not (Test-Path $CertDir)) {
    New-Item -ItemType Directory -Path $CertDir -Force | Out-Null
}

Write-Host "========================================================" -ForegroundColor Cyan
Write-Host " OpenLargePrint -- Self-Signed Certificate Generator" -ForegroundColor Cyan
Write-Host "========================================================" -ForegroundColor Cyan

# Check if an existing certificate exists
$Existing = Get-ChildItem "Cert:\CurrentUser\My" | Where-Object { $_.Subject -match "OpenLargePrint" }
if ($Existing -and -not $Force) {
    $Cert = $Existing[0]
    $Thumbprint = $Cert.Thumbprint
    Write-Host "`nFound existing certificate in CurrentUser\My:" -ForegroundColor Green
    Write-Host "  Subject:    $($Cert.Subject)"
    Write-Host "  Thumbprint: $Thumbprint"
    Write-Host "  Expires:    $($Cert.NotAfter)"
    
    [System.Environment]::SetEnvironmentVariable("OLP_CODESIGN_THUMBPRINT", $Thumbprint, "Process")
    [System.Environment]::SetEnvironmentVariable("OLP_CODESIGN_THUMBPRINT", $Thumbprint, "User")
    
    # Export public certificate (.cer)
    $CerPath = Join-Path $CertDir "OpenLargePrint-CodeSigning.cer"
    Export-Certificate -Cert $Cert -FilePath $CerPath | Out-Null
    
    # Export PFX
    $PfxPath = Join-Path $CertDir "OpenLargePrint-CodeSigning.pfx"
    $SecurePass = ConvertTo-SecureString -String $Password -AsPlainText -Force
    Export-PfxCertificate -Cert $Cert -FilePath $PfxPath -Password $SecurePass | Out-Null
    
    Write-Host "`nEnvironment variable OLP_CODESIGN_THUMBPRINT set to: $Thumbprint" -ForegroundColor Green
    Write-Host "PFX saved to: $PfxPath (Password: $Password)" -ForegroundColor Green
    Write-Host "CER saved to: $CerPath" -ForegroundColor Green
    return $Thumbprint
}

Write-Host "`nCreating new self-signed code signing certificate..." -ForegroundColor Green

$Cert = New-SelfSignedCertificate `
    -Type CodeSigningCert `
    -Subject $Subject `
    -KeyAlgorithm RSA `
    -KeyLength 3072 `
    -KeyExportPolicy Exportable `
    -KeyUsage DigitalSignature `
    -CertStoreLocation "Cert:\CurrentUser\My" `
    -NotAfter (Get-Date).AddYears(3)

$Thumbprint = $Cert.Thumbprint

Write-Host "Certificate created successfully!" -ForegroundColor Green
Write-Host "  Thumbprint: $Thumbprint"
Write-Host "  Subject:    $($Cert.Subject)"
Write-Host "  Valid Until: $($Cert.NotAfter)"

# Export public certificate (.cer)
$CerPath = Join-Path $CertDir "OpenLargePrint-CodeSigning.cer"
Export-Certificate -Cert $Cert -FilePath $CerPath | Out-Null
Write-Host "Exported public certificate to: $CerPath" -ForegroundColor Green

# Export PFX with password
$PfxPath = Join-Path $CertDir "OpenLargePrint-CodeSigning.pfx"
$SecurePass = ConvertTo-SecureString -String $Password -AsPlainText -Force
Export-PfxCertificate -Cert $Cert -FilePath $PfxPath -Password $SecurePass | Out-Null
Write-Host "Exported PFX certificate to: $PfxPath (Password: $Password)" -ForegroundColor Green

# Set environment variable for process and user
[System.Environment]::SetEnvironmentVariable("OLP_CODESIGN_THUMBPRINT", $Thumbprint, "Process")
[System.Environment]::SetEnvironmentVariable("OLP_CODESIGN_THUMBPRINT", $Thumbprint, "User")

Write-Host "`nEnvironment variable OLP_CODESIGN_THUMBPRINT set to: $Thumbprint" -ForegroundColor Cyan
Write-Host "Run packaging/build_windows_app.ps1 to build and sign automatically." -ForegroundColor Green

return $Thumbprint
