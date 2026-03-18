param(
    [string]$AppVersion = "0.1.0"
)

$ErrorActionPreference = "Stop"

$distExe = "dist\GST HSN Resolver\GST HSN Resolver.exe"
if (!(Test-Path $distExe)) {
    throw "Missing built app. Run scripts/build_exe.ps1 first."
}

$isccCandidates = @(
    "$Env:ProgramFiles(x86)\Inno Setup 6\ISCC.exe",
    "$Env:ProgramFiles\Inno Setup 6\ISCC.exe"
)

$iscc = $null
foreach ($candidate in $isccCandidates) {
    if (Test-Path $candidate) {
        $iscc = $candidate
        break
    }
}

if ($null -eq $iscc) {
    throw "Inno Setup not found. Install from https://jrsoftware.org/isinfo.php"
}

& $iscc "/DAppVersion=$AppVersion" "installer\gst_hsn_resolver.iss"

Write-Host "Installer created in dist_installer folder."
