; ═══════════════════════════════════════════════════════════
;   FLOWRA Busy Sync Agent — Inno Setup installer script
;   Generates a friendly Windows installer (.exe wrapper).
;
;   Prerequisite: Inno Setup 6 from https://jrsoftware.org/isdl.php
;   Compile:      build.bat (or right-click installer.iss → Compile)
;   Output:       installer/FLOWRA_Busy_Agent_Setup.exe
; ═══════════════════════════════════════════════════════════

#define MyAppName        "FLOWRA Busy Sync Agent"
#define MyAppVersion     "1.0.0"
#define MyAppPublisher   "FLOWRA"
#define MyAppURL         "https://flowralive.in"
#define MyAppExeName     "FLOWRA_Busy_Agent.exe"

[Setup]
AppId={{F1OWRA-BUSY-AGNT-2026-WIN}}
AppName={#MyAppName}
AppVersion={#MyAppVersion}
AppPublisher={#MyAppPublisher}
AppPublisherURL={#MyAppURL}
AppSupportURL={#MyAppURL}/support
AppUpdatesURL={#MyAppURL}
DefaultDirName={autopf}\FLOWRA\BusyAgent
DefaultGroupName=FLOWRA
DisableProgramGroupPage=yes
LicenseFile=
OutputDir=installer
OutputBaseFilename=FLOWRA_Busy_Agent_Setup
SetupIconFile=src\flowra.ico
UninstallDisplayIcon={app}\{#MyAppExeName}
Compression=lzma2/ultra64
SolidCompression=yes
WizardStyle=modern
ArchitecturesInstallIn64BitMode=x64
ArchitecturesAllowed=x64
PrivilegesRequired=lowest
PrivilegesRequiredOverridesAllowed=dialog

[Languages]
Name: "english"; MessagesFile: "compiler:Default.isl"

[Tasks]
Name: "desktopicon"; Description: "Create a desktop shortcut"; GroupDescription: "Additional shortcuts:"; Flags: unchecked
Name: "startupicon"; Description: "Run FLOWRA Busy Agent at Windows startup"; GroupDescription: "Auto-start:"; Flags: unchecked

[Files]
Source: "dist\{#MyAppExeName}"; DestDir: "{app}"; Flags: ignoreversion
Source: "src\BUSY_README.md";   DestDir: "{app}"; Flags: ignoreversion isreadme

[Icons]
Name: "{group}\{#MyAppName}";        Filename: "{app}\{#MyAppExeName}"; IconFilename: "{app}\{#MyAppExeName}"
Name: "{group}\Uninstall {#MyAppName}"; Filename: "{uninstallexe}"
Name: "{autodesktop}\{#MyAppName}";  Filename: "{app}\{#MyAppExeName}"; Tasks: desktopicon
Name: "{userstartup}\{#MyAppName}";  Filename: "{app}\{#MyAppExeName}"; Tasks: startupicon

[Run]
Filename: "{app}\{#MyAppExeName}"; Description: "Launch FLOWRA Busy Agent now"; Flags: nowait postinstall skipifsilent

[Code]
{ Pre-install check: warn if Microsoft Access Database Engine is missing.
  pyodbc cannot read .bds files without it. }
function InitializeSetup(): Boolean;
var
  HasAccessDriver: Boolean;
  ResultCode: Integer;
begin
  Result := True;
  HasAccessDriver :=
    RegKeyExists(HKLM, 'SOFTWARE\WOW6432Node\Microsoft\Office\16.0\Access Connectivity Engine\InstallRoot') or
    RegKeyExists(HKLM, 'SOFTWARE\Microsoft\Office\16.0\Access Connectivity Engine\InstallRoot') or
    RegKeyExists(HKLM, 'SOFTWARE\WOW6432Node\Microsoft\Office\14.0\Access Connectivity Engine\InstallRoot');
  if not HasAccessDriver then
  begin
    if MsgBox(
      'Microsoft Access Database Engine is required to read Busy data files (.bds).' + #13#10 + #13#10 +
      'Without it, FLOWRA Busy Agent cannot connect to your Busy data.' + #13#10 + #13#10 +
      'Do you want to open the Microsoft download page now?',
      mbConfirmation, MB_YESNO) = IDYES then
    begin
      ShellExec('open',
                'https://www.microsoft.com/en-us/download/details.aspx?id=54920',
                '', '', SW_SHOWNORMAL, ewNoWait, ResultCode);
    end;
  end;
end;
