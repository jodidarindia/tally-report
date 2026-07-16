# PyInstaller spec for FLOWRA Busy Sync Agent.
# Built by build.bat — do not run directly.
# Output: dist/FlowraBusyAgent.exe (single-file, ~25–35 MB compressed).

# -*- mode: python ; coding: utf-8 -*-
import os

block_cipher = None

a = Analysis(
    ['flowra_busy_gui.py'],
    pathex=[],
    binaries=[],
    # The agent script is bundled as a data file so flowra_busy_gui.py can
    # import it via `import flowra_busy_agent` (works because PyInstaller
    # adds _MEIPASS to sys.path).
    datas=[
        ('flowra_busy_agent.py', '.'),
        *( [('flowra.ico', '.')]        if os.path.exists('flowra.ico')        else [] ),
        *( [('flowra_logo.png', '.')]   if os.path.exists('flowra_logo.png')   else [] ),
    ],
    hiddenimports=[
        'requests',
        'schedule',
        'dotenv',
        'cryptography',
        'cryptography.fernet',
        'cryptography.hazmat.primitives.kdf.pbkdf2',
        'flowra_busy_agent',
        # Busy database access — pyodbc is imported LAZILY inside
        # _get_connection(), so PyInstaller's static analyzer misses it.
        # Declare it explicitly so the bundle contains the binary wheel.
        'pyodbc',
        # v1.4 — pywin32 for the ADODB / OLE DB (BSSData) provider path.
        # Also lazy-imported, so declare explicitly.
        'win32com', 'win32com.client', 'pywintypes', 'pythoncom',
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
    name='FlowraBusyAgent',
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
