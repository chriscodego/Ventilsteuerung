; Inno Setup script for the Magnetventilsteuerung per-user installer.
; Build via: python packaging/build.py  (passes /DMyAppVersion=X.Y.Z)

#ifndef MyAppVersion
  #define MyAppVersion "0.0.0"
#endif
#ifndef BundleDir
  #define BundleDir "..\dist\Magnetventilsteuerung"
#endif
#define MyAppName "Magnetventilsteuerung"
#define MyAppExeName "Magnetventilsteuerung.exe"

[Setup]
AppId={{2E7A9C14-5B3D-4F88-A1C6-8D2F0B7E4A91}}
AppName={#MyAppName}
AppVersion={#MyAppVersion}
AppPublisher=Christian Gerken
DefaultDirName={userpf}\{#MyAppName}
DefaultGroupName={#MyAppName}
PrivilegesRequired=lowest
OutputDir=..\dist\installer
OutputBaseFilename=Ventilsteuerung-Setup-{#MyAppVersion}
Compression=lzma2
SolidCompression=yes
CloseApplications=yes
WizardStyle=modern
DisableProgramGroupPage=yes

[Languages]
Name: "german"; MessagesFile: "compiler:Languages\German.isl"

[Files]
Source: "{#BundleDir}\*"; DestDir: "{app}"; Flags: recursesubdirs ignoreversion
; User data: seed on first install, never overwrite on update, keep on uninstall
Source: "..\GUI\programs.json"; DestDir: "{app}"; Flags: onlyifdoesntexist uninsneveruninstall
Source: "..\GUI\emergency.json"; DestDir: "{app}"; Flags: onlyifdoesntexist uninsneveruninstall

[Icons]
Name: "{userprograms}\{#MyAppName}"; Filename: "{app}\{#MyAppExeName}"
Name: "{userdesktop}\{#MyAppName}"; Filename: "{app}\{#MyAppExeName}"

[Run]
Filename: "{app}\{#MyAppExeName}"; Description: "{#MyAppName} starten"; Flags: nowait postinstall
