# Finance - Playbook de Empacotamento

## Ferramentas oficiais
- Python: %USERPROFILE%\.venvs\Finance\Scripts\python.exe
- PyInstaller: 6.22.3
- Inno Setup: 7.0.2
- ISCC: %LOCALAPPDATA%\Programs\Inno Setup 7\ISCC.exe
- Updater: %USERPROFILE%\J.A. Technology\Instaladores Homologados\J.A. Updater\JA_Updater_Setup_1.0.0.exe

## Arquivos de empacotamento
- packaging/Finance.spec
- packaging/FinanceServer.spec
- packaging/Finance.iss
- packaging/release.json
- ja-product.json

## Compilacao
Executar na raiz do repositorio Finance:

    python -m PyInstaller --noconfirm --clean packaging\Finance.spec
    python -m PyInstaller --noconfirm --clean packaging\FinanceServer.spec

Utilizar o Python da venv oficial, nao o Python global.

## Instalador
Compilar packaging/Finance.iss com ISCC.exe.
Informar obrigatoriamente: ProductVersion, BuildRoot, OutputRoot e UpdaterInstaller.
O UpdaterInstaller deve apontar para o instalador homologado do J.A. Updater.

## Organizacao
- Softwares/Finance: codigo-fonte, Git e configuracoes de build.
- Instaladores Homologados/Finance: somente versoes formalmente aprovadas.
- Artefatos em Homologacao/Finance: instaladores candidatos.
- build, dist e installer: artefatos temporarios ignorados pelo Git.

## Regras de seguranca
- Nunca sobrescrever instaladores homologados.
- Nunca publicar automaticamente.
- Validar SHA-256, abertura do aplicativo e funcionalidades alteradas.
- Preservar a integracao com o J.A. Updater.
- Nao alterar bancos, usuarios, migrations ou servicos durante o build.
- Nao interferir na producao da porta 8000.
- Registrar versao, testes e autorizacao antes de publicar.

## FIN-UI-007
- Instalador candidato: Finance_Setup_1.0.1.exe
- SHA-256: 9F97E84580911631FE64A21F9776F42C880A3A9FE403A9E1D1187E775D4A3E5D
- Local: Artefatos em Homologacao/Finance/FIN-UI-007
- Build e teste de abertura: aprovados.
- Publicacao: nao realizada.
- Instalacao final: pendente.

## Comando oficial - Inno Setup 7

Executar no PowerShell, na raiz do repositorio Finance:

    $repo = Join-Path $env:USERPROFILE "J.A. Technology\Softwares\Finance"
    $iscc = Join-Path $env:LOCALAPPDATA "Programs\Inno Setup 7\ISCC.exe"
    $updater = Join-Path $env:USERPROFILE "J.A. Technology\Instaladores Homologados\J.A. Updater\JA_Updater_Setup_1.0.0.exe"
    $buildRoot = Join-Path $repo "dist"
    $outputRoot = Join-Path $repo "installer\CANDIDATO"
    $versao = "VERSAO_AUTORIZADA"
    Set-Location -LiteralPath $repo
    & $iscc "/DProductVersion=$versao" "/DBuildRoot=$buildRoot" "/DOutputRoot=$outputRoot" "/DUpdaterInstaller=$updater" "packaging\Finance.iss"

Pre-condicoes:
- Compilar primeiro Finance.spec e FinanceServer.spec.
- Substituir VERSAO_AUTORIZADA pela versao candidata aprovada.
- Confirmar que o instalador de destino ainda nao existe.
- Nao executar o instalador durante o build.
- Nao publicar ou atualizar a versao instalada automaticamente.

## Validacao de artefatos
- Confirmar dist/Finance/Finance.exe.
- Confirmar dist/FinanceServer.exe e dist/FinanceServer.pkg.
- Confirmar que o instalador inclui o bootstrap oficial do J.A. Updater.
- Calcular e registrar SHA-256 do instalador.
- Testar abertura do executavel compilado e tela de login.
- Testar as funcionalidades alteradas com ambiente autorizado.
- Realizar instalacao final somente em ambiente seguro e aprovado.
- Copiar candidatos para Artefatos em Homologacao.
- Mover para Instaladores Homologados somente apos aprovacao formal.
- Limpar build, dist e installer somente apos verificar a copia externa.

## Historico
- 2026-10-26: FIN-UI-007, instalador candidato 1.0.1 gerado e validado parcialmente.
- Instalacao final e publicacao permanecem pendentes.
