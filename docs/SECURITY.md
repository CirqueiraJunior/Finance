# Segurança do Finance

- Senhas: Argon2id; mínimo de 12 caracteres, maiúscula, minúscula, número e símbolo.
- Sessão: JWT curto e refresh aleatório armazenado somente como hash; tokens locais apenas em memória.
- Reset: resposta neutra, expiração, uso único e revogação das sessões anteriores.
- Usuário inativo não autentica. Respostas não expõem `password_hash`.

`SECRET_KEY`, credenciais PostgreSQL e SMTP nunca são versionados. A chave deve conter ao menos 32 caracteres aleatórios. Auditoria remove senhas e tokens dos detalhes.

Perfis: Administrador, Gestor, Operador Financeiro, Operador BOE e Consulta. A API decide toda autorização e responde 403 quando negada; ocultação visual não é controle de segurança.

Auditoria registra login/falha/logout, usuários, senha e operações financeiras com usuário, instante, ação, entidade, id e origem, sem segredos.

Produção exige HTTPS por proxy reverso e certificado confiável. Não usar CORS `*`, HTTP externo ou certificado permanente autoassinado.
