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
#define UpdaterRequiredVersion "1.0.0"
#define UpdaterUninstallKey "SOFTWARE\Microsoft\Windows\CurrentVersion\Uninstall\{A72CFE39-4BA1-46C1-A8A2-9244536D86BB}_is1"

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
Source: "..\ja-product.json"; DestDir: "{app}"; Flags: ignoreversion
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

function CompareVersionPart(
  A: Integer;
  B: Integer
): Integer;
begin
  if A < B then
    Result := -1
  else if A > B then
    Result := 1
  else
    Result := 0;
end;

function NextVersionPart(
  Version: String;
  var Position: Integer
): Integer;
var
  StartPos: Integer;
  PartText: String;
begin
  while
    (Position <= Length(Version)) and
    (Version[Position] = '.')
  do
    Position := Position + 1;

  StartPos := Position;

  while
    (Position <= Length(Version)) and
    (Version[Position] <> '.')
  do
    Position := Position + 1;

  PartText := Copy(
    Version,
    StartPos,
    Position - StartPos
  );

  Result := StrToIntDef(
    PartText,
    0
  );
end;

function CompareVersions(
  CurrentVersion: String;
  RequiredVersion: String
): Integer;
var
  I: Integer;
  CurrentPos: Integer;
  RequiredPos: Integer;
  CurrentValue: Integer;
  RequiredValue: Integer;
begin
  CurrentPos := 1;
  RequiredPos := 1;

  for I := 0 to 3 do
  begin
    CurrentValue := NextVersionPart(
      CurrentVersion,
      CurrentPos
    );

    RequiredValue := NextVersionPart(
      RequiredVersion,
      RequiredPos
    );

    Result := CompareVersionPart(
      CurrentValue,
      RequiredValue
    );

    if Result <> 0 then
      Exit;
  end;

  Result := 0;
end;

function UpdaterNeedsInstallation(): Boolean;
var
  InstalledVersion: String;
  UpdaterExe: String;
begin
  UpdaterExe := ExpandConstant(
    '{autopf}\J.A. Technology\J.A. Updater\J.A. Updater.exe'
  );

  if not FileExists(UpdaterExe) then
  begin
    Result := True;
    Exit;
  end;

  if not RegQueryStringValue(
    HKLM64,
    '{#UpdaterUninstallKey}',
    'DisplayVersion',
    InstalledVersion
  ) then
  begin
    Result := True;
    Exit;
  end;

  Result :=
    CompareVersions(
      InstalledVersion,
      '{#UpdaterRequiredVersion}'
    ) < 0;
end;

procedure InstallUpdaterIfRequired();
var
  ResultCode: Integer;
  InstallerPath: String;
begin
  if not UpdaterNeedsInstallation() then
    Exit;

  ExtractTemporaryFile(
    '{#UpdaterInstallerName}'
  );

  InstallerPath :=
    ExpandConstant(
      '{tmp}\{#UpdaterInstallerName}'
    );

  if not Exec(
    InstallerPath,
    '/VERYSILENT /SUPPRESSMSGBOXES /NORESTART /SP-',
    '',
    SW_HIDE,
    ewWaitUntilTerminated,
    ResultCode
  ) then
    RaiseException(
      'J.A. Updater bootstrap could not be started.'
    );

  if ResultCode <> 0 then
    RaiseException(Format(
      'J.A. Updater bootstrap returned exit code %d.', [ResultCode]));

  if UpdaterNeedsInstallation() then
    RaiseException(
      'J.A. Updater bootstrap did not install the required version.'
    );
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
  InstallUpdaterIfRequired();
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
