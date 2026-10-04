#define ProductName "Finance"
#define ProductVersion "1.0.0"
#define Publisher "J.A. Technology"
#define ServiceName "JATechnologyFinanceServer"
#ifndef BuildRoot
  #define BuildRoot "..\dist"
#endif
#ifndef OutputRoot
  #define OutputRoot "..\installer"
#endif
#ifndef UpdaterInstaller
  #error UpdaterInstaller define is required for official Finance builds
#endif
#define UpdaterInstallerName ExtractFileName(UpdaterInstaller)

[Setup]
AppId={{D4265C90-A4A7-4F51-BE50-DDAA3984E5E9}
AppName={#ProductName}
AppVersion={#ProductVersion}
AppPublisher={#Publisher}
DefaultDirName={autopf}\J.A. Technology\Finance
DefaultGroupName=J.A. Technology\Finance
DisableProgramGroupPage=yes
PrivilegesRequired=admin
ArchitecturesAllowed=x64compatible
ArchitecturesInstallIn64BitMode=x64compatible
OutputDir={#OutputRoot}
OutputBaseFilename=Finance_Setup_1.0.0
SetupIconFile=..\assets\branding\finance_desktop_v100.ico
UninstallDisplayIcon={app}\Finance.exe
Compression=lzma2/ultra64
SolidCompression=yes
WizardStyle=modern
CloseApplications=yes
RestartApplications=no
ChangesEnvironment=no
UsedUserAreasWarning=no

[Files]
Source: "{#BuildRoot}\Finance\*"; DestDir: "{app}"; Flags: ignoreversion recursesubdirs createallsubdirs
Source: "{#BuildRoot}\FinanceServer.exe"; DestDir: "{app}"; Flags: ignoreversion
Source: "{#UpdaterInstaller}"; DestName: "{#UpdaterInstallerName}"; Flags: dontcopy

[InstallDelete]
Type: files; Name: "{userdesktop}\Finance.lnk"
Type: files; Name: "{commondesktop}\Finance.lnk"
Type: files; Name: "{userprograms}\Finance.lnk"
Type: files; Name: "{commonprograms}\Finance.lnk"

[Icons]
Name: "{group}\Finance"; Filename: "{app}\Finance.exe"; WorkingDir: "{app}"; IconFilename: "{app}\_internal\assets\branding\finance_desktop_v100.ico"
Name: "{commondesktop}\Finance"; Filename: "{app}\Finance.exe"; WorkingDir: "{app}"; IconFilename: "{app}\_internal\assets\branding\finance_desktop_v100.ico"

[Code]
const
  ServiceRegistryKey = 'SYSTEM\CurrentControlSet\Services\{#ServiceName}';

function ServiceExists(): Boolean;
begin
  Result := RegKeyExists(HKLM, ServiceRegistryKey);
end;

function UpdaterInstalled(): Boolean;
begin
  Result := FileExists(ExpandConstant(
    '{autopf}\J.A. Technology\J.A. Updater\J.A. Updater.exe'));
end;

procedure EnsureUpdaterInstalled();
var
  ResultCode: Integer;
  InstallerPath: String;
begin
  if UpdaterInstalled() then
    exit;

  ExtractTemporaryFile('{#UpdaterInstallerName}');
  InstallerPath := ExpandConstant('{tmp}\{#UpdaterInstallerName}');

  if not Exec(InstallerPath,
    '/VERYSILENT /SUPPRESSMSGBOXES /NORESTART /SP-', '', SW_HIDE,
    ewWaitUntilTerminated, ResultCode) then
    RaiseException('J.A. Updater bootstrap could not be started.');

  if ResultCode <> 0 then
    RaiseException(Format(
      'J.A. Updater bootstrap returned exit code %d.', [ResultCode]));

  if not UpdaterInstalled() then
    RaiseException(
      'J.A. Updater bootstrap completed without the expected executable.');
end;

procedure RunServiceCommand(const Parameters: String; const Required: Boolean);
var
  ResultCode: Integer;
begin
  if not Exec(ExpandConstant('{app}\FinanceServer.exe'), Parameters, '',
    SW_HIDE, ewWaitUntilTerminated, ResultCode) then
  begin
    if Required then
      RaiseException('Não foi possível executar a configuração do serviço Finance.');
    exit;
  end;
  if Required and (ResultCode <> 0) then
    RaiseException(Format('O serviço Finance retornou o código %d.', [ResultCode]));
end;

procedure RemovePreviousService();
var
  ResultCode: Integer;
  Attempts: Integer;
begin
  if not ServiceExists() then
    exit;

  Exec(ExpandConstant('{sys}\sc.exe'), 'stop {#ServiceName}', '', SW_HIDE,
    ewWaitUntilTerminated, ResultCode);
  Sleep(1000);
  Exec(ExpandConstant('{sys}\sc.exe'), 'delete {#ServiceName}', '', SW_HIDE,
    ewWaitUntilTerminated, ResultCode);

  for Attempts := 1 to 20 do
  begin
    if not ServiceExists() then
      exit;
    Sleep(250);
  end;

  RaiseException('A instalação anterior do serviço Finance não pôde ser removida.');
end;

function HealthIsReady(): Boolean;
var
  Http: Variant;
begin
  Result := False;
  try
    Http := CreateOleObject('WinHttp.WinHttpRequest.5.1');
    Http.SetTimeouts(1000, 1000, 1000, 2000);
    Http.Open('GET', 'http://127.0.0.1:8000/health', False);
    Http.Send('');
    Result := Http.Status = 200;
  except
    Result := False;
  end;
end;

procedure WaitForHealth();
var
  Attempts: Integer;
begin
  for Attempts := 1 to 20 do
  begin
    if HealthIsReady() then
      exit;
    Sleep(1000);
  end;
  RaiseException(
    'O serviço Finance foi iniciado, mas a API local não respondeu ao diagnóstico.');
end;

function PrepareToInstall(var NeedsRestart: Boolean): String;
begin
  Result := '';
  EnsureUpdaterInstalled();
  RemovePreviousService();
end;

procedure CurStepChanged(CurStep: TSetupStep);
var
  ResultCode: Integer;
  ConfigPath: String;
begin
  if CurStep <> ssPostInstall then
    exit;

  ConfigPath := ExpandConstant(
    '{commonappdata}\J.A. Technology\Finance\server_config.json');
  if not FileExists(ConfigPath) then
  begin
    if not Exec(ExpandConstant('{app}\Finance.exe'), '--configure-service', '',
      SW_SHOWNORMAL, ewWaitUntilTerminated, ResultCode) or (ResultCode <> 0) then
      RaiseException(
        'A configuração segura do servidor foi cancelada ou não pôde ser salva.');
  end;

  RunServiceCommand('--startup auto install', True);
  RunServiceCommand('--wait 30 start', True);
  WaitForHealth();
end;

procedure CurUninstallStepChanged(CurUninstallStep: TUninstallStep);
begin
  if CurUninstallStep = usUninstall then
  begin
    if FileExists(ExpandConstant('{app}\FinanceServer.exe')) then
    begin
      RunServiceCommand('--wait 30 stop', False);
      RunServiceCommand('remove', False);
    end;
  end;
end;
