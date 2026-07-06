#
# Build script for Bookmarker (Windows)
# Produces a PyInstaller --onedir bundle at dist\bookmarker\ from bookmarker.spec.
#
# CI (.github/workflows/release.yml) runs this with $env:BOOKMARKER_NO_INSTALL=1
# to build the bundle only; installer.iss then wraps dist\bookmarker\ into the
# Inno Setup installer. Run without that variable for a local dev install into
# %USERPROFILE%\bin.
#

$ErrorActionPreference = "Stop"

$ScriptDir = Split-Path -Parent $MyInvocation.MyCommand.Path
$AppName = "bookmarker"
$DistDir = Join-Path $ScriptDir "dist"
$BuildDir = Join-Path $ScriptDir "build"
$VenvDir = Join-Path $ScriptDir ".venv"
$BinDir = Join-Path $env:USERPROFILE "bin"
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

if ($env:BOOKMARKER_NO_INSTALL -eq "1") {
    Write-Host ""
    Write-Host "BOOKMARKER_NO_INSTALL=1 set - skipping local install." -ForegroundColor Yellow
    exit 0
}

# Local dev install: copy the whole onedir bundle to %USERPROFILE%\bin\bookmarker\
# and drop a launcher shim next to it. A single-file copy no longer works under
# --onedir. Production installs go through the Inno Setup installer instead.
$DestDir = Join-Path $BinDir $AppName
$OldDir = Join-Path $BinDir "$AppName.old"
if (-not (Test-Path $BinDir)) {
    Write-Host "Creating $BinDir..."
    New-Item -ItemType Directory -Path $BinDir | Out-Null
}
Write-Host "Installing bundle to $DestDir..."
if (Test-Path $OldDir) {
    try { Remove-Item -Recurse -Force $OldDir -ErrorAction SilentlyContinue } catch { }
}
if (Test-Path $DestDir) {
    try { Rename-Item $DestDir $OldDir -ErrorAction SilentlyContinue } catch { }
}
Copy-Item $BundleDir $DestDir -Recurse -Force

Write-Host ""
Write-Host "=== Installation Complete ===" -ForegroundColor Cyan
Write-Host "Bundle installed to: $DestDir"
Write-Host "Launcher: $(Join-Path $DestDir "$AppName.exe")"
Write-Host ""
Write-Host "Make sure $BinDir is in your PATH."
Write-Host ""
