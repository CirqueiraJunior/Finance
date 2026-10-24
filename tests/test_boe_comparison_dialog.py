from types import SimpleNamespace

from app.gui.boe_comparison_dialog import BOEComparisonDialog


def result(*, approved=True, issues=(), errors=0, warnings=0):
    return SimpleNamespace(
        aprovado=approved,
        nome_arquivo="boe_outubro.xlsx",
        periodo_ano=2026,
        periodo_mes=10,
        linhas=(object(), object()),
        inconsistencias=issues,
        quantidade_erros=errors,
        quantidade_avisos=warnings,
        valor_total_calculado=100,
    )


def test_boe_approved_exposes_authorization(qtbot):
    dialog = BOEComparisonDialog(result())
    qtbot.addWidget(dialog)
    assert dialog.authorize_button is not None
    assert dialog.authorize_button.isEnabled()


def test_boe_rejected_blocks_authorization(qtbot):
    dialog = BOEComparisonDialog(result(approved=False, errors=1))
    qtbot.addWidget(dialog)
    assert dialog.authorize_button is None


def test_boe_errors_block_authorization(qtbot):
    dialog = BOEComparisonDialog(result(errors=2))
    qtbot.addWidget(dialog)
    assert dialog.authorize_button is None


def test_boe_explicit_permission_blocks_authorization(qtbot):
    dialog = BOEComparisonDialog(
        result(), can_authorize=False
    )
    qtbot.addWidget(dialog)
    assert dialog.authorize_button is None


def test_boe_issues_remain_read_only(qtbot):
    issue = SimpleNamespace(
        severidade=SimpleNamespace(value="ERROR"),
        linha=14,
        codigo="BOE001",
        mensagem="Entidade inválida",
    )
    dialog = BOEComparisonDialog(
        result(approved=False, issues=(issue,), errors=1)
    )
    qtbot.addWidget(dialog)
    assert dialog.authorize_button is None
    assert "boe_outubro.xlsx" in dialog.windowTitle()


def test_boe_reuses_shared_dialog(qtbot):
    from app.gui.import_comparison_dialog import (
        ImportComparisonDialog,
    )
    dialog = BOEComparisonDialog(result())
    qtbot.addWidget(dialog)
    assert isinstance(dialog, ImportComparisonDialog)
