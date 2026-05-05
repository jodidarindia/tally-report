# FLOWRA Busy Sync Agent — Windows Build Kit

This folder contains everything needed to compile a one-click `.exe` installer
of the FLOWRA Busy Sync Agent on a **Windows 10/11** PC.

> **You don't need to be a developer.** Follow the 4 steps below.

---

## Prerequisites (one-time, ~10 minutes)

### 1. Install Python 3.9+
Download from <https://www.python.org/downloads/> →
**IMPORTANT** during install, tick "**Add Python to PATH**".

Verify in Command Prompt:
```cmd
python --version
```
Should print something like `Python 3.11.7`.

### 2. Install Microsoft Access Database Engine 64-bit
Required so the agent can read Busy `.bds` files (which are MS Access databases).

Download: <https://www.microsoft.com/en-us/download/details.aspx?id=54920> → install.

### 3. (Optional but recommended) Install Inno Setup
Creates a friendly Windows installer wrapper around the `.exe`. Without it you
still get a working standalone `.exe`, just without "next-next-finish" UX.

Download free from <https://jrsoftware.org/isdl.php> → install with defaults.

---

## Build steps (~3 minutes)

1. **Extract** this folder anywhere on your PC (e.g., `C:\flowra-build\`).
2. **Open Command Prompt** in that folder.
   *Tip*: hold Shift, right-click the folder in Explorer → "Open in Terminal" /
   "Open PowerShell window here".
3. **Run**:
   ```cmd
   build.bat
   ```
4. Wait ~2 minutes for compilation. When you see `SUCCESS!`, you'll find:
   - `dist\FLOWRA_Busy_Agent.exe` — standalone executable (no install needed)
   - `installer\FLOWRA_Busy_Agent_Setup.exe` — friendly installer (only if Inno Setup was installed)

---

## Distribute to your customers

Send `installer\FLOWRA_Busy_Agent_Setup.exe` to your customers. They will:

1. Double-click the `.exe`.
2. Click **Yes** on the SmartScreen warning (it appears because the file isn't
   code-signed — see "Code signing" below).
3. Choose tasks: ☐ Desktop shortcut, ☐ Run at Windows startup.
4. Click Install. Done.

The installer:
- Auto-detects if Microsoft Access Database Engine is missing and prompts the
  user to download it.
- Creates Start Menu, optional Desktop, and optional Startup shortcuts.
- Includes a clean Uninstaller (Settings → Apps → FLOWRA Busy Sync Agent → Uninstall).

---

## Folder structure after build

```
busy-agent-build/
├── build.bat                          (you ran this)
├── flowra-busy-agent.spec             (PyInstaller config)
├── installer.iss                      (Inno Setup config)
├── version_info.txt                   (Windows EXE metadata)
├── README-build.md                    (this file)
├── src/
│   ├── flowra_busy_agent_v1.py        (Python source — never edit on Windows; pull from /app/desktop-agent/)
│   ├── flowra.ico                     (Windows icon — multi-size)
│   └── BUSY_README.md                 (end-user docs, bundled into installer)
├── .venv/                             (created by build.bat)
├── build/                             (PyInstaller intermediates — safe to delete)
├── dist/
│   └── FLOWRA_Busy_Agent.exe          ⭐ standalone executable
└── installer/
    └── FLOWRA_Busy_Agent_Setup.exe    ⭐ friendly installer (with Inno Setup)
```

---

## Updating the agent

When the agent script changes (`flowra_busy_agent_v1.py`):

1. Replace `src/flowra_busy_agent_v1.py` with the new version.
2. Re-run `build.bat`. New EXE in ~2 minutes.

The script lives in the FLOWRA repo at `/app/desktop-agent/flowra_busy_agent_v1.py`.

---

## Code signing (when ready for production)

The compiled `.exe` is **unsigned**, which means Windows shows
"Windows protected your PC" / "Unrecognized publisher" SmartScreen warnings.
That's fine for early users but kills conversions at scale.

To fix:
1. Buy a code-signing certificate (Sectigo / DigiCert / SSL.com — ~₹15,000/year).
   *EV certificates* (~₹40,000/year) bypass SmartScreen entirely.
2. Use `signtool.exe` (comes with Windows SDK):
   ```cmd
   signtool sign /tr http://timestamp.sectigo.com /td sha256 /fd sha256 /a dist\FLOWRA_Busy_Agent.exe
   signtool sign /tr http://timestamp.sectigo.com /td sha256 /fd sha256 /a installer\FLOWRA_Busy_Agent_Setup.exe
   ```
3. Add `signtool sign...` lines to `build.bat` after the PyInstaller and Inno
   Setup steps.

---

## Troubleshooting

| Error | Fix |
|-------|-----|
| `python : The term 'python' is not recognized` | Python not in PATH. Reinstall Python with the "Add to PATH" checkbox ticked. |
| `pyodbc.InterfaceError: IM002` | MS Access Database Engine not installed. See Prerequisite #2. |
| `pyinstaller : not found` | Open a *new* Command Prompt; `build.bat` re-creates the venv on first run. |
| `LINK : fatal error LNK1158: cannot run 'rc.exe'` | Visual C++ Build Tools missing. Install "Build Tools for Visual Studio" → "Desktop development with C++" workload. |
| Antivirus deletes the EXE during build | Add the build folder to your AV's exclusion list. PyInstaller's bootloader looks suspicious to heuristic AV — fixes once code-signed. |
| Compiled `.exe` is huge (~80 MB) | Normal for a PyInstaller single-file build. UPX compression in spec already cuts ~50 %. |

---

## Support

Issues building? Email **hello@flowralive.in** with the contents of `build/warn-flowra_busy_agent_v1.txt` and we'll help.
