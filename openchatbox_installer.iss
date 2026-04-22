[Setup]
AppName=OpenChatbox
AppVersion=1.0
AppId={{B9F4C6A1-7D2E-4A8B-9C3F-1E5D7A2B4C6F}
DefaultDirName={autopf}\OpenChatbox
DefaultGroupName=OpenChatbox
OutputDir=dist
OutputBaseFilename=OpenChatboxSetup
Compression=lzma
SolidCompression=yes
SetupIconFile=OpenChatbox.ico
UninstallDisplayIcon={app}\OpenChatbox.exe
PrivilegesRequired=lowest
PrivilegesRequiredOverridesAllowed=dialog
CloseApplications=yes
RestartApplications=no

[Files]
Source: "dist\OpenChatbox\*"; DestDir: "{app}"; Flags: ignoreversion recursesubdirs createallsubdirs

[Icons]
Name: "{group}\OpenChatbox"; Filename: "{app}\OpenChatbox.exe"
Name: "{autodesktop}\OpenChatbox"; Filename: "{app}\OpenChatbox.exe"

[Run]
Filename: "{app}\OpenChatbox.exe"; Description: "Launch OpenChatbox"; Flags: nowait postinstall skipifsilent
