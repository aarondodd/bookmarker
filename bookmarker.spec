# pyinstaller spec for Bookmarker. Run via `pyinstaller --noconfirm --clean bookmarker.spec`.
# --windowed --onedir: produces dist/bookmarker/ containing bookmarker[.exe] +
# sibling .pyd/.dll/.so + data files. The Inno Setup installer (installer.iss)
# recurses the whole tree into the install dir; the Linux release ships the tree
# as a tar.gz. Onedir avoids the onefile self-extraction to a temp dir on every
# launch -- faster startup, no orphan _MEI* dirs on crash, fewer antivirus hits,
# and (critically) it is what the in-app self-updater expects: a directory it can
# swap in place (Linux) or an installer can replace via Restart Manager (Windows).
# -*- mode: python ; coding: utf-8 -*-
from PyInstaller.utils.hooks import collect_all

datas = []
binaries = []
hiddenimports = ['PyQt6', 'PyQt6.QtCore', 'PyQt6.QtGui', 'PyQt6.QtWidgets']
tmp_ret = collect_all('PyQt6')
datas += tmp_ret[0]; binaries += tmp_ret[1]; hiddenimports += tmp_ret[2]

# pynput powers the global hotkey (utils/hotkey.py). It selects its platform
# backend at runtime via importlib (pynput.keyboard._xorg / _win32 / _darwin),
# which PyInstaller's static analysis cannot see -- without collect_all the
# frozen build imports pynput but the backend is absent, so the hotkey feature
# silently disables itself ("pynput not available"). Collect the whole package
# so every OS backend ships.
tmp_ret = collect_all('pynput')
datas += tmp_ret[0]; binaries += tmp_ret[1]; hiddenimports += tmp_ret[2]

# pynput's Linux backend (pynput.keyboard._xorg) imports python-xlib (top-level
# module name `Xlib`), a separate package pynput depends on only on Linux. It is
# imported dynamically inside the backend, so collect_all('pynput') does not pull
# it. Collect it explicitly, guarded so Windows/macOS CI builds (where Xlib is
# not installed) don't fail here.
try:
    import Xlib  # noqa: F401  -- presence probe; only on Linux
    tmp_ret = collect_all('Xlib')
    datas += tmp_ret[0]; binaries += tmp_ret[1]; hiddenimports += tmp_ret[2]
except ImportError:
    pass

# Tray icon PNG is loaded at runtime via Path(__file__).parent / "bookmark.png"
# (utils/icon.py). PyInstaller's static analysis does not treat it as a data
# dependency, so ship it explicitly at the same package-relative location the
# frozen module resolves against.
datas += [('bookmarker/utils/bookmark.png', 'bookmarker/utils')]

# The browser-sync extension is extracted from here to user space by
# automation/installer.py, so it must ship inside the frozen bundle.
datas += [('bookmarker/resources/extension', 'bookmarker/resources/extension')]


a = Analysis(
    ['main.py'],
    pathex=[],
    binaries=binaries,
    datas=datas,
    hiddenimports=hiddenimports,
    hookspath=[],
    hooksconfig={},
    runtime_hooks=[],
    excludes=['PyQt6.Qt3D', 'PyQt6.QtBluetooth', 'PyQt6.QtDBus', 'PyQt6.QtDesigner', 'PyQt6.QtHelp', 'PyQt6.QtMultimedia', 'PyQt6.QtMultimediaWidgets', 'PyQt6.QtNfc', 'PyQt6.QtOpenGL', 'PyQt6.QtOpenGLWidgets', 'PyQt6.QtPdf', 'PyQt6.QtPdfWidgets', 'PyQt6.QtPositioning', 'PyQt6.QtQml', 'PyQt6.QtQuick', 'PyQt6.QtQuick3D', 'PyQt6.QtQuickWidgets', 'PyQt6.QtRemoteObjects', 'PyQt6.QtSensors', 'PyQt6.QtSerialPort', 'PyQt6.QtSpatialAudio', 'PyQt6.QtSql', 'PyQt6.QtStateMachine', 'PyQt6.QtSvg', 'PyQt6.QtSvgWidgets', 'PyQt6.QtTest', 'PyQt6.QtTextToSpeech', 'PyQt6.QtWebChannel', 'PyQt6.QtWebSockets', 'PyQt6.QtXml', 'PyQt6.lupdate', 'PyQt6.uic'],
    noarchive=False,
    optimize=0,
)
pyz = PYZ(a.pure)

# Onedir split: EXE holds only the launcher (exclude_binaries=True); COLLECT
# gathers the binaries + zipfiles + datas next to it in dist/bookmarker/.
exe = EXE(
    pyz,
    a.scripts,
    [],
    exclude_binaries=True,
    name='bookmarker',
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=True,
    upx_exclude=[],
    console=False,
    disable_windowed_traceback=False,
    argv_emulation=False,
    target_arch=None,
    codesign_identity=None,
    entitlements_file=None,
)

coll = COLLECT(
    exe,
    a.binaries,
    a.zipfiles,
    a.datas,
    strip=False,
    upx=True,
    upx_exclude=[],
    name='bookmarker',
)
