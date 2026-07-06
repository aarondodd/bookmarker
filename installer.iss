; Inno Setup script for Bookmarker.
;
; Wraps the PyInstaller --onedir bundle (dist\bookmarker\) in a proper Windows
; installer: Start Menu entry, Add/Remove Programs registration, per-user install
; with no admin required (the user can elevate via the UAC dialog for a
; system-wide install if they want).
;
; Compile via: ISCC.exe /DAppVersion=0.1.4 installer.iss
; The CI workflow passes /DAppVersion derived from the release tag.

#ifndef AppVersion
  #define AppVersion "0.0.0-dev"
#endif

[Setup]
; Stable AppId so future installers upgrade in place instead of stacking
; side-by-side entries in Add/Remove Programs. Do NOT change this value.
AppId={{1F6B8A6C-F768-42C5-9C3A-9E05B1F1B38B}}
AppName=Bookmarker
AppVersion={#AppVersion}
AppVerName=Bookmarker {#AppVersion}
AppPublisher=Aaron Dodd
AppPublisherURL=https://github.com/aarondodd/bookmarker
AppSupportURL=https://github.com/aarondodd/bookmarker/issues
AppUpdatesURL=https://github.com/aarondodd/bookmarker/releases
DefaultDirName={autopf}\Bookmarker
DefaultGroupName=Bookmarker
DisableProgramGroupPage=yes
LicenseFile=LICENSE
OutputDir=Output
OutputBaseFilename=bookmarker-setup-{#AppVersion}
Compression=lzma2/ultra
SolidCompression=yes
WizardStyle=modern
ArchitecturesAllowed=x64compatible
ArchitecturesInstallIn64BitMode=x64compatible
; lowest = per-user by default, no admin prompt. The override dialog lets the
; user elevate for a Program Files install if they pick it.
PrivilegesRequired=lowest
PrivilegesRequiredOverridesAllowed=dialog
UninstallDisplayName=Bookmarker {#AppVersion}
UninstallDisplayIcon={app}\bookmarker.exe
MinVersion=10.0.17763
; CloseApplications + RestartApplications make Windows Restart Manager close the
; running bookmarker.exe before the install, then relaunch it after. Required
; for the in-app self-updater (utils/updater.py), which downloads this same
; installer and runs it silently; without these a silent upgrade would fail with
; "file in use" when the existing install is being replaced.
CloseApplications=yes
RestartApplications=yes

[Languages]
Name: "english"; MessagesFile: "compiler:Default.isl"

[Tasks]
Name: "desktopicon"; Description: "{cm:CreateDesktopIcon}"; GroupDescription: "{cm:AdditionalIcons}"; Flags: unchecked

[Files]
; PyInstaller --onedir produces dist\bookmarker\ with the launcher .exe plus
; sibling .pyd / .dll / data files (PyQt6). Recurse the whole tree into {app}
; preserving the layout the launcher expects to find.
Source: "dist\bookmarker\*"; DestDir: "{app}"; Flags: ignoreversion recursesubdirs createallsubdirs

[Icons]
Name: "{group}\Bookmarker"; Filename: "{app}\bookmarker.exe"
Name: "{group}\{cm:UninstallProgram,Bookmarker}"; Filename: "{uninstallexe}"
Name: "{autodesktop}\Bookmarker"; Filename: "{app}\bookmarker.exe"; Tasks: desktopicon

[Run]
Filename: "{app}\bookmarker.exe"; Description: "{cm:LaunchProgram,Bookmarker}"; Flags: nowait postinstall skipifsilent
