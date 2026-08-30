from collections.abc import Callable

from fastapi import Depends, HTTPException, status

from finance_server.models import User, UserRole


ROLE_PERMISSIONS = {
    UserRole.ADMINISTRATOR: {"*"},
    UserRole.MANAGER: {"dashboard:read", "cashflow:read", "cashflow:write", "budget:read",
                       "budget:write", "boe:read", "boe:write", "targets:read", "targets:write",
                       "ranking:read", "reports:read", "reports:export", "admin:read",
                       "entities:manage", "catalog:manage"},
    UserRole.FINANCE_OPERATOR: {"dashboard:read", "cashflow:read", "cashflow:write",
                                "budget:read", "budget:write", "reports:read", "reports:export"},
    UserRole.BOE_OPERATOR: {"dashboard:read", "boe:read", "boe:write", "targets:read",
                            "ranking:read"},
    UserRole.READ_ONLY: {"dashboard:read", "cashflow:read", "budget:read", "boe:read",
                         "targets:read", "ranking:read", "reports:read"},
}


def has_permission(user: User, permission: str) -> bool:
    permissions = ROLE_PERMISSIONS.get(UserRole(user.perfil), set())
    return "*" in permissions or permission in permissions


def require_permission(permission: str, current_user_dependency: Callable) -> Callable:
    def dependency(user: User = Depends(current_user_dependency)) -> User:
        if not has_permission(user, permission):
            raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Permissão insuficiente.")
        return user
    return dependency
