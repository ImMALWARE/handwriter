# -*- mode: python ; coding: utf-8 -*-
from sys import platform

icon_path = 'img/handwriter.png'
if platform == 'win32':
    icon_path = 'img/handwriter.ico'
elif platform == 'darwin':
    icon_path = 'img/handwriter.icns'

a = Analysis(
    ['handwriter/main.py'],
    pathex=[],
    binaries=[],
    datas=[('handwriter/translations/*.qm', 'handwriter/translations/'), ('img/handwriter.png', 'img/')],
    hiddenimports=[],
    hookspath=[],
    hooksconfig={},
    runtime_hooks=[],
    excludes=[],
    noarchive=False,
    optimize=0,
)
pyz = PYZ(a.pure)

exe = EXE(
    pyz,
    a.scripts,
    [],
    exclude_binaries=True,
    name='Handwriter',
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=True,
    console=False,
    icon=icon_path,
    disable_windowed_traceback=False,
    argv_emulation=False,
    target_arch=None,
    codesign_identity=None,
    entitlements_file=None,
)
coll = COLLECT(
    exe,
    a.binaries,
    a.datas,
    strip=False,
    upx=True,
    upx_exclude=[],
    name='Handwriter',
)