# PyInstaller spec for FLOWRA Tally Sync Agent.
# Built by build.bat — do not run directly.
# Output: dist/FlowraTallyAgent.exe (single-file, ~25–35 MB compressed).

# -*- mode: python ; coding: utf-8 -*-
import os

block_cipher = None

a = Analysis(
    ['flowra_gui.py'],
    pathex=[],
    binaries=[],
    # The agent script is bundled as a data file so flowra_gui.py can
    # import it via `import tally_sync_agent_v9` (imports work because
    # PyInstaller adds _MEIPASS to sys.path).
    datas=[
        ('tally_sync_agent_v9.py', '.'),
        # Include the optional icon if it exists; harmless if missing.
        *( [('flowra.ico', '.')]        if os.path.exists('flowra.ico')        else [] ),
        *( [('flowra_logo.png', '.')]   if os.path.exists('flowra_logo.png')   else [] ),
    ],
    hiddenimports=[
        # Modules the agent imports dynamically that PyInstaller can't see
        'requests',
        'xmltodict',
        'schedule',
        'dotenv',
        'cryptography',
        'cryptography.fernet',
        'cryptography.hazmat.primitives.kdf.pbkdf2',
        'websockets',
        'websockets.server',
        'websockets.client',
        'asyncio',
        'tally_sync_agent_v9',
        # GUI tray + icon generation
        'pystray',
        'pystray._win32',
        'PIL',
        'PIL.Image',
        'PIL.ImageDraw',
        'PIL.ImageFont',
        'PIL.ImageTk',
        # Auto-start registry on Windows
        'winreg',
    ],
    hookspath=[],
    hooksconfig={},
    runtime_hooks=[],
    excludes=[
        # Cut bloat we don't use
        'matplotlib', 'numpy', 'pandas', 'scipy',
        'tkinter.test', 'test', 'unittest',
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
    name='FlowraTallyAgent',
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=True,
    upx_exclude=[],
    runtime_tmpdir=None,
    console=False,            # ← Windowed app (no black console)
    disable_windowed_traceback=False,
    target_arch=None,
    codesign_identity=None,
    entitlements_file=None,
    icon='flowra.ico' if os.path.exists('flowra.ico') else None,
    version='version_info.txt' if os.path.exists('version_info.txt') else None,
)
