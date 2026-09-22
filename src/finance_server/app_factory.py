from datetime import datetime, timedelta, timezone
from ipaddress import ip_address

from fastapi import Body, Depends, FastAPI, File, Form, HTTPException, Query, Request, UploadFile
from fastapi.encoders import jsonable_encoder
from fastapi.responses import JSONResponse, Response
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
import jwt
from sqlalchemy import create_engine, func, or_, select
from sqlalchemy.orm import Session, sessionmaker
from sqlalchemy.pool import NullPool
from pathlib import Path
from shutil import copyfileobj
from tempfile import TemporaryDirectory
from zipfile import ZIP_DEFLATED, ZipFile

from app.database.base import Base
from finance_server.config import ServerSettings, get_server_settings
from finance_server.email_service import EmailService, FakeEmailService, SMTPEmailService
from finance_server.models import (
    AuditLog, PasswordResetToken, RefreshSession, User, UserRole,
)
from finance_server.initial_setup import (
    InitialAdministratorData,
    InitialSetupUnavailableError,
    create_initial_administrator,
    users_exist,
)
from finance_server.assisted_recovery import (
    AssistedRecoveryError,
    create_request as create_assisted_recovery_request,
    validate_authorization as validate_assisted_recovery_authorization,
)
from finance_server.personal_recovery import (
    PersonalRecoveryError,
    generate_key as generate_personal_recovery_key,
    revoke_active_keys as revoke_active_personal_recovery_keys,
    validate_key as validate_personal_recovery_key,
)
from finance_server.rbac import has_permission
from finance_server.schemas import (
    AdminPasswordResetRequest,
    AssistedRecoveryAuthorizationRequest, AssistedRecoveryAuthorizationResponse,
    AssistedRecoveryCompleteRequest, AssistedRecoveryRequestCreate,
    AssistedRecoveryRequestResponse, AuditResponse, ChangePasswordRequest,
    CompletePasswordChangeRequest, CompletePasswordChangeResponse,
    ForgotPasswordRequest, LoginRequest,
    PersonalRecoveryRequest,
    InitialAdministratorCreate, InitialSetupStatus,
    RankingParameterResponse, RankingParameterValues,
    RefreshRequest, ResetPasswordRequest, TokenPair, UserCreate, UserResponse, UserUpdate,
    CashflowCreate, CashflowUpdate, CashflowResponse,
    BudgetCreate, BudgetUpdate, BudgetResponse,
    EntityCreate, EntityUpdate, EntityResponse,
    CatalogCreate, CatalogUpdate, CatalogResponse,
)
from app.models.cashflow_entry import CashflowEntry, CashflowOrigin, CashflowType, CashflowCategory
from app.models.entity import Entity
from app.models.ranking_parameter import RankingParameter
from app.repositories.association_repository import AssociationRepository
from app.repositories.boe_repository import BOERepository
from app.repositories.budget_repository import BudgetRepository
from app.repositories.cashflow_repository import CashflowRepository
from app.repositories.csv_export_repository import CSVExportRepository
from app.repositories.entity_repository import EntityRepository
from app.repositories.investment_repository import InvestmentRepository
from app.repositories.target_repository import TargetRepository
from app.repositories.ranking_parameter_repository import RankingParameterRepository
from app.importers.boe_importer import BOEImporter
from app.services.boe_service import BOEService
from app.services.budget_service import BudgetService
from app.services.budget_import_service import (
    BudgetImportService, BudgetImportValidationError,
)
from app.services.cashflow_service import CashflowService
from app.services.dashboard_service import DashboardService
from app.services.financial_flow_service import FinancialFlowService
from app.services.financial_import_service import (
    FinancialImportService, FinancialImportValidationError,
)
from app.services.investment_service import InvestmentService
from app.services.ranking_service import RankingParametersNotConfiguredError, RankingService
from app.services.report_service import ReportService
from app.services.site_csv_service import SiteCSVService
from app.services.target_service import TargetService
from app.services.target_import_service import (
    TargetImportService, TargetImportValidationError,
)
from app.core.exceptions import BOEValidationError, CSVExportValidationError, CashflowDuplicateBOEError, CashflowIntegrityError
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


def runtime_environment_metadata(dialect_name: str) -> dict:
    is_dev_sqlite = dialect_name == "sqlite"
    return {
        "environment": "DEV" if is_dev_sqlite else "SERVER",
        "database": "SQLite DEV" if is_dev_sqlite else "PostgreSQL central",
        "historical_import_enabled": is_dev_sqlite,
    }


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
        with Session(engine) as seed_session:
            if seed_session.scalar(
                select(RankingParameter.id).where(RankingParameter.year == 2026)
            ) is None:
                seed_session.add(RankingParameter.defaults_2026())
                seed_session.commit()
    app = FastAPI(title="Finance API", version=__version__)

    @app.exception_handler(CashflowIntegrityError)
    async def cashflow_integrity_error(request: Request, error: CashflowIntegrityError):
        return JSONResponse(status_code=500, content={"detail": str(error)})

    @app.exception_handler(CashflowDuplicateBOEError)
    async def cashflow_duplicate_boe(request: Request, error: CashflowDuplicateBOEError):
        return JSONResponse(status_code=409, content={"detail": str(error)})

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

    def local_setup_origin(request: Request) -> str:
        host = request.client.host if request.client else ""
        forwarded = request.headers.get("forwarded") or request.headers.get(
            "x-forwarded-for"
        )
        try:
            local = ip_address(host).is_loopback
        except ValueError:
            local = host.casefold() == "localhost"
        if not local or forwarded:
            raise HTTPException(
                status_code=403,
                detail="A configuração inicial está disponível somente localmente.",
            )
        return host

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
            if user.must_change_password:
                raise HTTPException(
                    status_code=403,
                    detail="Troca de senha obrigatória antes de acessar o Finance.",
                )
            if not has_permission(user, permission):
                raise HTTPException(status_code=403, detail="Permissão insuficiente.")
            return user
        return dependency

    def require_administrator(user: User = Depends(current_user)) -> User:
        if user.must_change_password:
            raise HTTPException(
                status_code=403,
                detail="Troca de senha obrigatória antes de acessar o Finance.",
            )
        if user.perfil != UserRole.ADMINISTRATOR.value:
            raise HTTPException(status_code=403, detail="Permissão insuficiente.")
        return user

    def issue_pair(
        db: Session,
        user: User,
        *,
        personal_recovery_key: str | None = None,
    ) -> TokenPair:
        access = create_access_token(user.id, user.perfil, settings.secret_key,
                                     settings.access_token_minutes)
        refresh = random_token()
        db.add(RefreshSession(
            user_id=user.id, token_hash=token_hash(refresh),
            expires_at=utcnow() + timedelta(days=settings.refresh_token_days),
        ))
        return TokenPair(access_token=access, refresh_token=refresh,
                         expires_in=settings.access_token_minutes * 60,
                         must_change_password=user.must_change_password,
                         personal_recovery_key=personal_recovery_key)

    def domain_services(db: Session):
        cashflow = CashflowService(CashflowRepository(db))
        investments = InvestmentService(InvestmentRepository(db))
        boe = BOEService(BOERepository(db), EntityRepository(db), BOEImporter(), cashflow)
        budget = BudgetService(BudgetRepository(db), CashflowRepository(db))
        targets = TargetService(TargetRepository(db), EntityRepository(db))
        ranking = RankingService(
            TargetRepository(db), AssociationRepository(db),
            RankingParameterRepository(db),
        )
        flow = FinancialFlowService(cashflow, investments)
        return cashflow, investments, boe, budget, targets, ranking, flow

    @app.get("/health")
    def health():
        return {
            "status": "ok",
            "version": __version__,
            **runtime_environment_metadata(engine.dialect.name),
        }

    @app.get("/api/v1/setup/status", response_model=InitialSetupStatus)
    def initial_setup_status(
        request: Request, db: Session = Depends(get_db)
    ) -> InitialSetupStatus:
        local_setup_origin(request)
        return InitialSetupStatus(requires_initial_setup=not users_exist(db))

    @app.post(
        "/api/v1/setup/administrator",
        response_model=UserResponse,
        status_code=201,
    )
    def initial_setup_administrator(
        payload: InitialAdministratorCreate,
        request: Request,
        db: Session = Depends(get_db),
    ):
        origin = local_setup_origin(request)
        try:
            target = create_initial_administrator(
                db,
                InitialAdministratorData(
                    nome=payload.nome,
                    email=str(payload.email),
                    username=payload.username,
                    password=payload.password,
                ),
                origin=origin,
            )
            db.commit()
            db.refresh(target)
            return target
        except InitialSetupUnavailableError as error:
            db.rollback()
            raise HTTPException(status_code=409, detail=str(error)) from None
        except ValueError as error:
            db.rollback()
            raise HTTPException(status_code=422, detail=str(error)) from None
        except Exception:
            db.rollback()
            raise

    @app.post(
        "/api/v1/auth/login",
        response_model=TokenPair,
        response_model_exclude_none=True,
    )
    def login(payload: LoginRequest, request: Request, db: Session = Depends(get_db)):
        identifier = payload.identifier.strip().casefold()
        user = db.scalar(select(User).where(or_(func.lower(User.username) == identifier,
                                                func.lower(User.email) == identifier)))
        if user is None or not user.ativo or not verify_password(payload.password, user.password_hash):
            audit(db, "LOGIN_FAILED", user, origin=request.client.host if request.client else None)
            db.commit()
            raise HTTPException(status_code=401, detail="Usuário ou senha inválidos.")
        user.ultimo_login = utcnow()
        raw_key = None
        if user.personal_recovery_key_pending and not user.must_change_password:
            raw_key, key = generate_personal_recovery_key(db, user)
            user.personal_recovery_key_pending = False
            audit(
                db,
                "PERSONAL_RECOVERY_KEY_CREATED",
                user,
                entity_type="PersonalRecoveryKey",
                entity_id=key.id,
            )
        pair = issue_pair(db, user, personal_recovery_key=raw_key)
        audit(db, "LOGIN", user, origin=request.client.host if request.client else None)
        db.commit()
        return pair

    @app.post(
        "/api/v1/auth/refresh",
        response_model=TokenPair,
        response_model_exclude_none=True,
    )
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
        if user.must_change_password:
            raise HTTPException(
                status_code=409,
                detail="Conclua a troca obrigatória da senha temporária.",
            )
        if not verify_password(payload.current_password, user.password_hash):
            raise HTTPException(status_code=400, detail="Senha atual inválida.")
        try:
            user.password_hash = hash_password(payload.new_password)
        except ValueError as error:
            raise HTTPException(status_code=422, detail=str(error)) from None
        audit(db, "PASSWORD_CHANGED", user)
        db.commit()

    def assisted_environment() -> str:
        return runtime_environment_metadata(engine.dialect.name)["environment"]

    @app.post(
        "/api/v1/auth/assisted-recovery/request",
        response_model=AssistedRecoveryRequestResponse,
    )
    def assisted_recovery_request(
        payload: AssistedRecoveryRequestCreate,
        db: Session = Depends(get_db),
    ):
        created = create_assisted_recovery_request(
            db,
            payload.identifier,
            assisted_environment(),
            settings.assisted_recovery_request_minutes,
        )
        message = "Solicitação processada."
        if created is None:
            return AssistedRecoveryRequestResponse(message=message)
        item, code = created
        user = db.get(User, item.user_id)
        audit(
            db,
            "PASSWORD_ASSISTED_RECOVERY_REQUESTED",
            user,
            entity_type="AssistedRecoveryRequest",
            entity_id=item.request_id,
            details={"environment": item.environment},
        )
        db.commit()
        return AssistedRecoveryRequestResponse(message=message, request_code=code)

    @app.post(
        "/api/v1/auth/assisted-recovery/validate",
        response_model=AssistedRecoveryAuthorizationResponse,
    )
    def assisted_recovery_validate(
        payload: AssistedRecoveryAuthorizationRequest,
        db: Session = Depends(get_db),
    ):
        try:
            validate_assisted_recovery_authorization(
                db, payload.authorization, assisted_environment()
            )
        except AssistedRecoveryError as error:
            raise HTTPException(status_code=400, detail=str(error)) from None
        except RuntimeError:
            raise HTTPException(
                status_code=503,
                detail="Recuperação assistida temporariamente indisponível.",
            ) from None
        return AssistedRecoveryAuthorizationResponse(valid=True)

    @app.post("/api/v1/auth/assisted-recovery/complete", status_code=204)
    def assisted_recovery_complete(
        payload: AssistedRecoveryCompleteRequest,
        db: Session = Depends(get_db),
    ):
        try:
            validated = validate_assisted_recovery_authorization(
                db, payload.authorization, assisted_environment()
            )
            new_hash = hash_password(payload.new_password)
        except AssistedRecoveryError as error:
            raise HTTPException(status_code=400, detail=str(error)) from None
        except ValueError as error:
            raise HTTPException(status_code=422, detail=str(error)) from None
        except RuntimeError:
            raise HTTPException(
                status_code=503,
                detail="Recuperação assistida temporariamente indisponível.",
            ) from None
        now = utcnow()
        validated.user.password_hash = new_hash
        validated.user.must_change_password = False
        validated.user.personal_recovery_key_pending = True
        validated.request.used_at = now
        revoke_active_personal_recovery_keys(db, validated.user)
        for item in db.scalars(
            select(RefreshSession).where(
                RefreshSession.user_id == validated.user.id,
                RefreshSession.revoked_at.is_(None),
            )
        ):
            item.revoked_at = now
        audit(
            db,
            "PASSWORD_ASSISTED_RECOVERY_COMPLETED",
            validated.user,
            entity_type="AssistedRecoveryRequest",
            entity_id=validated.request.request_id,
            details={"environment": validated.request.environment},
        )
        db.commit()

    @app.post(
        "/api/v1/auth/complete-password-change",
        response_model=CompletePasswordChangeResponse,
    )
    def complete_password_change(
        payload: CompletePasswordChangeRequest,
        user: User = Depends(current_user),
        db: Session = Depends(get_db),
    ):
        if not user.must_change_password:
            raise HTTPException(status_code=409, detail="A troca obrigatória já foi concluída.")
        try:
            user.password_hash = hash_password(payload.new_password)
        except ValueError as error:
            raise HTTPException(status_code=422, detail=str(error)) from None
        user.must_change_password = False
        user.personal_recovery_key_pending = False
        for item in db.scalars(select(RefreshSession).where(
                RefreshSession.user_id == user.id, RefreshSession.revoked_at.is_(None))):
            item.revoked_at = utcnow()
        raw_key, key = generate_personal_recovery_key(db, user)
        pair = issue_pair(db, user)
        audit(db, "PASSWORD_INITIAL_CHANGED", user)
        audit(
            db,
            "PERSONAL_RECOVERY_KEY_CREATED",
            user,
            entity_type="PersonalRecoveryKey",
            entity_id=key.id,
        )
        db.commit()
        return CompletePasswordChangeResponse(
            **pair.model_dump(exclude={"personal_recovery_key"}),
            personal_recovery_key=raw_key,
        )

    @app.post("/api/v1/auth/personal-recovery", status_code=204)
    def personal_recovery(
        payload: PersonalRecoveryRequest,
        db: Session = Depends(get_db),
    ):
        identifier = payload.identifier.strip().casefold()
        user = db.scalar(
            select(User).where(
                or_(
                    func.lower(User.username) == identifier,
                    func.lower(User.email) == identifier,
                )
            )
        )
        generic = HTTPException(
            status_code=400,
            detail="Identificação ou chave pessoal de recuperação inválida.",
        )
        if user is None or not user.ativo:
            raise generic
        try:
            recovery_key = validate_personal_recovery_key(
                db, user, payload.recovery_key
            )
            new_hash = hash_password(payload.new_password)
        except PersonalRecoveryError:
            raise generic from None
        except ValueError as error:
            raise HTTPException(status_code=422, detail=str(error)) from None
        now = utcnow()
        user.password_hash = new_hash
        user.must_change_password = False
        user.personal_recovery_key_pending = True
        recovery_key.used_at = now
        revoke_active_personal_recovery_keys(db, user)
        for item in db.scalars(
            select(RefreshSession).where(
                RefreshSession.user_id == user.id,
                RefreshSession.revoked_at.is_(None),
            )
        ):
            item.revoked_at = now
        audit(
            db,
            "PASSWORD_PERSONAL_RECOVERY_COMPLETED",
            user,
            entity_type="PersonalRecoveryKey",
            entity_id=recovery_key.id,
        )
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
        if (
            administrator.perfil == UserRole.MANAGER.value
            and role is UserRole.ADMINISTRATOR
        ):
            raise HTTPException(
                status_code=403,
                detail="Gestores não podem criar usuários Administrador.",
            )
        if db.scalar(select(User.id).where(or_(func.lower(User.email) == payload.email.casefold(),
                                              func.lower(User.username) == payload.username.casefold()))):
            raise HTTPException(status_code=409, detail="Email ou username já cadastrado.")
        target = User(nome=payload.nome.strip(), email=payload.email.casefold(),
                      username=payload.username.casefold(), password_hash=password_hash,
                      perfil=role.value, ativo=True, must_change_password=True)
        db.add(target)
        db.flush()
        audit(db, "USER_CREATED", administrator, entity_type="User", entity_id=target.id,
              details={"perfil": target.perfil})
        db.commit()
        return target

    @app.post("/api/v1/users/{user_id}/reset-password", status_code=204)
    def admin_reset_user_password(
        user_id: int,
        payload: AdminPasswordResetRequest,
        administrator: User = Depends(require("users:manage")),
        db: Session = Depends(get_db),
    ):
        target = db.get(User, user_id)
        if target is None:
            raise HTTPException(status_code=404, detail="Usuário não encontrado.")
        if (
            administrator.perfil == UserRole.MANAGER.value
            and target.perfil == UserRole.ADMINISTRATOR.value
        ):
            raise HTTPException(
                status_code=403,
                detail="Gestores não podem administrar usuários Administrador.",
            )
        try:
            target.password_hash = hash_password(payload.temporary_password)
        except ValueError as error:
            raise HTTPException(status_code=422, detail=str(error)) from None

        target.must_change_password = True
        now = utcnow()
        for item in db.scalars(
            select(RefreshSession).where(
                RefreshSession.user_id == target.id,
                RefreshSession.revoked_at.is_(None),
            )
        ):
            item.revoked_at = now

        audit(
            db,
            "USER_PASSWORD_RESET_BY_ADMIN",
            administrator,
            entity_type="User",
            entity_id=target.id,
            details={"target_username": target.username},
        )
        db.commit()

    @app.patch("/api/v1/users/{user_id}", response_model=UserResponse)
    def update_user(user_id: int, payload: UserUpdate,
                    administrator: User = Depends(require("users:manage")),
                    db: Session = Depends(get_db)):
        target = db.get(User, user_id)
        if target is None:
            raise HTTPException(status_code=404, detail="Usuário não encontrado.")
        changes = payload.model_dump(exclude_unset=True)
        if administrator.perfil == UserRole.MANAGER.value:
            if target.perfil == UserRole.ADMINISTRATOR.value:
                raise HTTPException(
                    status_code=403,
                    detail="Gestores não podem administrar usuários Administrador.",
                )
            if changes.get("perfil") == UserRole.ADMINISTRATOR.value:
                raise HTTPException(
                    status_code=403,
                    detail="Gestores não podem promover usuários a Administrador.",
                )
        if "perfil" in changes:
            try:
                changes["perfil"] = UserRole(changes["perfil"]).value
            except ValueError as error:
                raise HTTPException(status_code=422, detail=str(error)) from None
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
        user: User = Depends(require("entities:read")),
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
            entity = service.update_entity(
                entity_id, **payload.model_dump(exclude_unset=True)
            )
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
        user: User = Depends(require("entities:read")),
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
        user: User = Depends(require("catalog:read")),
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
        from app.repositories.financial_balance_repository import FinancialBalanceRepository
        from app.services.financial_balance_service import FinancialBalanceService
        *_, flow = domain_services(db)
        position = FinancialBalanceService(
            FinancialBalanceRepository(db), flow
        ).position(year, month)
        return jsonable_encoder({
            "items": flow.list_by_period(year, month),
            "summary": flow.get_summary(year, month),
            "position": position,
        })

    def financial_import_response(validation):
        return jsonable_encoder({
            "file_name": validation.file_name,
            "detected_type": validation.detected_type,
            "preview": validation.preview,
            "warnings": validation.warnings,
            "errors": validation.errors,
            "duplicates": validation.duplicates,
            "total": validation.total,
            "can_import": validation.can_import,
        })

    @app.post("/api/v1/financial-import/validate")
    async def validate_financial_import(
        file: UploadFile = File(...),
        user: User = Depends(require("cashflow:write")),
        db: Session = Depends(get_db),
    ):
        with TemporaryDirectory(prefix="finance_cashflow_") as directory:
            file_name = Path(file.filename or "financeiro.xlsx").name
            path = Path(directory) / file_name
            path.write_bytes(await file.read())
            service = FinancialImportService(
                db, CashflowCatalogService(CashflowCatalogRepository(db))
            )
            return financial_import_response(
                service.validate(path, file_name=file_name)
            )

    @app.post("/api/v1/financial-import", status_code=201)
    async def import_financial(
        file: UploadFile = File(...),
        user: User = Depends(require("cashflow:write")),
        db: Session = Depends(get_db),
    ):
        with TemporaryDirectory(prefix="finance_cashflow_") as directory:
            file_name = Path(file.filename or "financeiro.xlsx").name
            path = Path(directory) / file_name
            path.write_bytes(await file.read())
            service = FinancialImportService(
                db, CashflowCatalogService(CashflowCatalogRepository(db))
            )
            try:
                validation, entries = service.stage_import(
                    path, file_name=file_name
                )
                for entry in entries:
                    if isinstance(entry, CashflowEntry):
                        entry.created_by_user_id = user.id
                        entry.updated_by_user_id = user.id
                audit(
                    db, "FINANCIAL_IMPORTED", user,
                    entity_type="FinancialImport",
                    details={
                        "file_name": validation.file_name,
                        "imported": len(entries),
                        "ignored": len(validation.preview) - len(entries),
                        "duplicates": validation.duplicates,
                        "warnings": len(validation.warnings),
                    },
                )
                db.commit()
            except FinancialImportValidationError as error:
                db.rollback()
                raise HTTPException(
                    status_code=422,
                    detail=financial_import_response(error.validation),
                ) from None
            except Exception:
                db.rollback()
                raise
        return jsonable_encoder({
            "file_name": validation.file_name,
            "imported": len(entries),
            "ignored": len(validation.preview) - len(entries),
            "duplicates": validation.duplicates,
            "warnings": validation.warnings,
            "total": validation.total,
        })

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

    @app.get("/api/v1/boe/operations/entities")
    def boe_operational_entities(
        user: User = Depends(require("boe:read")), db: Session = Depends(get_db)
    ):
        return [
            {"id": identifier, "name": name}
            for identifier, name in domain_services(db)[2].list_operational_entities()
        ]

    @app.get("/api/v1/boe/operations")
    def boe_operations(
        start_year: int, start_month: int, end_year: int, end_month: int,
        entity_id: int | None = None,
        user: User = Depends(require("boe:read")), db: Session = Depends(get_db),
    ):
        try:
            result = domain_services(db)[2].query_operations(
                start_year, start_month, end_year, end_month, entity_id
            )
        except ValueError as error:
            raise HTTPException(status_code=422, detail=str(error)) from None
        return jsonable_encoder(result)

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

    @app.delete("/api/v1/budgets/{budget_id}", status_code=204)
    def delete_budget(
        budget_id: int,
        user: User = Depends(require("budget:write")),
        db: Session = Depends(get_db),
    ) -> Response:
        item = BudgetRepository(db).get_by_id(budget_id)
        if item is None:
            raise HTTPException(status_code=404, detail="Orçamento não encontrado.")
        details = jsonable_encoder({
            "year": item.periodo_ano,
            "month": item.periodo_mes,
            "type": item.tipo,
            "category": item.categoria,
            "description": item.descricao,
            "budgeted_value": str(item.valor_orcado),
            "notes": item.observacao,
        })
        try:
            audit(
                db,
                "BUDGET_DELETED",
                user,
                entity_type="BudgetEntry",
                entity_id=item.id,
                details=details,
            )
            db.delete(item)
            db.commit()
        except Exception:
            db.rollback()
            raise
        return Response(status_code=204)

    def budget_import_response(validation):
        return jsonable_encoder({
            "metadata": {
                "file_name": validation.file_name,
                "detected_type": validation.detected_type,
                "year": validation.year,
                "sheets": validation.sheets,
            },
            "preview": validation.preview,
            "warnings": validation.warnings,
            "errors": validation.errors,
            "can_import": validation.can_import,
            "totals": {
                "rows": len(validation.preview),
                "value": validation.total,
            },
        })

    @app.post("/api/v1/budgets/import/validate")
    def validate_budget_import(
        file: UploadFile = File(...),
        user: User = Depends(require("budget:write")),
        db: Session = Depends(get_db),
    ):
        with TemporaryDirectory(prefix="finance_budgets_") as directory:
            file_name = Path(file.filename or "orcamento.xlsx").name
            path = Path(directory) / file_name
            with path.open("wb") as destination:
                copyfileobj(file.file, destination)

            service = BudgetImportService(BudgetRepository(db))
            return budget_import_response(
                service.validate(path, file_name=file_name)
            )

    @app.post("/api/v1/budgets/import", status_code=201)
    def import_budgets(
        file: UploadFile = File(...),
        user: User = Depends(require("budget:write")),
        db: Session = Depends(get_db),
    ):
        with TemporaryDirectory(prefix="finance_budgets_") as directory:
            file_name = Path(file.filename or "orcamento.xlsx").name
            path = Path(directory) / file_name
            with path.open("wb") as destination:
                copyfileobj(file.file, destination)

            service = BudgetImportService(BudgetRepository(db))

            try:
                validation, entries = service.stage_import(
                    path, file_name=file_name
                )
                audit(
                    db,
                    "BUDGETS_IMPORTED",
                    user,
                    entity_type="BudgetEntry",
                    details={
                        "file_name": validation.file_name,
                        "year": validation.year,
                        "imported": len(entries),
                        "inconsistencies": len(validation.warnings),
                    },
                )
                db.commit()
            except BudgetImportValidationError as error:
                db.rollback()
                raise HTTPException(
                    status_code=422,
                    detail=budget_import_response(error.validation),
                ) from None
            except Exception:
                db.rollback()
                raise

            return jsonable_encoder({
                "file_name": validation.file_name,
                "year": validation.year,
                "imported": len(entries),
                "warnings": validation.warnings,
                "total": validation.total,
            })

    @app.get("/api/v1/targets")
    def targets(
        year: int, month: int, indicator: str,
        entity_id: list[int] | None = Query(None),
        user: User = Depends(require("targets:read")), db: Session = Depends(get_db),
    ):
        service = domain_services(db)[4]
        return jsonable_encoder({"entities": service.list_entities(),
                                 "comparison": service.get_target_vs_actual(year, month, indicator, entity_id)})

    def target_import_response(validation):
        return jsonable_encoder({
            "metadata": {
                "file_name": validation.file_name,
                "detected_type": validation.detected_type,
                "year": validation.year,
                "sheets": validation.sheets,
            },
            "preview": validation.preview,
            "warnings": validation.warnings,
            "errors": validation.errors,
            "can_import": validation.can_import,
            "totals": {
                "rows": len(validation.preview),
                "target": validation.target_total,
                "actual": validation.actual_total,
            },
        })

    @app.post("/api/v1/targets/import/validate")
    def validate_target_import(
        file: UploadFile = File(...),
        user: User = Depends(require("targets:write")),
        db: Session = Depends(get_db),
    ):
        with TemporaryDirectory(prefix="finance_targets_") as directory:
            file_name = Path(file.filename or "metas.xlsx").name
            path = Path(directory) / file_name
            with path.open("wb") as destination:
                copyfileobj(file.file, destination)
            service = TargetImportService(
                TargetRepository(db), EntityRepository(db)
            )
            return target_import_response(
                service.validate(path, file_name=file_name)
            )

    @app.post("/api/v1/targets/import", status_code=201)
    def import_targets(
        file: UploadFile = File(...),
        user: User = Depends(require("targets:write")),
        db: Session = Depends(get_db),
    ):
        with TemporaryDirectory(prefix="finance_targets_") as directory:
            file_name = Path(file.filename or "metas.xlsx").name
            path = Path(directory) / file_name
            with path.open("wb") as destination:
                copyfileobj(file.file, destination)
            service = TargetImportService(
                TargetRepository(db), EntityRepository(db)
            )
            try:
                validation, entries = service.stage_import(
                    path, file_name=file_name
                )
                audit(
                    db, "TARGETS_IMPORTED", user,
                    entity_type="TargetEntry",
                    details={
                        "file_name": validation.file_name,
                        "year": validation.year,
                        "imported": len(entries),
                        "inconsistencies": len(validation.warnings),
                    },
                )
                db.commit()
            except TargetImportValidationError as error:
                db.rollback()
                raise HTTPException(
                    status_code=422,
                    detail=target_import_response(error.validation),
                ) from None
            except Exception:
                db.rollback()
                raise
            return jsonable_encoder({
                "file_name": validation.file_name,
                "year": validation.year,
                "imported": len(entries),
                "warnings": validation.warnings,
                "target_total": validation.target_total,
                "actual_total": validation.actual_total,
            })

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

    @app.delete("/api/v1/targets/{target_id}", status_code=204)
    def delete_target(
        target_id: int,
        user: User = Depends(require("targets:write")),
        db: Session = Depends(get_db),
    ) -> Response:
        item = TargetRepository(db).get_by_id(target_id)
        if item is None:
            raise HTTPException(status_code=404, detail="Meta não encontrada.")
        details = {
            "entity_id": item.entity_id,
            "entity_code": item.entity.codigo_entidade,
            "year": item.periodo_ano,
            "month": item.periodo_mes,
            "indicator": item.indicador,
            "target": str(item.valor_meta),
            "actual": str(item.valor_realizado),
            "notes": item.observacao,
        }
        try:
            audit(
                db,
                "TARGET_DELETED",
                user,
                entity_type="TargetEntry",
                entity_id=item.id,
                details=details,
            )
            db.delete(item)
            db.commit()
        except Exception:
            db.rollback()
            raise
        return Response(status_code=204)

    @app.get("/api/v1/ranking")
    def ranking(year: int, quarter: int, user: User = Depends(require("ranking:read")),
                db: Session = Depends(get_db)):
        service = domain_services(db)[5]
        try:
            return jsonable_encoder({"quarterly": service.quarterly(year, quarter),
                                     "annual": service.annual(year)})
        except RankingParametersNotConfiguredError as error:
            raise HTTPException(status_code=422, detail=str(error)) from None

    @app.get(
        "/api/v1/ranking/parameters/{year}",
        response_model=RankingParameterResponse,
    )
    def ranking_parameters(
        year: int,
        user: User = Depends(require_administrator),
        db: Session = Depends(get_db),
    ):
        if not 2000 <= year <= 9999:
            raise HTTPException(status_code=422, detail="Ano inválido.")
        item = RankingParameterRepository(db).get_by_year(year)
        if item is None:
            raise HTTPException(
                status_code=404,
                detail=f"Os parâmetros do Ranking para {year} não foram configurados.",
            )
        return item

    @app.put(
        "/api/v1/ranking/parameters/{year}",
        response_model=RankingParameterResponse,
    )
    def save_ranking_parameters(
        year: int,
        payload: RankingParameterValues,
        user: User = Depends(require_administrator),
        db: Session = Depends(get_db),
    ):
        if not 2000 <= year <= 9999:
            raise HTTPException(status_code=422, detail="Ano inválido.")
        repository = RankingParameterRepository(db)
        item = repository.get_by_year(year)
        created = item is None
        if item is None:
            item = RankingParameter(year=year, **payload.model_dump())
            db.add(item)
        else:
            for field, value in payload.model_dump().items():
                setattr(item, field, value)
        try:
            audit(
                db,
                "RANKING_PARAMETERS_CREATED" if created else "RANKING_PARAMETERS_UPDATED",
                user,
                entity_type="RankingParameter",
                entity_id=year,
                details={"year": year},
            )
            db.commit()
            db.refresh(item)
        except Exception:
            db.rollback()
            raise
        return item

    @app.get("/api/v1/dashboard")
    def dashboard(year: int, month: int, user: User = Depends(require("dashboard:read")),
                  db: Session = Depends(get_db)):
        _, _, boe, budget, targets, _, flow = domain_services(db)
        return jsonable_encoder(DashboardService(flow, boe, budget, targets).get_dashboard_summary(year, month))

    @app.get("/api/v1/dashboard/financial")
    def dashboard_financial(
        year: int, month: int, category: str | None = None,
        entry_type: str | None = None,
        user: User = Depends(require("cashflow:read")),
        db: Session = Depends(get_db),
    ):
        if not has_permission(user, "budget:read"):
            raise HTTPException(status_code=403, detail="Permissão insuficiente.")
        _, _, boe, budget, targets, ranking_service, flow = domain_services(db)
        return jsonable_encoder(
            DashboardService(flow, boe, budget, targets, ranking_service)
            .get_financial_dashboard(year, month, category, entry_type)
        )

    @app.get("/api/v1/dashboard/boe")
    def dashboard_boe(
        year: int, month: int, entity_id: int | None = None,
        start_month: int | None = None, end_month: int | None = None,
        user: User = Depends(require("boe:read")),
        db: Session = Depends(get_db),
    ):
        _, _, boe, budget, targets, ranking_service, flow = domain_services(db)
        try:
            return jsonable_encoder(
                DashboardService(flow, boe, budget, targets, ranking_service)
                .get_boe_dashboard(year, month, entity_id, start_month, end_month)
            )
        except ValueError as error:
            raise HTTPException(status_code=422, detail=str(error)) from None

    @app.get("/api/v1/dashboard/targets")
    def dashboard_targets(
        year: int, month: int, entity_id: int | None = None,
        indicator: str = "TODAS", start_month: int | None = None,
        end_month: int | None = None,
        user: User = Depends(require("targets:read")),
        db: Session = Depends(get_db),
    ):
        if not has_permission(user, "ranking:read"):
            raise HTTPException(status_code=403, detail="Permissão insuficiente.")
        _, _, boe, budget, targets, ranking_service, flow = domain_services(db)
        try:
            return jsonable_encoder(
                DashboardService(flow, boe, budget, targets, ranking_service)
                .get_targets_dashboard(
                    year, month, entity_id, indicator, start_month, end_month
                )
            )
        except ValueError as error:
            raise HTTPException(status_code=422, detail=str(error)) from None

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
        return jsonable_encoder(service.validate_period(year))

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
            audit(db, "CSV_EXPORTED", user, entity_type="CSVExport", details={
                "year": payload["year"]
            })
            db.commit()
            return Response(buffer.getvalue(), media_type="application/zip",
                            headers={"Content-Disposition": "attachment; filename=finance_csv.zip"})

    app.state.get_db = get_db
    app.state.current_user = current_user
    return app
