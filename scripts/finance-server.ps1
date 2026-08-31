$ErrorActionPreference = "Stop"
$FinancePython = Join-Path $env:USERPROFILE ".venvs\Finance\Scripts\python.exe"
& $FinancePython -m finance_server.environment_cli server
exit $LASTEXITCODE
