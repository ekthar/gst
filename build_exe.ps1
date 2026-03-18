param(
    [switch]$Clean
)

$ErrorActionPreference = "Stop"
Set-Location $PSScriptRoot

if ($Clean) {
    if (Test-Path "build") { Remove-Item -Recurse -Force "build" }
    if (Test-Path "dist") { Remove-Item -Recurse -Force "dist" }
}

python -m pip install --upgrade pip

# Use wheel-safe runtime deps for packaging. python-Levenshtein is optional
# acceleration for fuzzywuzzy and may fail to compile on some Python toolchains.
$runtimeDeps = @(
    "openpyxl==3.1.5",
    "streamlit==1.42.2",
    "fuzzywuzzy==0.18.0",
    "pandas==2.3.3"
)

python -m pip install $runtimeDeps
if ($LASTEXITCODE -ne 0) { throw "Dependency installation failed." }

python -m pip install pyinstaller
if ($LASTEXITCODE -ne 0) { throw "PyInstaller installation failed." }

python -m PyInstaller --noconfirm GST_HSN_Resolver.spec
if ($LASTEXITCODE -ne 0) { throw "PyInstaller build failed." }

Write-Host "Build complete."
Write-Host "Output folder: dist\GST_HSN_Resolver"
Write-Host "Executable: dist\GST_HSN_Resolver\GST_HSN_Resolver.exe"
