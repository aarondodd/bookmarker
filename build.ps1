#
# Build script for Bookmarker (Windows)
# Produces a PyInstaller --onedir bundle at dist\bookmarker\ from bookmarker.spec.
#
# This only builds -- it leaves the bundle in dist\ and installs nothing. Normal
# users install via the Inno Setup installer (installer.iss wraps dist\bookmarker\;
# CI in .github/workflows/release.yml builds it there). For a local run, launch
# dist\bookmarker\bookmarker.exe directly.
#

$ErrorActionPreference = "Stop"

$ScriptDir = Split-Path -Parent $MyInvocation.MyCommand.Path
$AppName = "bookmarker"
$DistDir = Join-Path $ScriptDir "dist"
$BuildDir = Join-Path $ScriptDir "build"
$VenvDir = Join-Path $ScriptDir ".venv"
$BundleDir = Join-Path $DistDir $AppName
$ExePath = Join-Path $BundleDir "$AppName.exe"

Write-Host "=== Bookmarker Build Script ===" -ForegroundColor Cyan
Write-Host ""

# Check if we're in a virtual environment, if not activate or create one
if (-not $env:VIRTUAL_ENV) {
    if (Test-Path $VenvDir) {
        Write-Host "Activating virtual environment..."
        & "$VenvDir\Scripts\Activate.ps1"
    } else {
        Write-Host "Creating virtual environment..."
        python -m venv $VenvDir
        & "$VenvDir\Scripts\Activate.ps1"
    }
}

# Install dependencies
Write-Host "Installing dependencies..."
pip install --quiet --upgrade pip
pip install --quiet -r (Join-Path $ScriptDir "requirements.txt")
pip install --quiet pyinstaller

# Clean previous builds
Write-Host "Cleaning previous builds..."
if (Test-Path $DistDir) { Remove-Item -Recurse -Force $DistDir }
if (Test-Path $BuildDir) { Remove-Item -Recurse -Force $BuildDir }

# Run PyInstaller (all config lives in bookmarker.spec)
Write-Host "Building onedir bundle with PyInstaller..."
Set-Location $ScriptDir
pyinstaller --noconfirm --clean (Join-Path $ScriptDir "bookmarker.spec")

# Check if build succeeded
if (-not (Test-Path $ExePath)) {
    Write-Host "ERROR: Build failed - launcher not found at $ExePath" -ForegroundColor Red
    exit 1
}

Write-Host ""
Write-Host "Build successful!" -ForegroundColor Green
Write-Host "Bundle: $BundleDir"
Write-Host "Launcher: $ExePath"
Write-Host ""
Write-Host "Package it with installer.iss (Inno Setup) to produce the installer,"
Write-Host "or run the launcher above directly for a local test."
