param(
    [string]$AppVersion = "0.1.0"
)

$ErrorActionPreference = "Stop"

Write-Host "Installing build dependency: pyinstaller"
python -m pip install pyinstaller

Write-Host "Cleaning previous build artifacts"
if (Test-Path "build") { Remove-Item -Recurse -Force "build" }
if (Test-Path "dist") { Remove-Item -Recurse -Force "dist" }

$addDataArgs = @(
    "--add-data", "data;data"
)

if (Test-Path "assets") {
    $addDataArgs += @("--add-data", "assets;assets")
}

Write-Host "Building Windows desktop executable"
python -m PyInstaller `
    --noconfirm `
    --clean `
    --windowed `
    --name "GST HSN Resolver" `
    --collect-all openpyxl `
    --collect-all xlrd `
    --hidden-import gst_hsn_tool.gui `
    --hidden-import gst_hsn_tool.cli `
    $addDataArgs `
    src/gst_hsn_tool/__main__.py

$distFolder = "dist\GST HSN Resolver"
if (!(Test-Path $distFolder)) {
    throw "Build failed. Missing output folder: $distFolder"
}

$versionFile = Join-Path $distFolder "VERSION.txt"
"GST HSN Resolver version $AppVersion" | Out-File -Encoding utf8 $versionFile

Write-Host "Build complete. Output: $distFolder"
Write-Host "Run executable: dist\GST HSN Resolver\GST HSN Resolver.exe"
