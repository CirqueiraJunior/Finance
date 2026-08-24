# Estrutura do projeto

```text
.
├── migrations/              # ambiente Alembic
├── src/app/
│   ├── core/                # configuração e logs
│   ├── database/            # SQLAlchemy
│   ├── models/              # modelos futuros
│   ├── repositories/        # acesso a dados futuro
│   ├── services/            # casos de uso futuros
│   ├── gui/
│   │   ├── controllers/     # coordenação da interface
│   │   └── pages/           # páginas placeholder
│   ├── widgets/             # barra superior e menu lateral
│   ├── resources/           # tema QSS
│   ├── reports/             # relatórios futuros
│   └── integrations/        # integrações futuras
├── tests/                   # testes automatizados
├── docs/                    # documentação técnica
├── .env.example             # variáveis de ambiente documentadas
├── alembic.ini
├── pyproject.toml
└── requirements.txt
```

