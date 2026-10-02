#ifndef AppVersion
  #define AppVersion "0.2.0"
#endif
[Setup]
AppId=SportsBug.Desktop
AppName=SportsBug
AppVersion={#AppVersion}
DefaultDirName={localappdata}\Programs\SportsBug
PrivilegesRequired=lowest
DefaultGroupName=SportsBug
DisableProgramGroupPage=yes
UsePreviousAppDir=yes
CloseApplications=yes
RestartApplications=no
OutputDir=installer-output
OutputBaseFilename=SportsBug-Setup
SetupIconFile=SportsBug.ico
UninstallDisplayIcon={app}\SportsBug.exe
Compression=lzma2
SolidCompression=yes
[Files]
Source: "dist\SportsBug\*"; DestDir: "{app}"; Flags: ignoreversion recursesubdirs createallsubdirs
[Icons]
Name: "{autoprograms}\SportsBug"; Filename: "{app}\SportsBug.exe"
Name: "{autodesktop}\SportsBug"; Filename: "{app}\SportsBug.exe"
[Run]
Filename: "{app}\SportsBug.exe"; Description: "Launch SportsBug"; Flags: nowait postinstall skipifsilent
