# -*- mode: python ; coding: utf-8 -*-
"""
PyInstaller spec for FLOWRA Busy Sync Agent.
Produces a single-file Windows executable with bundled dependencies.

Build: pyinstaller flowra-busy-agent.spec --clean --noconfirm
Output: dist/FLOWRA_Busy_Agent.exe
"""
import os

block_cipher = None

a = Analysis(
    ['src/flowra_busy_agent_v1.py'],
    pathex=[],
    binaries=[],
    datas=[
        # Bundle the README so users can right-click the EXE -> Show README
        ('src/BUSY_README.md', '.'),
    ],
    hiddenimports=[
        'pyodbc',
        'requests',
        'tkinter',
        'tkinter.ttk',
        'tkinter.filedialog',
        'tkinter.messagebox',
        'json',
        'logging',
        'datetime',
        'threading',
        'queue',
        'gc',
        'urllib.parse',
    ],
    hookspath=[],
    hooksconfig={},
    runtime_hooks=[],
    excludes=[
        # Exclude unused stdlib modules to reduce size
        'matplotlib',
        'numpy',
        'pandas',
        'pytest',
        'PIL',
        'scipy',
    ],
    win_no_prefer_redirects=False,
    win_private_assemblies=False,
    cipher=block_cipher,
    noarchive=False,
)

pyz = PYZ(a.pure, a.zipped_data, cipher=block_cipher)

exe = EXE(
    pyz,
    a.scripts,
    a.binaries,
    a.zipfiles,
    a.datas,
    [],
    name='FLOWRA_Busy_Agent',
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=True,                # Compress with UPX if available (50 % smaller)
    upx_exclude=[],
    runtime_tmpdir=None,
    console=False,           # NO console window — pure GUI
    disable_windowed_traceback=False,
    argv_emulation=False,
    target_arch=None,
    codesign_identity=None,
    entitlements_file=None,
    icon='src/flowra.ico',
    version='version_info.txt',
)
