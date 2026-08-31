# Ambientes e inicialização do Finance

## Terminais oficiais

**Python Finance** é o terminal exclusivo da API/Uvicorn na porta 8000. Enquanto a API estiver ativa, não use esse terminal para testes, Git ou comandos administrativos.

**PowerShell** é o terminal comum para testes, diagnósticos, Git e administração.

Os comandos são instalados no ambiente virtual pelas entradas do `pyproject.toml`. Após atualizar o projeto, execute uma vez no PowerShell:

```powershell
& "$env:USERPROFILE\.venvs\Finance\Scripts\python.exe" -m pip install -e .
```

No terminal **Python Finance**, ative o ambiente oficial antes de usar os comandos curtos:

```powershell
& "$env:USERPROFILE\.venvs\Finance\Scripts\Activate.ps1"
```

Também existem wrappers equivalentes em `scripts\`, que funcionam sem ativação prévia do ambiente.

## Desenvolvimento diário

No terminal **Python Finance**:

```powershell
finance-dev
```

O comando usa exclusivamente o ambiente virtual oficial e cria um SQLite DEV isolado em:

```text
%LOCALAPPDATA%\J.A. Technology\Finance\dev\finance_dev.db
```

Ele não usa Supabase, aplica as migrations no banco DEV, protege a porta 8000 contra processos desconhecidos e inicia uma única API em `http://127.0.0.1:8000`.

## Configuração central inicial

Execute uma única vez no PowerShell:

```powershell
finance-server-config
```

Host, porta, banco e usuário são armazenados fora do repositório. A senha PostgreSQL e a `SECRET_KEY` são protegidas pelo DPAPI do Windows, vinculadas ao usuário atual. A URL PostgreSQL completa existe apenas em memória durante a inicialização.

O arquivo protegido fica em:

```text
%LOCALAPPDATA%\J.A. Technology\Finance\server_config.json
```

Não copie esse arquivo para o projeto ou para outro usuário Windows.

## Homologação central

No PowerShell, encerre a API anterior:

```powershell
finance-stop
```

Depois, no terminal **Python Finance**:

```powershell
finance-server
```

O comando recupera os segredos via DPAPI, valida o estado Alembic sem executar upgrade automático no PostgreSQL e inicia a API central.

## Encerramento

No PowerShell:

```powershell
finance-stop
```

O comando só encerra processos na porta 8000 quando a assinatura do processo e o `/health` confirmam que se trata da API Finance. Processos desconhecidos nunca são encerrados automaticamente.
