from datetime import datetime, timedelta, timezone

from fastapi import Body, Depends, FastAPI, File, Form, HTTPException, Query, Request, UploadFile
from fastapi.encoders import jsonable_encoder
from fastapi.responses import Response
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
import jwt
from sqlalchemy import create_engine, func, or_, select
from sqlalchemy.orm import Session, sessionmaker
from sqlalchemy.pool import NullPool
from pathlib import Path
from tempfile import TemporaryDirectory
from zipfile import ZIP_DEFLATED, ZipFile

from app.database.base import Base
from finance_server.config import ServerSettings, get_server_settings
from finance_server.email_service import EmailService, FakeEmailService, SMTPEmailService
from finance_server.models import AuditLog, PasswordResetToken, RefreshSession, User, UserRole
from finance_server.rbac import has_permission
from finance_server.schemas import (
    AuditResponse, ChangePasswordRequest, ForgotPasswordRequest, LoginRequest,
    RefreshRequest, ResetPasswordRequest, TokenPair, UserCreate, UserResponse, UserUpdate,
    CashflowCreate, CashflowUpdate, CashflowResponse,
    BudgetCreate, BudgetUpdate, BudgetResponse,
    EntityCreate, EntityUpdate, EntityResponse,
    CatalogCreate, CatalogUpdate, CatalogResponse,
)
from app.models.cashflow_entry import CashflowEntry, CashflowOrigin, CashflowType, CashflowCategory
from app.models.entity import Entity
from app.repositories.association_repository import AssociationRepository
from app.repositories.boe_repository import BOERepository
from app.repositories.budget_repository import BudgetRepository
from app.repositories.cashflow_repository import CashflowRepository
from app.repositories.csv_export_repository import CSVExportRepository
from app.repositories.entity_repository import EntityRepository
from app.repositories.investment_repository import InvestmentRepository
from app.repositories.target_repository import TargetRepository
from app.importers.boe_importer import BOEImporter
from app.services.boe_service import BOEService
from app.services.budget_service import BudgetService
from app.services.cashflow_service import CashflowService
from app.services.dashboard_service import DashboardService
from app.services.financial_flow_service import FinancialFlowService
from app.services.investment_service import InvestmentService
from app.services.ranking_service import RankingService
from app.services.report_service import ReportService
from app.services.site_csv_service import SiteCSVService
from app.services.target_service import TargetService
from app.core.exceptions import BOEValidationError, CSVExportValidationError
from app.repositories.entity_repository import EntityRepository
from app.repositories.cashflow_catalog_repository import CashflowCatalogRepository
from app.services.entity_service import EntityService
from app.services.cashflow_catalog_service import CashflowCatalogService
from finance_server.security import (
    create_access_token, decode_access_token, hash_password, random_token,
    token_hash, verify_password,
)
from finance_server.version import __version__


def utcnow() -> datetime:
    return datetime.now(timezone.utc)


def aware(value: datetime) -> datetime:
    return value if value.tzinfo else value.replace(tzinfo=timezone.utc)


def database_engine_options(database_url: str) -> dict:
    options = {"pool_pre_ping": True}
    if database_url.startswith(("postgresql://", "postgresql+")):
        options.update(
            poolclass=NullPool,
            connect_args={"connect_timeout": 10},
        )
    return options


def create_app(
    settings: ServerSettings | None = None,
    *,
    email_service: EmailService | None = None,
    create_schema: bool = False,
) -> FastAPI:
    settings = settings or get_server_settings()
    engine = create_engine(settings.database_url, **database_engine_options(settings.database_url))
    factory = sessionmaker(engine, expire_on_commit=False)
    if create_schema:
        Base.metadata.create_all(engine)
    app = FastAPI(title="Finance API", version=__version__)
    app.state.engine = engine
    app.state.session_factory = factory
    app.state.email_service = email_service or (
        SMTPEmailService(settings.smtp_host, settings.smtp_port, settings.smtp_from,
                         settings.smtp_user, settings.smtp_password)
        if settings.smtp_host and settings.smtp_from else FakeEmailService()
    )
    bearer = HTTPBearer(auto_error=False)

    def get_db():
        with factory() as session:
            yield session

    def audit(db: Session, action: str, user: User | None = None, *,
              entity_type: str | None = None, entity_id=None,
              details: dict | None = None, origin: str | None = None) -> None:
        forbidden = {"password", "password_hash", "token", "access_token", "refresh_token"}
        safe = {key: value for key, value in (details or {}).items()
                if key.casefold() not in forbidden}
        db.add(AuditLog(user_id=user.id if user else None, action=action,
                        entity_type=entity_type, entity_id=str(entity_id) if entity_id else None,
                        details=safe or None, origin=origin))

    def current_user(
        credentials: HTTPAuthorizationCredentials | None = Depends(bearer),
        db: Session = Depends(get_db),
    ) -> User:
        unauthorized = HTTPException(status_code=401, detail="Sessão inválida ou expirada.")
        if credentials is None:
            raise unauthorized
        try:
            payload = decode_access_token(credentials.credentials, settings.secret_key)
            user = db.get(User, int(payload["sub"]))
        except (jwt.InvalidTokenError, KeyError, TypeError, ValueError):
            raise unauthorized from None
        if user is None or not user.ativo:
            raise unauthorized
        return user

    def require(permission: str):
        def dependency(user: User = Depends(current_user)) -> User:
            if not has_permission(user, permission):
                raise HTTPException(status_code=403, detail="Permissão insuficiente.")
            return user
        return dependency

    def issue_pair(db: Session, user: User) -> TokenPair:
        access = create_access_token(user.id, user.perfil, settings.secret_key,
                                     settings.access_token_minutes)
        refresh = random_token()
        db.add(RefreshSession(
            user_id=user.id, token_hash=token_hash(refresh),
            expires_at=utcnow() + timedelta(days=settings.refresh_token_days),
        ))
        return TokenPair(access_token=access, refresh_token=refresh,
                         expires_in=settings.access_token_minutes * 60)

    def domain_services(db: Session):
        cashflow = CashflowService(CashflowRepository(db))
        investments = InvestmentService(InvestmentRepository(db))
        boe = BOEService(BOERepository(db), EntityRepository(db), BOEImporter(), cashflow)
        budget = BudgetService(BudgetRepository(db), CashflowRepository(db))
        targets = TargetService(TargetRepository(db), EntityRepository(db))
        ranking = RankingService(TargetRepository(db), AssociationRepository(db))
        flow = FinancialFlowService(cashflow, investments)
        return cashflow, investments, boe, budget, targets, ranking, flow

    @app.get("/health")
    def health():
        return {"status": "ok", "version": __version__}

    @app.post("/api/v1/auth/login", response_model=TokenPair)
    def login(payload: LoginRequest, request: Request, db: Session = Depends(get_db)):
        identifier = payload.identifier.strip().casefold()
        user = db.scalar(select(User).where(or_(func.lower(User.username) == identifier,
                                                func.lower(User.email) == identifier)))
        if user is None or not user.ativo or not verify_password(payload.password, user.password_hash):
            audit(db, "LOGIN_FAILED", user, origin=request.client.host if request.client else None)
            db.commit()
            raise HTTPException(status_code=401, detail="Usuário ou senha inválidos.")
        user.ultimo_login = utcnow()
        pair = issue_pair(db, user)
        audit(db, "LOGIN", user, origin=request.client.host if request.client else None)
        db.commit()
        return pair

    @app.post("/api/v1/auth/refresh", response_model=TokenPair)
    def refresh(payload: RefreshRequest, db: Session = Depends(get_db)):
        session = db.scalar(select(RefreshSession).where(
            RefreshSession.token_hash == token_hash(payload.refresh_token)))
        if session is None or session.revoked_at is not None or aware(session.expires_at) <= utcnow():
            raise HTTPException(status_code=401, detail="Sessão inválida ou expirada.")
        user = db.get(User, session.user_id)
        if user is None or not user.ativo:
            raise HTTPException(status_code=401, detail="Sessão inválida ou expirada.")
        session.revoked_at = utcnow()
        pair = issue_pair(db, user)
        db.commit()
        return pair

    @app.post("/api/v1/auth/logout", status_code=204)
    def logout(payload: RefreshRequest, user: User = Depends(current_user),
               db: Session = Depends(get_db)):
        session = db.scalar(select(RefreshSession).where(
            RefreshSession.token_hash == token_hash(payload.refresh_token),
            RefreshSession.user_id == user.id))
        if session and session.revoked_at is None:
            session.revoked_at = utcnow()
        audit(db, "LOGOUT", user)
        db.commit()

    @app.post("/api/v1/auth/forgot-password")
    def forgot(payload: ForgotPasswordRequest, db: Session = Depends(get_db)):
        user = db.scalar(select(User).where(func.lower(User.email) == payload.email.casefold()))
        if user and user.ativo:
            raw = random_token()
            db.add(PasswordResetToken(user_id=user.id, token_hash=token_hash(raw),
                                      expires_at=utcnow() + timedelta(minutes=settings.reset_token_minutes)))
            app.state.email_service.send_password_reset(user.email, raw)
            audit(db, "PASSWORD_RESET_REQUESTED", user)
            db.commit()
        return {"message": "Se o endereço estiver cadastrado, as instruções serão enviadas."}

    @app.post("/api/v1/auth/reset-password", status_code=204)
    def reset(payload: ResetPasswordRequest, db: Session = Depends(get_db)):
        reset_token = db.scalar(select(PasswordResetToken).where(
            PasswordResetToken.token_hash == token_hash(payload.token)))
        if (reset_token is None or reset_token.used_at is not None
                or aware(reset_token.expires_at) <= utcnow()):
            raise HTTPException(status_code=400, detail="Token inválido ou expirado.")
        user = db.get(User, reset_token.user_id)
        try:
            user.password_hash = hash_password(payload.new_password)
        except ValueError as error:
            raise HTTPException(status_code=422, detail=str(error)) from None
        reset_token.used_at = utcnow()
        for item in db.scalars(select(RefreshSession).where(
                RefreshSession.user_id == user.id, RefreshSession.revoked_at.is_(None))):
            item.revoked_at = utcnow()
        audit(db, "PASSWORD_RESET", user)
        db.commit()

    @app.post("/api/v1/auth/change-password", status_code=204)
    def change_password(payload: ChangePasswordRequest, user: User = Depends(current_user),
                        db: Session = Depends(get_db)):
        if not verify_password(payload.current_password, user.password_hash):
            raise HTTPException(status_code=400, detail="Senha atual inválida.")
        try:
            user.password_hash = hash_password(payload.new_password)
        except ValueError as error:
            raise HTTPException(status_code=422, detail=str(error)) from None
        audit(db, "PASSWORD_CHANGED", user)
        db.commit()

    @app.get("/api/v1/auth/me", response_model=UserResponse)
    def me(user: User = Depends(current_user)):
        return user

    @app.get("/api/v1/users", response_model=list[UserResponse])
    def list_users(user: User = Depends(require("users:manage")), db: Session = Depends(get_db)):
        return list(db.scalars(select(User).order_by(User.nome)))

    @app.post("/api/v1/users", response_model=UserResponse, status_code=201)
    def create_user(payload: UserCreate, administrator: User = Depends(require("users:manage")),
                    db: Session = Depends(get_db)):
        try:
            role = UserRole(payload.perfil)
            password_hash = hash_password(payload.password)
        except ValueError as error:
            raise HTTPException(status_code=422, detail=str(error)) from None
        if db.scalar(select(User.id).where(or_(func.lower(User.email) == payload.email.casefold(),
                                              func.lower(User.username) == payload.username.casefold()))):
            raise HTTPException(status_code=409, detail="Email ou username já cadastrado.")
        target = User(nome=payload.nome.strip(), email=payload.email.casefold(),
                      username=payload.username.casefold(), password_hash=password_hash,
                      perfil=role.value, ativo=True)
        db.add(target)
        db.flush()
        audit(db, "USER_CREATED", administrator, entity_type="User", entity_id=target.id,
              details={"perfil": target.perfil})
        db.commit()
        return target

    @app.patch("/api/v1/users/{user_id}", response_model=UserResponse)
    def update_user(user_id: int, payload: UserUpdate,
                    administrator: User = Depends(require("users:manage")),
                    db: Session = Depends(get_db)):
        target = db.get(User, user_id)
        if target is None:
            raise HTTPException(status_code=404, detail="Usuário não encontrado.")
        changes = payload.model_dump(exclude_unset=True)
        if "perfil" in changes:
            changes["perfil"] = UserRole(changes["perfil"]).value
        for key, value in changes.items():
            setattr(target, key, value)
        audit(db, "USER_UPDATED", administrator, entity_type="User", entity_id=target.id,
              details={key: value for key, value in changes.items() if key != "password"})
        db.commit()
        return target

    @app.get("/api/v1/audit", response_model=list[AuditResponse])
    def audit_list(action: str | None = Query(None), user_id: int | None = Query(None),
                   user: User = Depends(require("audit:read")), db: Session = Depends(get_db)):
        statement = select(AuditLog).order_by(AuditLog.timestamp.desc()).limit(500)
        if action:
            statement = statement.where(AuditLog.action == action)
        if user_id:
            statement = statement.where(AuditLog.user_id == user_id)
        return list(db.scalars(statement))

    @app.get("/api/v1/entities", response_model=list[EntityResponse])
    def entities(
        user: User = Depends(require("dashboard:read")),
        db: Session = Depends(get_db),
    ):
        return EntityRepository(db).list_all()

    @app.post("/api/v1/entities", response_model=EntityResponse, status_code=201)
    def create_entity(
        payload: EntityCreate,
        user: User = Depends(require("entities:manage")),
        db: Session = Depends(get_db),
    ):
        service = EntityService(EntityRepository(db))
        try:
            entity = service.create_entity(**payload.model_dump())
        except (ValueError, Exception) as error:
            db.rollback()
            raise HTTPException(status_code=422, detail=str(error)) from None
        audit(
            db,
            "ENTITY_CREATED",
            user,
            entity_type="Entity",
            entity_id=entity.id,
            details={"codigo_entidade": entity.codigo_entidade},
        )
        db.commit()
        db.refresh(entity)
        return EntityRepository(db).get_by_id(entity.id)

    @app.patch("/api/v1/entities/{entity_id}", response_model=EntityResponse)
    def update_entity(
        entity_id: int,
        payload: EntityUpdate,
        user: User = Depends(require("entities:manage")),
        db: Session = Depends(get_db),
    ):
        service = EntityService(EntityRepository(db))
        try:
            entity = service.update_entity(entity_id, **payload.model_dump())
        except ValueError as error:
            db.rollback()
            message = str(error)
            code = 404 if "não encontrada" in message.casefold() else 422
            raise HTTPException(status_code=code, detail=message) from None
        audit(
            db,
            "ENTITY_UPDATED",
            user,
            entity_type="Entity",
            entity_id=entity.id,
        )
        db.commit()
        return EntityRepository(db).get_by_id(entity.id)

    @app.get("/api/v1/entities/{entity_id}/aliases")
    def entity_aliases(
        entity_id: int,
        user: User = Depends(require("dashboard:read")),
        db: Session = Depends(get_db),
    ):
        entity = EntityRepository(db).get_by_id(entity_id)
        if entity is None:
            raise HTTPException(status_code=404, detail="Entidade não encontrada.")
        return [
            {"id": item.id, "alias": item.alias, "origem": item.origem}
            for item in entity.aliases
        ]

    @app.get("/api/v1/catalog", response_model=list[CatalogResponse])
    def catalog(
        user: User = Depends(require("cashflow:read")),
        db: Session = Depends(get_db),
    ):
        return CashflowCatalogRepository(db).list_all()

    @app.post("/api/v1/catalog", response_model=CatalogResponse, status_code=201)
    def create_catalog(
        payload: CatalogCreate,
        user: User = Depends(require("catalog:manage")),
        db: Session = Depends(get_db),
    ):
        service = CashflowCatalogService(CashflowCatalogRepository(db))
        try:
            entry = service.create_entry(**payload.model_dump())
        except ValueError as error:
            db.rollback()
            raise HTTPException(status_code=422, detail=str(error)) from None
        audit(
            db,
            "CATALOG_CREATED",
            user,
            entity_type="CashflowCatalogEntry",
            entity_id=entry.id,
        )
        db.commit()
        return entry

    @app.patch("/api/v1/catalog/{entry_id}", response_model=CatalogResponse)
    def update_catalog(
        entry_id: int,
        payload: CatalogUpdate,
        user: User = Depends(require("catalog:manage")),
        db: Session = Depends(get_db),
    ):
        service = CashflowCatalogService(CashflowCatalogRepository(db))
        try:
            entry = service.update_entry(entry_id, **payload.model_dump())
        except ValueError as error:
            db.rollback()
            message = str(error)
            code = 404 if "não encontrado" in message.casefold() else 422
            raise HTTPException(status_code=code, detail=message) from None
        audit(
            db,
            "CATALOG_UPDATED",
            user,
            entity_type="CashflowCatalogEntry",
            entity_id=entry.id,
        )
        db.commit()
        return entry

    @app.get("/api/v1/cashflow", response_model=list[CashflowResponse])
    def cashflow(user: User = Depends(require("cashflow:read")), db: Session = Depends(get_db)):
        return list(db.scalars(select(CashflowEntry).order_by(CashflowEntry.id)))

    @app.post("/api/v1/cashflow", response_model=CashflowResponse, status_code=201)
    def create_cashflow(payload: CashflowCreate,
                        user: User = Depends(require("cashflow:write")),
                        db: Session = Depends(get_db)):
        if payload.tipo == CashflowType.REVENUE.value:
            valid_category = payload.categoria == CashflowCategory.INDIRECT_REVENUE.value
        else:
            valid_category = payload.tipo == CashflowType.EXPENSE.value and payload.categoria not in {
                CashflowCategory.DIRECT_REVENUE.value, CashflowCategory.INDIRECT_REVENUE.value}
        if not valid_category:
            raise HTTPException(status_code=422, detail="Tipo e categoria incompatíveis.")
        entry = CashflowEntry(**payload.model_dump(), origem=CashflowOrigin.MANUAL.value,
                              created_by_user_id=user.id,
                              updated_by_user_id=user.id, version=1)
        db.add(entry)
        db.flush()
        audit(db, "CASHFLOW_CREATED", user, entity_type="CashflowEntry", entity_id=entry.id)
        db.commit()
        return entry

    @app.patch("/api/v1/cashflow/{entry_id}", response_model=CashflowResponse)
    def update_cashflow(entry_id: int, payload: CashflowUpdate,
                        user: User = Depends(require("cashflow:write")),
                        db: Session = Depends(get_db)):
        entry = db.get(CashflowEntry, entry_id)
        if entry is None:
            raise HTTPException(status_code=404, detail="Lançamento não encontrado.")
        if entry.version != payload.expected_version:
            raise HTTPException(status_code=409, detail="O lançamento foi alterado por outro usuário. Atualize a tela.")
        changes = payload.model_dump(exclude={"expected_version"}, exclude_unset=True)
        for key, value in changes.items():
            setattr(entry, key, value)
        entry.updated_by_user_id = user.id
        entry.version += 1
        audit(db, "CASHFLOW_UPDATED", user, entity_type="CashflowEntry", entity_id=entry.id,
              details={"version": entry.version})
        db.commit()
        return entry

    @app.get("/api/v1/financial-flow")
    def financial_flow(year: int, month: int, user: User = Depends(require("cashflow:read")),
                       db: Session = Depends(get_db)):
        *_, flow = domain_services(db)
        return jsonable_encoder({"items": flow.list_by_period(year, month),
                                 "summary": flow.get_summary(year, month)})

    @app.post("/api/v1/investments", status_code=201)
    def create_investment(payload: dict = Body(...),
                          user: User = Depends(require("cashflow:write")), db: Session = Depends(get_db)):
        _, investments, *_ = domain_services(db)
        kind = payload.pop("movement_type", "")
        method = investments.create_application if kind == "APLICACAO" else investments.create_redemption
        item = method(**payload)
        audit(db, "INVESTMENT_CREATED", user, entity_type="InvestmentMovement", entity_id=item.id)
        db.commit()
        return jsonable_encoder(item)

    @app.post("/api/v1/boe/validate")
    async def validate_boe(file: UploadFile = File(...), user: User = Depends(require("boe:write")),
                           db: Session = Depends(get_db)):
        with TemporaryDirectory(prefix="finance_boe_") as directory:
            path = Path(directory) / (Path(file.filename or "boe.xlsx").name)
            path.write_bytes(await file.read())
            result = domain_services(db)[2].validate_file(path)
            return jsonable_encoder(result)

    @app.post("/api/v1/boe/import", status_code=201)
    async def import_boe(file: UploadFile = File(...), user: User = Depends(require("boe:write")),
                         db: Session = Depends(get_db)):
        with TemporaryDirectory(prefix="finance_boe_") as directory:
            path = Path(directory) / (Path(file.filename or "boe.xlsx").name)
            path.write_bytes(await file.read())
            try:
                item = domain_services(db)[2].import_file(path)
            except BOEValidationError as error:
                raise HTTPException(status_code=422, detail=jsonable_encoder(error.result)) from None
            audit(db, "BOE_IMPORTED", user, entity_type="BOEImport", entity_id=item.id)
            db.commit()
            return jsonable_encoder(item)

    @app.get("/api/v1/boe")
    def boe_history(user: User = Depends(require("boe:read")), db: Session = Depends(get_db)):
        return jsonable_encoder(domain_services(db)[2].list_imports())

    @app.get("/api/v1/boe/{import_id}")
    def boe_details(import_id: int, user: User = Depends(require("boe:read")),
                    db: Session = Depends(get_db)):
        value = domain_services(db)[2].get_import_details(import_id)
        if value is None:
            raise HTTPException(status_code=404, detail="Importação BOE não encontrada.")
        header = value.boe_import
        return jsonable_encoder({
            "boe_import": {
                "id": header.id, "periodo_ano": header.periodo_ano,
                "periodo_mes": header.periodo_mes, "nome_arquivo": header.nome_arquivo,
                "hash_arquivo": header.hash_arquivo, "data_importacao": header.data_importacao,
                "quantidade_entidades": header.quantidade_entidades,
                "quantidade_inconsistencias": header.quantidade_inconsistencias,
                "valor_total": header.valor_total, "status": header.status,
            },
            "entities": value.entities,
            "total_entities": value.total_entities,
            "total_queries": value.total_queries,
            "total_value": value.total_value,
            "inconsistencies": [
                {"id": item.id, "linha": item.linha, "codigo": item.codigo,
                 "mensagem": item.mensagem, "severidade": item.severidade}
                for item in value.inconsistencies
            ],
        })

    @app.get("/api/v1/budgets")
    def budgets(year: int, month: int | None = None,
                user: User = Depends(require("budget:read")), db: Session = Depends(get_db)):
        service = domain_services(db)[3]
        items = service.list_by_year(year) if month is None else service.list_by_period(year, month)
        return jsonable_encoder({"items": items, "comparison": service.get_budget_vs_actual(year, month)})

    @app.post("/api/v1/budgets", response_model=BudgetResponse, status_code=201)
    def create_budget(payload: BudgetCreate, user: User = Depends(require("budget:write")),
                      db: Session = Depends(get_db)):
        item = domain_services(db)[3].create_budget(
            year=payload.year,
            month=payload.month,
            descricao=payload.description,
            entry_type=payload.entry_type,
            category=payload.category,
            budgeted_value=payload.budgeted_value,
            notes=payload.notes,
        )
        audit(db, "BUDGET_CREATED", user, entity_type="BudgetEntry", entity_id=item.id)
        db.commit()
        return jsonable_encoder(item)

    @app.get("/api/v1/budgets/{budget_id}", response_model=BudgetResponse)
    def budget(budget_id: int, user: User = Depends(require("budget:read")),
               db: Session = Depends(get_db)):
        item = domain_services(db)[3].get_budget(budget_id)
        if item is None:
            raise HTTPException(status_code=404, detail="Orçamento não encontrado.")
        return jsonable_encoder(item)

    @app.patch("/api/v1/budgets/{budget_id}", response_model=BudgetResponse)
    def update_budget(budget_id: int, payload: BudgetUpdate,
                      user: User = Depends(require("budget:write")), db: Session = Depends(get_db)):
        changes = payload.model_dump(exclude_unset=True)
        item = domain_services(db)[3].update_budget(
            budget_id,
            descricao=changes.get("description"),
            budgeted_value=payload.budgeted_value,
            notes=changes.get("notes"),
        )
        audit(db, "BUDGET_UPDATED", user, entity_type="BudgetEntry", entity_id=item.id)
        db.commit()
        return jsonable_encoder(item)

    @app.get("/api/v1/targets")
    def targets(year: int, month: int, indicator: str, entity_id: int | None = None,
                user: User = Depends(require("targets:read")), db: Session = Depends(get_db)):
        service = domain_services(db)[4]
        return jsonable_encoder({"entities": service.list_entities(),
                                 "comparison": service.get_target_vs_actual(year, month, indicator, entity_id)})

    @app.get("/api/v1/targets/{target_id}")
    def target(target_id: int, user: User = Depends(require("targets:read")), db: Session = Depends(get_db)):
        item = domain_services(db)[4].get_target(target_id)
        if item is None:
            raise HTTPException(status_code=404, detail="Meta não encontrada.")
        return jsonable_encoder(item)

    @app.post("/api/v1/targets", status_code=201)
    def create_target(payload: dict = Body(...), user: User = Depends(require("targets:write")),
                      db: Session = Depends(get_db)):
        item = domain_services(db)[4].create_target(**payload)
        audit(db, "TARGET_CREATED", user, entity_type="TargetEntry", entity_id=item.id)
        db.commit()
        return jsonable_encoder(item)

    @app.patch("/api/v1/targets/{target_id}")
    def update_target(target_id: int, payload: dict = Body(...),
                      user: User = Depends(require("targets:write")), db: Session = Depends(get_db)):
        item = domain_services(db)[4].update_target(target_id, **payload)
        audit(db, "TARGET_UPDATED", user, entity_type="TargetEntry", entity_id=item.id)
        db.commit()
        return jsonable_encoder(item)

    @app.get("/api/v1/ranking")
    def ranking(year: int, quarter: int, user: User = Depends(require("ranking:read")),
                db: Session = Depends(get_db)):
        service = domain_services(db)[5]
        return jsonable_encoder({"quarterly": service.quarterly(year, quarter),
                                 "annual": service.annual(year)})

    @app.get("/api/v1/dashboard")
    def dashboard(year: int, month: int, user: User = Depends(require("dashboard:read")),
                  db: Session = Depends(get_db)):
        _, _, boe, budget, targets, _, flow = domain_services(db)
        return jsonable_encoder(DashboardService(flow, boe, budget, targets).get_dashboard_summary(year, month))

    @app.get("/api/v1/reports/annual")
    def annual_report(year: int, user: User = Depends(require("reports:read")),
                      db: Session = Depends(get_db)):
        _, _, boe, budget, _, _, flow = domain_services(db)
        return jsonable_encoder(ReportService(flow, boe, budget).get_annual_report(year))

    @app.get("/api/v1/reports/csv-validation")
    def csv_validation(year: int, user: User = Depends(require("reports:read")),
                       db: Session = Depends(get_db)):
        service = SiteCSVService(EntityRepository(db), TargetRepository(db),
                                 AssociationRepository(db), CSVExportRepository(db))
        return jsonable_encoder(service.validate_year(year))

    @app.post("/api/v1/reports/csv-export")
    def csv_export(payload: dict = Body(...), user: User = Depends(require("reports:export")),
                   db: Session = Depends(get_db)):
        import io
        service = SiteCSVService(EntityRepository(db), TargetRepository(db),
                                 AssociationRepository(db), CSVExportRepository(db))
        with TemporaryDirectory(prefix="finance_csv_") as directory:
            try:
                result = service.export_all(int(payload["year"]), directory)
            except CSVExportValidationError as error:
                raise HTTPException(status_code=422, detail=error.errors) from None
            buffer = io.BytesIO()
            with ZipFile(buffer, "w", ZIP_DEFLATED) as archive:
                for file_path in (*result.files, result.report_file):
                    archive.write(file_path, file_path.name)
            audit(db, "CSV_EXPORTED", user, entity_type="CSVExport", details={"year": payload["year"]})
            db.commit()
            return Response(buffer.getvalue(), media_type="application/zip",
                            headers={"Content-Disposition": "attachment; filename=finance_csv.zip"})

    app.state.get_db = get_db
    app.state.current_user = current_user
    return app
