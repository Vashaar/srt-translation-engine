[Setup]
AppId={{C9E4E4D8-1D16-4F58-8C87-0D55A8C7D7A1}
AppName=SRTranslate
AppVersion=1.0.0
AppPublisher=Vashaar
DefaultDirName={autopf}\SRTranslate
DefaultGroupName=SRTranslate
DisableProgramGroupPage=yes
OutputDir=.
OutputBaseFilename=SRTranslate_Setup
Compression=lzma
SolidCompression=yes
WizardStyle=modern
UninstallDisplayIcon={app}\SRTranslate Desktop.exe
ArchitecturesInstallIn64BitMode=x64compatible

[Languages]
Name: "english"; MessagesFile: "compiler:Default.isl"

[Tasks]
Name: "desktopicon"; Description: "Create a desktop shortcut"; GroupDescription: "Additional shortcuts:"

[Files]
Source: "dist\SRTranslate Desktop\*"; DestDir: "{app}"; Flags: ignoreversion recursesubdirs createallsubdirs

[Icons]
Name: "{group}\SRTranslate"; Filename: "{app}\SRTranslate Desktop.exe"
Name: "{group}\Uninstall SRTranslate"; Filename: "{uninstallexe}"
Name: "{autodesktop}\SRTranslate"; Filename: "{app}\SRTranslate Desktop.exe"; Tasks: desktopicon

[Run]
Filename: "{app}\SRTranslate Desktop.exe"; Description: "Launch SRTranslate"; Flags: nowait postinstall skipifsilent
