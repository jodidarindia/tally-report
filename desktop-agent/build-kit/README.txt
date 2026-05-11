FLOWRA Tally Sync Agent — Build Kit (v9.8.9)
=============================================

This folder produces a single Windows .exe that bundles the FLOWRA Tally
Sync Agent and its lightweight Tkinter GUI launcher into one file your
customers can run with no Python install required.


CONTENTS
--------
  build.bat                  →  Double-click this on Windows to build.
  flowra_gui.py              →  Tkinter GUI wrapper (Status / Settings / Logs / About).
  tally_sync_agent_v9.py     →  The headless sync agent (source of truth).
  agent.spec                 →  PyInstaller spec — bundles everything into one .exe.
  requirements.txt           →  Pinned build + runtime dependencies.
  version_info.txt           →  Windows file metadata (Publisher, Version, Copyright).
  flowra.ico   (optional)    →  Drop a 256×256 .ico here to brand the .exe & taskbar.
  README.txt                 →  This file.


PREREQUISITES (Windows machine)
-------------------------------
  • Windows 10 / 11 (64-bit recommended).
  • Python 3.10 or newer (3.14.5 fully supported via the latest Pillow /
    cryptography / PyInstaller wheels — see requirements.txt for minimums).
        Download:  https://www.python.org/downloads/
        IMPORTANT: tick "Add Python to PATH" during install.
  • Internet connection for the first build (to download pip packages).
  • ~500 MB free disk for the build cache + .venv.


HOW TO BUILD
------------
  1. Copy this entire folder to your Windows machine.
  2. Double-click  build.bat.
  3. Wait 2–4 minutes for the first build (subsequent builds are ~30 s).
  4. When you see "BUILD SUCCESSFUL", look in this folder:

         FlowraTallyAgent_v9.8.9.exe        ← single-file, ready to ship

That's it. Distribute the .exe directly, or upload it to your FLOWRA
Setup page so customers can download it.

IF THE BUILD FAILS
------------------
  The full pip / PyInstaller output is saved to  build.log  in this
  folder. Open it in Notepad, scroll to the bottom, and you'll see the
  exact error. Mail that file to support@flowra.in and we'll debug it.

  Common fixes:
    • "Could not find a version of pyinstaller / Pillow / cryptography"
      →  pip can't see a wheel for your Python. Upgrade pip first:
            .venv\Scripts\python.exe -m pip install --upgrade pip
         then re-run build.bat. If still failing, your Python is newer
         than the wheels published on PyPI — wait a few weeks or use
         a slightly older Python release.
    • Long compiler errors mentioning "Microsoft Visual C++ 14.0"  →
      pip couldn't find a wheel and is trying to compile from source.
      Easiest fix: install Microsoft C++ Build Tools from
      https://visualstudio.microsoft.com/visual-cpp-build-tools/  OR
      switch to a Python version that does have a wheel.
    • "pip: SSL: CERTIFICATE_VERIFY_FAILED"  →  corporate proxy or
      out-of-date Windows TLS roots. Run on a non-corporate network
      for the first build, or set HTTPS_PROXY in the cmd window.


WHAT'S INSIDE THE .EXE
----------------------
  • Python 3.10 runtime (slim)
  • The agent script + GUI launcher
  • requests, xmltodict, schedule, dotenv, cryptography, websockets
  Idle RAM:   ~25 MB (GUI only)
  Sync RAM:   ~80 MB peak (during a full Tally export)
  Disk:       ~25–35 MB compressed single-file


SMARTSCREEN WARNING (FIRST RUN)
-------------------------------
Without code-signing, Windows will show:
        "Windows protected your PC"  →  Unknown publisher
The customer must click "More info" → "Run anyway".

This is normal for unsigned binaries. To remove it, purchase a
Windows Authenticode code-signing certificate (~₹3,000/year — Sectigo,
DigiCert, Comodo) and add `--codesign-identity` to the spec. Strongly
recommended before public launch.


CONFIG STORAGE
--------------
First-time users open the .exe, go to "Settings", and enter:
   • FLOWRA Server URL   (e.g. https://yourcompany.flowra.in)
   • Login Email + Password
   • Tally Host / Port (default localhost:9000)

The GUI saves these to:
   %LOCALAPPDATA%\Flowra\agent.env       (per-user, ACL-restricted)

Logs are written to:
   %LOCALAPPDATA%\Flowra\logs\agent_YYYYMMDD.log


SYSTEM-TRAY BEHAVIOUR
---------------------
• Closing the window minimises FLOWRA to the system tray (notification
  area near the clock). The sync service keeps running in the background.
• Right-click the tray icon for: Show, Sync Now, Open Logs Folder,
  Toggle "Auto-start with Windows", Quit.
• "Quit FLOWRA" is the ONLY way to fully stop the service. Clicking
  the X just hides the window.


AUTO-START WITH WINDOWS
-----------------------
On first launch the app asks once whether to launch on Windows boot.
Toggle it any time from:
   • Settings tab → "Start FLOWRA automatically when Windows starts"
   • Tray icon → right-click → "Auto-start with Windows"
   • Command line:
        FlowraTallyAgent.exe --register-startup
        FlowraTallyAgent.exe --unregister-startup

Auto-start uses the per-user registry key
   HKCU\Software\Microsoft\Windows\CurrentVersion\Run\FlowraTallyAgent
so no admin rights are required. When triggered by Windows the GUI
opens directly minimised to tray (it passes itself the --minimized flag).


REBUILDING WHEN THE AGENT CHANGES
---------------------------------
Whenever a new agent version drops:
  1. Replace `tally_sync_agent_v9.py` in this folder with the new copy.
  2. Bump the version strings in:
        flowra_gui.py        →   APP_VERSION   = "v9.x.x"
        version_info.txt     →   filevers / prodvers / FileVersion / ProductVersion
        build.bat            →   output filename "FlowraTallyAgent_v9.x.x.exe"
  3. Run build.bat again.

A `.venv` and `build/` cache will be reused on subsequent builds.
Delete them if you ever want a fully clean rebuild.


SUPPORT
-------
If the build fails, copy the entire console output and email it to
support@flowra.in along with:
   • Python version  (run:  python -V )
   • Windows version (run:  ver        )
