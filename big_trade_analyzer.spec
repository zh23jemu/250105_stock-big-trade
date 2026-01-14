# -*- mode: python ; coding: utf-8 -*-


a = Analysis(
    ['big_trade_analyzer.py'],
    pathex=[],
    binaries=[],
    datas=[('C:\\Coding\\!temp_project\\260105_stock-big-trade\\venv\\Lib\\site-packages\\akshare\\file_fold', 'akshare\\file_fold')],
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
    a.binaries,
    a.datas,
    [],
    name='big_trade_analyzer',
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=True,
    upx_exclude=[],
    runtime_tmpdir=None,
    console=False,
    disable_windowed_traceback=False,
    argv_emulation=False,
    target_arch=None,
    codesign_identity=None,
    entitlements_file=None,
)
