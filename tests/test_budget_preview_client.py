import pytest
from app.services.remote_services import RemoteBudgetService

class FakeAPI:
    def __init__(self, value):
        self.value = value
        self.calls = []
    def upload(self, endpoint, path, **kwargs):
        self.calls.append((endpoint, path, kwargs))
        if endpoint.endswith("/validate"):
            return self.value
        return {"imported": 1}

def test_token_forwarding():
    api = FakeAPI({"can_import": True, "preview_authorization": "token"})
    service = RemoteBudgetService(api)
    service.validate_import("orcado.xlsx")
    service.import_file("orcado.xlsx")
    assert api.calls[-1][2]["preview_authorization"] == "token"
    assert service._budget_preview_authorization is None

def test_invalid_validation_discards_old_token():
    api = FakeAPI({"can_import": True, "preview_authorization": "token"})
    service = RemoteBudgetService(api)
    service.validate_import("old.xlsx")
    api.value = {"can_import": False}
    service.validate_import("new.xlsx")
    assert service._budget_preview_authorization is None

def test_another_file_is_blocked():
    api = FakeAPI({"can_import": True, "preview_authorization": "token"})
    service = RemoteBudgetService(api)
    service.validate_import("old.xlsx")
    with pytest.raises(ValueError):
        service.import_file("new.xlsx")
    assert len(api.calls) == 1

def test_import_without_preview_is_blocked():
    api = FakeAPI({"can_import": True})
    service = RemoteBudgetService(api)
    service.validate_import("file.xlsx")
    with pytest.raises(ValueError, match="Previa ausente"):
        service.import_file("file.xlsx")
    assert len(api.calls) == 1
