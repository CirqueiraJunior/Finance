from PySide6.QtWidgets import QDialog, QLineEdit

from app.gui.service_config_dialog import ServiceConfigurationDialog


def test_service_configuration_dialog_masks_password(qtbot):
    dialog = ServiceConfigurationDialog()
    qtbot.addWidget(dialog)

    assert dialog.password.echoMode() == QLineEdit.EchoMode.Password


def test_service_configuration_dialog_provisions_without_exposing_secret(
    qtbot, monkeypatch,
):
    captured = {}
    dialog = ServiceConfigurationDialog()
    qtbot.addWidget(dialog)
    dialog.host.setText("db.example")
    dialog.database.setText("postgres")
    dialog.username.setText("finance.user")
    dialog.password.setText("Password1")
    monkeypatch.setattr(
        "app.gui.service_config_dialog.provision_service_configuration",
        lambda **kwargs: captured.update(kwargs),
    )
    monkeypatch.setattr(
        "app.gui.service_config_dialog.QMessageBox.information",
        lambda *args: None,
    )

    dialog._save()

    assert dialog.result() == QDialog.DialogCode.Accepted
    assert captured == {
        "host": "db.example",
        "port": 5432,
        "database": "postgres",
        "username": "finance.user",
        "password": "Password1",
    }
    assert dialog.password.text() == ""
