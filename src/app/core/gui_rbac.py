"""Visibilidade dos módulos Desktop derivada do RBAC oficial da API."""

from finance_server.models import UserRole
from finance_server.rbac import ROLE_PERMISSIONS


MODULE_PERMISSIONS = {
    "dashboard": "dashboard:read",
    "financeiro": "cashflow:read",
    "orcamento": "budget:read",
    "boe": "boe:read",
    "metas": "targets:read",
    "relatorios": "reports:read",
}

REGISTRATION_AREAS_BY_ROLE = {
    UserRole.ADMINISTRATOR.value: {"entities", "catalog"},
    UserRole.MANAGER.value: {"entities", "catalog"},
    UserRole.FINANCE_OPERATOR.value: {"catalog"},
    UserRole.BOE_OPERATOR.value: {"entities"},
    UserRole.READ_ONLY.value: set(),
}

ROLE_LABELS = {
    UserRole.ADMINISTRATOR.value: "Administrador",
    UserRole.MANAGER.value: "Gestor",
    UserRole.FINANCE_OPERATOR.value: "Operador financeiro",
    UserRole.BOE_OPERATOR.value: "Operador BOE",
    UserRole.READ_ONLY.value: "Consulta",
}


def permissions_for_role(role: str) -> set[str]:
    try:
        return set(ROLE_PERMISSIONS.get(UserRole(role), set()))
    except ValueError:
        return set()


def role_has_permission(role: str, permission: str) -> bool:
    permissions = permissions_for_role(role)
    return "*" in permissions or permission in permissions


def allowed_modules(role: str) -> set[str]:
    modules = {
        module
        for module, permission in MODULE_PERMISSIONS.items()
        if role_has_permission(role, permission)
    }
    if allowed_registration_areas(role):
        modules.add("cadastros")
    # Administração hospeda a área pessoal de todo usuário autenticado.
    if permissions_for_role(role):
        modules.add("administracao")
    return modules


def allowed_registration_areas(role: str) -> set[str]:
    return set(REGISTRATION_AREAS_BY_ROLE.get(role, set()))


def role_label(role: str) -> str:
    return ROLE_LABELS.get(role, role)


def allowed_dashboard_areas(role: str) -> set[str]:
    permission_by_area = {
        "financial": "cashflow:read",
        "boe": "boe:read",
        "targets": "targets:read",
    }
    return {
        area
        for area, permission in permission_by_area.items()
        if role_has_permission(role, permission)
    }
