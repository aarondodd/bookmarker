#!/bin/bash
#
# Build script for Bookmarker (Linux / macOS)
# Produces a PyInstaller --onedir bundle at dist/bookmarker/ from bookmarker.spec.
#
# This only builds -- it leaves the bundle in dist/ and installs nothing. Normal
# users install from the release tarball (bookmarker-linux-x86_64-X.Y.Z.tar.gz),
# which ships an install.sh that places the bundle under ~/.local/share/bookmarker
# and symlinks ~/.local/bin/bookmarker. For a local run, launch
# dist/bookmarker/bookmarker directly.
#

set -e

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
APP_NAME="bookmarker"
DIST_DIR="$SCRIPT_DIR/dist"
BUILD_DIR="$SCRIPT_DIR/build"
VENV_DIR="$SCRIPT_DIR/.venv"
BUNDLE_DIR="$DIST_DIR/$APP_NAME"
LAUNCHER="$BUNDLE_DIR/$APP_NAME"

echo "=== Bookmarker Build Script ==="
echo ""

# Check if we're in a virtual environment, if not activate or create one
if [ -z "$VIRTUAL_ENV" ]; then
    if [ -d "$VENV_DIR" ]; then
        echo "Activating virtual environment..."
        source "$VENV_DIR/bin/activate"
    else
        echo "Creating virtual environment..."
        python3 -m venv "$VENV_DIR"
        source "$VENV_DIR/bin/activate"
    fi
fi

# Install dependencies
echo "Installing dependencies..."
pip install --quiet --upgrade pip
pip install --quiet -r "$SCRIPT_DIR/requirements.txt"
pip install --quiet pyinstaller

# Clean previous builds
echo "Cleaning previous builds..."
rm -rf "$DIST_DIR" "$BUILD_DIR"

# Run PyInstaller (all config lives in bookmarker.spec)
echo "Building onedir bundle with PyInstaller..."
cd "$SCRIPT_DIR"
pyinstaller --noconfirm --clean "$SCRIPT_DIR/bookmarker.spec"

# Check if build succeeded
if [ ! -f "$LAUNCHER" ]; then
    echo "ERROR: Build failed - launcher not found at $LAUNCHER"
    exit 1
fi

echo ""
echo "Build successful!"
echo "Bundle:   $BUNDLE_DIR"
echo "Launcher: $LAUNCHER"
echo ""
echo "Run the launcher above directly for a local test, or package the release"
echo "tarball via .github/workflows/release.yml."
