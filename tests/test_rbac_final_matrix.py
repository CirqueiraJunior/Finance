from finance_server.models import UserRole
from finance_server.rbac import ROLE_PERMISSIONS


def test_finance_operator_has_operational_financial_permissions_only():
    assert ROLE_PERMISSIONS[UserRole.FINANCE_OPERATOR] == {
        "dashboard:read",
        "cashflow:read",
        "cashflow:write",
        "budget:read",
        "catalog:read",
        "catalog:manage",
    }


def test_boe_operator_is_read_only_and_limited():
    assert ROLE_PERMISSIONS[UserRole.BOE_OPERATOR] == {
        "dashboard:read",
        "boe:read",
        "entities:read",
    }


def test_manager_keeps_full_functional_access():
    permissions = ROLE_PERMISSIONS[UserRole.MANAGER]
    assert {
        "dashboard:read",
        "cashflow:write",
        "budget:write",
        "boe:write",
        "targets:write",
        "ranking:read",
        "reports:export",
        "entities:manage",
        "catalog:manage",
        "users:manage",
    } <= permissions


def test_read_only_profile_preserves_previous_functional_modules():
    permissions = ROLE_PERMISSIONS[UserRole.READ_ONLY]
    assert {
        "dashboard:read",
        "cashflow:read",
        "budget:read",
        "boe:read",
        "targets:read",
        "ranking:read",
        "reports:read",
        "entities:read",
    } <= permissions
