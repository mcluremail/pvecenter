# -*- mode: python ; coding: utf-8 -*-
# PyInstaller spec for Windows build of PVE Center.
# Usage: pyinstaller packaging/pve-center-win.spec --noconfirm

block_cipher = None

a = Analysis(
    ['pve_center/__main__.py'],
    pathex=[],
    binaries=[],
    datas=[
        ('pve_center/ui/i18n/*.json', 'pve_center/ui/i18n'),
        ('pve_center/ui/*.svg', 'pve_center/ui'),
    ],
    hiddenimports=[
        'PySide6.QtCore',
        'PySide6.QtWidgets',
        'PySide6.QtGui',
    ],
    hookspath=[],
    runtime_hooks=[],
    excludes=[],
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