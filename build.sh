#!/bin/bash
#
# Build script for Bookmarker (Linux / macOS)
# Produces a PyInstaller --onedir bundle at dist/bookmarker/ from bookmarker.spec.
#
# By default it also installs the bundle for local use: the whole directory
# goes to ~/.local/share/bookmarker/ and ~/bin/bookmarker is symlinked at the
# launcher. Set BOOKMARKER_NO_INSTALL=1 to build only (CI uses this to produce
# the release tarball without touching the developer's ~/bin).
#

set -e

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
APP_NAME="bookmarker"
DIST_DIR="$SCRIPT_DIR/dist"
BUILD_DIR="$SCRIPT_DIR/build"
VENV_DIR="$SCRIPT_DIR/.venv"
BUNDLE_DIR="$DIST_DIR/$APP_NAME"
LAUNCHER="$BUNDLE_DIR/$APP_NAME"
INSTALL_DIR="$HOME/.local/share/$APP_NAME"
BIN_DIR="$HOME/bin"

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
echo "Bundle: $BUNDLE_DIR"
echo "Launcher: $LAUNCHER"

if [ "${BOOKMARKER_NO_INSTALL:-}" = "1" ]; then
    echo ""
    echo "BOOKMARKER_NO_INSTALL=1 set - skipping local install."
    exit 0
fi

# Install the whole onedir bundle for local use. A single-file copy no longer
# works under --onedir, so install the directory and symlink the launcher.
echo ""
echo "Installing bundle to $INSTALL_DIR..."
rm -rf "$INSTALL_DIR"
mkdir -p "$(dirname "$INSTALL_DIR")"
cp -r "$BUNDLE_DIR" "$INSTALL_DIR"

mkdir -p "$BIN_DIR"
ln -sfn "$INSTALL_DIR/$APP_NAME" "$BIN_DIR/$APP_NAME"

echo ""
echo "=== Installation Complete ==="
echo "Bundle installed to: $INSTALL_DIR"
echo "Launcher symlinked at: $BIN_DIR/$APP_NAME"
echo ""
echo "Make sure $BIN_DIR is in your PATH:"
echo "  export PATH=\"\$HOME/bin:\$PATH\""
echo ""
