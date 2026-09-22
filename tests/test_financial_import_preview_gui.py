from app.gui.pages.financeiro import FinanceiroPage
from app.api_client.client import AuthenticatedUser
from app.core.config import Settings
from app.gui.main_window import MainWindow
from app.services.remote_services import RemoteCashflowService
from tests.test_sprint12a1_centralization import FakeRemoteAPI


def test_financial_preview_shows_multiple_rows(qtbot):
    page = FinanceiroPage()
    qtbot.addWidget(page)

    rows = [
        {
            "line": 3 + index,
            "year": 2026,
            "month": 4,
            "type": "DESPESA",
            "description": f"Item {index + 1}",
            "category": "ADMINISTRATIVO",
            "boe": False,
            "value": str(10 + index),
        }
        for index in range(6)
    ]

    page.show_import_validation({
        "preview": rows,
        "warnings": [],
        "errors": [],
        "can_import": True,
    })

    assert page.import_preview.rowCount() == 6
    assert page.import_preview.item(0, 3).text() == "Item 1"
    assert page.import_preview.item(5, 3).text() == "Item 6"
    assert page.import_preview.minimumHeight() >= 150
    assert page.import_issues.toPlainText() == "Arquivo validado sem inconsistências."
    assert page.import_issues_scroll.height() <= 96


def test_financial_validation_keeps_errors_and_warnings_without_squeezing_preview(qtbot):
    page = FinanceiroPage()
    qtbot.addWidget(page)
    page.resize(1200, 650)
    page.show()

    rows = [{
        "line": index, "year": 2026, "month": 1, "type": "DESPESA",
        "description": f"Item {index}", "category": "OPERACIONAL",
        "boe": False, "value": "10.00",
    } for index in range(1, 7)]
    error = (
        "Nenhum lançamento novo pode ser importado; o arquivo contém apenas "
        "Receita Direta originada de BOE ou registros duplicados."
    )
    warning = "Linha já existente será ignorada."

    page.show_import_validation({
        "preview": rows,
        "warnings": [warning] * 30,
        "errors": [error],
        "can_import": False,
    })
    qtbot.wait(10)

    assert page.import_preview.rowCount() == 6
    assert page.import_preview.item(0, 3).text() == "Item 1"
    assert page.import_preview.item(5, 3).text() == "Item 6"
    assert error in page.import_issues.toPlainText()
    assert warning in page.import_issues.toPlainText()
    assert page.import_issues_scroll.height() <= 96
    assert page.import_preview.height() >= 150


def test_remote_financial_validation_preserves_every_preview_row():
    rows = [{"line": index} for index in range(1, 7)]

    class API:
        def upload(self, endpoint, file_path):
            assert endpoint == "/api/v1/financial-import/validate"
            return {"preview": rows, "errors": [], "warnings": []}

    result = RemoteCashflowService(API()).validate_import("Financeiro.xlsx")

    assert len(result["preview"]) == 6
    assert result["preview"][0]["line"] == 1
    assert result["preview"][-1]["line"] == 6


def test_financial_layout_uses_window_height_at_1366x768(qtbot, tmp_path):
    settings = Settings(
        "Finance", "development", False,
        f"sqlite:///{(tmp_path / 'unused.db').as_posix()}", "INFO", tmp_path,
    )
    window = MainWindow(
        settings,
        api_client=FakeRemoteAPI(),
        authenticated_user=AuthenticatedUser(
            1, "Administrador", "ADMINISTRADOR", False
        ),
    )
    qtbot.addWidget(window)
    window.resize(1366, 768)
    window.show()
    window.navigation.navigate_to("financeiro")
    qtbot.waitExposed(window)
    page = window.pages["financeiro"]

    assert page.entries_table.height() == 92
    assert page.import_preview.height() >= 150

    rows = [{
        "line": index, "year": 2026, "month": 1, "type": "DESPESA",
        "description": f"Item {index}", "category": "OPERACIONAL",
        "boe": False, "value": "10.00",
    } for index in range(1, 13)]
    page.show_import_validation({
        "preview": rows,
        "warnings": [],
        "errors": ["Erro bloqueante de validação totalmente legível."],
        "can_import": False,
    })
    qtbot.wait(20)

    assert page.import_preview.rowCount() == 12
    assert page.import_preview.height() >= 150
    assert page.import_issues.isVisible()
    assert page.import_issues.height() >= page.import_issues.sizeHint().height()
    assert page.import_issues_scroll.height() <= 96
    status_bottom = page.operation_status.mapToGlobal(
        page.operation_status.rect().bottomLeft()
    ).y()
    statusbar_top = window.statusBar().mapToGlobal(
        window.statusBar().rect().topLeft()
    ).y()
    assert 0 <= statusbar_top - status_bottom - 1 <= 12
