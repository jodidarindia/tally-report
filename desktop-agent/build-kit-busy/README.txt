FLOWRA Busy Sync Agent - Build Kit (v1.3)
==========================================

This folder produces a single Windows .exe that bundles the FLOWRA Busy
Sync Agent and its Tkinter GUI (identical look-and-feel to the FLOWRA
Tally Sync Agent v9.8.30) into one file your customers can run with no
Python install required.

WHAT CHANGED IN v1.3 (Feb 2026)
-------------------------------
* pyodbc is now bundled inside FlowraBusyAgent.exe (was missing in v1.2 —
  caused "ModuleNotFoundError: No module named 'pyodbc'" on first sync).
* Friendlier error messages when the Access ODBC driver is missing on
  the customer PC.
* Requires the "Microsoft Access Database Engine 2016 Redistributable"
  (free, 64-bit) if the customer PC doesn't already have it — download:
  https://www.microsoft.com/en-us/download/details.aspx?id=54920


CONTENTS
--------
  build.bat                  ->  Double-click this on Windows to build.
  flowra_busy_gui.py         ->  Tkinter GUI wrapper (Status / Settings / Logs / About).
  flowra_busy_agent.py       ->  The headless sync agent (source of truth).
  agent.spec                 ->  PyInstaller spec - bundles everything into one .exe.
  requirements.txt           ->  Pinned build + runtime dependencies.
  version_info.txt           ->  Windows file metadata (Publisher, Version, Copyright).
  flowra.ico   (optional)    ->  Drop a 256x256 .ico here to brand the .exe & taskbar.
  flowra_logo.png (optional) ->  40x40+ PNG for the in-app header + tray icon.
  README.txt                 ->  This file.


PREREQUISITES (Windows machine)
-------------------------------
  * Windows 10 / 11 (64-bit recommended).
  * Python 3.10 or newer (3.14.x fully supported).
        Download:  https://www.python.org/downloads/
        IMPORTANT: tick "Add Python to PATH" during install.
  * Internet connection for the first build.
  * ~500 MB free disk for the build cache + .venv.


HOW TO BUILD
------------
  1. Copy this entire folder to your Windows machine.
  2. Double-click  build.bat.
  3. Wait 2-4 minutes for the first build (subsequent builds are ~30 s).
  4. When you see "BUILD SUCCESSFUL", look in this folder:

         FlowraBusyAgent_v1.2.exe        <- single-file, ready to ship

Upload the .exe to your FLOWRA Setup page (busy channel) and update
these manifests with the new sha256 + size_bytes:

  backend/agent_release.json           (server-side latest)
  frontend/public/agent-latest.json    (public download page)


CONFIG STORAGE
--------------
On first launch the user opens the .exe, goes to "Settings", and:
  1. Enters Login Email + Password  ->  clicks "Login to FLOWRA".
     (login fields lock after success. Sign out to switch users.)
  2. Picks the Busy data folder (e.g. C:\Busy21\Data\).
     Companies + FYs are auto-detected immediately.
  3. Selects the Starting FY chip.
  4. Clicks  "Save & Start Sync".

The GUI saves these to:
   %LOCALAPPDATA%\Flowra\agent_busy.env       (per-user, ACL-restricted)

Logs are written to:
   %LOCALAPPDATA%\Flowra\logs_busy\busy_agent_YYYYMMDD.log


SYSTEM-TRAY BEHAVIOUR
---------------------
* Closing the window minimises to the system tray. The sync service
  keeps running in the background.
* Right-click the tray icon for: Show, Sync Now, Open Logs Folder,
  Toggle "Auto-start with Windows", Quit.
* "Quit FLOWRA" is the ONLY way to fully stop the service.


AUTO-START WITH WINDOWS
-----------------------
Toggle from Settings -> "Start FLOWRA automatically when Windows starts",
or from the tray icon -> "Auto-start with Windows".
Uses the per-user registry key
   HKCU\Software\Microsoft\Windows\CurrentVersion\Run\FlowraBusyAgent
so no admin rights are required.


REBUILDING WHEN THE AGENT CHANGES
---------------------------------
1. Update flowra_busy_agent.py in this folder (or drop in a newer copy).
2. Bump the version strings in:
      flowra_busy_gui.py   ->   APP_VERSION = "v1.x"
      flowra_busy_agent.py ->   VERSION = "1.x"
      version_info.txt     ->   filevers / prodvers / FileVersion / ProductVersion
3. Run build.bat again.


SUPPORT
-------
If the build fails, copy the entire console output and email it to
support@flowra.in along with:
   * Python version  (run:  python -V )
   * Windows version (run:  ver        )
