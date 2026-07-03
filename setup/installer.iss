#ifndef AppVersion
#define AppVersion "1.0"
#endif

#ifndef Arch
#define Arch "x64"
#endif

#if Arch == "arm64"
  #define AllowedArchs "arm64"
  #define Install64BitMode "arm64"
  #define OutName "Handwriter-Windows-ARM64"
#else
  #define AllowedArchs "x64 x86"
  #define Install64BitMode "x64"
  #define OutName "Handwriter-Windows-AMD64"
#endif

[Setup]
AppId={{7A91F605-725F-4C85-9F38-B8A8A1E9F10A}
PrivilegesRequired=lowest
AppName=Handwriter
AppVersion={#AppVersion}
AppPublisher=malw.link
UninstallDisplayIcon={app}\Handwriter.exe
DefaultDirName={autopf}\Handwriter
DefaultGroupName=Handwriter
OutputDir=..\Output
OutputBaseFilename={#OutName}
Compression=lzma
SolidCompression=yes
ArchitecturesAllowed={#AllowedArchs}
ArchitecturesInstallIn64BitMode={#Install64BitMode}
ChangesAssociations=yes
WizardStyle=modern dynamic
SetupIconFile=..\img\handwriter.ico

[Files]
Source: "..\dist\Handwriter\*"; DestDir: "{app}"; Flags: ignoreversion recursesubdirs createallsubdirs

[Languages]
Name: "english"; MessagesFile: "compiler:Default.isl"
Name: "russian"; MessagesFile: "compiler:Languages\Russian.isl"

[Registry]
Root: HKA; Subkey: "Software\Classes\.hwdoc"; ValueType: string; ValueName: ""; ValueData: "Handwriter.Document"; Flags: uninsdeletevalue
Root: HKA; Subkey: "Software\Classes\Handwriter.Document"; ValueType: string; ValueName: ""; ValueData: "Handwriter Document"; Flags: uninsdeletekey
Root: HKA; Subkey: "Software\Classes\Handwriter.Document\DefaultIcon"; ValueType: string; ValueName: ""; ValueData: "{app}\Handwriter.exe,0"
Root: HKA; Subkey: "Software\Classes\Handwriter.Document\shell\open\command"; ValueType: string; ValueName: ""; ValueData: """{app}\Handwriter.exe"" ""%1"""

Root: HKA; Subkey: "Software\Classes\.hfont"; ValueType: string; ValueName: ""; ValueData: "Handwriter.Font"; Flags: uninsdeletevalue
Root: HKA; Subkey: "Software\Classes\Handwriter.Font"; ValueType: string; ValueName: ""; ValueData: "Handwriter Font"; Flags: uninsdeletekey
Root: HKA; Subkey: "Software\Classes\Handwriter.Font\DefaultIcon"; ValueType: string; ValueName: ""; ValueData: "{app}\Handwriter.exe,0"
Root: HKA; Subkey: "Software\Classes\Handwriter.Font\shell\open\command"; ValueType: string; ValueName: ""; ValueData: """{app}\Handwriter.exe"" ""%1"""

Root: HKA; Subkey: "Software\Classes\.hwpap"; ValueType: string; ValueName: ""; ValueData: "Handwriter.Preset"; Flags: uninsdeletevalue
Root: HKA; Subkey: "Software\Classes\Handwriter.Preset"; ValueType: string; ValueName: ""; ValueData: "Handwriter Paper Preset"; Flags: uninsdeletekey
Root: HKA; Subkey: "Software\Classes\Handwriter.Preset\DefaultIcon"; ValueType: string; ValueName: ""; ValueData: "{app}\Handwriter.exe,0"
Root: HKA; Subkey: "Software\Classes\Handwriter.Preset\shell\open\command"; ValueType: string; ValueName: ""; ValueData: """{app}\Handwriter.exe"" ""%1"""

[Icons]
Name: "{group}\Handwriter"; Filename: "{app}\Handwriter.exe"
Name: "{autodesktop}\Handwriter"; Filename: "{app}\Handwriter.exe"; Tasks: desktopicon

[Tasks]
Name: "desktopicon"; Description: "{cm:CreateDesktopIcon}"; GroupDescription: "{cm:AdditionalIcons}"

[Run]
Filename: "{app}\Handwriter.exe"; Description: "{cm:LaunchProgram,Handwriter}"; Flags: nowait postinstall skipifsilent