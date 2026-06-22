# -*- mode: python ; coding: utf-8 -*-
# PyInstaller spec for Windows build of PVE Center.
# Usage: pyinstaller packaging/pve-center-win.spec --noconfirm
import os

# SPECPATH is the directory containing this spec file (packaging/).
# Project root is one level up.
_root = os.path.dirname(SPECPATH)

block_cipher = None

a = Analysis(
    [os.path.join(_root, 'pve_center', '__main__.py')],
    pathex=[_root],
    binaries=[],
    datas=[
        (os.path.join(_root, 'pve_center', 'ui', 'i18n', '*.json'), 'pve_center/ui/i18n'),
        (os.path.join(_root, 'pve_center', 'ui', '*.svg'), 'pve_center/ui'),
    ],
    hiddenimports=[
        'PySide6.QtCore',
        'PySide6.QtWidgets',
        'PySide6.QtGui',
    ],
    hookspath=[],
    runtime_hooks=[],
    excludes=['pyqtgraph.opengl', 'OpenGL'],
    cipher=block_cipher,
    noarchive=False,
)

pyz = PYZ(a.pure, a.zipped_data, cipher=block_cipher)

exe = EXE(
    pyz,
    a.scripts,
    [],
    exclude_binaries=True,
    name='pvecenter',
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=True,
    console=False,
    icon=None,
)

coll = COLLECT(
    exe,
    a.binaries,
    a.zipfiles,
    a.datas,
    strip=False,
    upx=True,
    upx_exclude=[],
    name='pvecenter',
)