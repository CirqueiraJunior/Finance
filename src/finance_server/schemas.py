from datetime import date, datetime
from decimal import Decimal

from pydantic import BaseModel, ConfigDict, EmailStr, Field


class LoginRequest(BaseModel):
    identifier: str
    password: str


class TokenPair(BaseModel):
    access_token: str
    refresh_token: str
    token_type: str = "bearer"
    expires_in: int


class RefreshRequest(BaseModel):
    refresh_token: str


class ForgotPasswordRequest(BaseModel):
    email: EmailStr


class ResetPasswordRequest(BaseModel):
    token: str
    new_password: str


class ChangePasswordRequest(BaseModel):
    current_password: str
    new_password: str


class UserCreate(BaseModel):
    nome: str = Field(min_length=2, max_length=255)
    email: EmailStr
    username: str = Field(min_length=3, max_length=100)
    password: str
    perfil: str


class UserUpdate(BaseModel):
    nome: str | None = None
    perfil: str | None = None
    ativo: bool | None = None


class UserResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: int
    nome: str
    email: str
    username: str
    perfil: str
    ativo: bool
    ultimo_login: datetime | None
    created_at: datetime
    updated_at: datetime


class AuditResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: int
    user_id: int | None
    timestamp: datetime
    action: str
    entity_type: str | None
    entity_id: str | None
    details: dict | None
    origin: str | None


class CashflowCreate(BaseModel):
    periodo_ano: int = Field(ge=2000, le=9999)
    periodo_mes: int = Field(ge=1, le=12)
    data_lancamento: date
    descricao: str = Field(min_length=1, max_length=255)
    tipo: str
    categoria: str
    valor: Decimal = Field(gt=0)
    observacao: str | None = None
    boe: bool = False


class CashflowUpdate(BaseModel):
    expected_version: int = Field(ge=1)
    descricao: str | None = Field(None, min_length=1, max_length=255)
    valor: Decimal | None = Field(None, gt=0)
    observacao: str | None = None


class CashflowResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: int
    periodo_ano: int
    periodo_mes: int
    data_lancamento: date
    descricao: str
    tipo: str
    categoria: str
    valor: Decimal
    observacao: str | None
    created_by_user_id: int | None
    updated_by_user_id: int | None
    version: int
    created_at: datetime
    updated_at: datetime


class BudgetCreate(BaseModel):
    year: int = Field(ge=2000, le=9999)
    month: int = Field(ge=1, le=12)
    description: str = Field(min_length=1, max_length=255)
    entry_type: str
    category: str
    budgeted_value: Decimal = Field(ge=0)
    notes: str | None = None


class BudgetUpdate(BaseModel):
    description: str | None = Field(None, min_length=1, max_length=255)
    budgeted_value: Decimal = Field(ge=0)
    notes: str | None = None


class BudgetResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: int
    periodo_ano: int
    periodo_mes: int
    descricao: str | None
    tipo: str
    categoria: str
    valor_orcado: Decimal
    observacao: str | None
    created_at: datetime
    updated_at: datetime

class EntityAliasResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    alias: str
    origem: str | None = None


class EntityCreate(BaseModel):
    codigo_entidade: int = Field(gt=0)
    nome: str = Field(min_length=1, max_length=255)
    nome_oficial: str | None = Field(None, max_length=255)
    municipio: str | None = Field(None, max_length=150)
    uf: str | None = Field(None, max_length=2)
    sigla: str | None = Field(None, max_length=50)
    ativa: bool = True


class EntityUpdate(BaseModel):
    nome: str = Field(min_length=1, max_length=255)
    nome_oficial: str | None = Field(None, max_length=255)
    municipio: str | None = Field(None, max_length=150)
    uf: str | None = Field(None, max_length=2)
    sigla: str | None = Field(None, max_length=50)
    ativa: bool | None = None


class EntityResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    codigo_entidade: int
    nome: str
    nome_oficial: str | None
    municipio: str | None
    uf: str | None
    sigla: str | None
    ativa: bool
    aliases: list[EntityAliasResponse] = []


class CatalogCreate(BaseModel):
    description: str = Field(min_length=1, max_length=255)
    category: str
    movement_type: str
    active: bool = True


class CatalogUpdate(CatalogCreate):
    pass


class CatalogResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    descricao: str
    categoria: str
    tipo: str
    ativa: bool
