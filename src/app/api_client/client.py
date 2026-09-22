"""Cliente da API; credenciais e tokens nunca são persistidos localmente."""

from dataclasses import dataclass
from typing import Any

import httpx
import jwt


class APIConnectionError(RuntimeError):
    pass


class APIReadTimeoutError(APIConnectionError):
    pass


class AuthenticationError(RuntimeError):
    pass


@dataclass(frozen=True, slots=True)
class AuthenticatedUser:
    user_id: int
    nome: str
    perfil: str
    must_change_password: bool = False
    personal_recovery_key: str | None = None


@dataclass(frozen=True, slots=True)
class PasswordChangeCompletion:
    user: AuthenticatedUser
    personal_recovery_key: str


class APIClient:
    def __init__(self, base_url: str, timeout: float = 10.0) -> None:
        self._client = httpx.Client(base_url=base_url, timeout=timeout)
        self._access_token: str | None = None
        self._refresh_token: str | None = None

    @property
    def authenticated(self) -> bool:
        return self._access_token is not None

    def health(self) -> dict[str, Any]:
        return self._request("GET", "/health", authenticated=False)

    def initial_setup_required(self) -> bool:
        data = self._request(
            "GET", "/api/v1/setup/status", authenticated=False
        )
        return bool(data["requires_initial_setup"])

    def create_initial_administrator(
        self, payload: dict[str, str]
    ) -> dict[str, Any]:
        return self._request(
            "POST",
            "/api/v1/setup/administrator",
            authenticated=False,
            json=payload,
        )

    def login(self, identifier: str, password: str) -> AuthenticatedUser:
        data = self._request(
            "POST", "/api/v1/auth/login", authenticated=False,
            json={"identifier": identifier, "password": password},
        )
        self._access_token = data["access_token"]
        self._refresh_token = data["refresh_token"]
        claims = jwt.decode(self._access_token, options={"verify_signature": False})
        profile = self._request("GET", "/api/v1/auth/me")
        return AuthenticatedUser(
            int(claims["sub"]), profile["nome"], profile["perfil"],
            bool(data.get("must_change_password", profile.get("must_change_password", False))),
            data.get("personal_recovery_key"),
        )

    def complete_password_change(self, new_password: str) -> PasswordChangeCompletion:
        data = self._request(
            "POST", "/api/v1/auth/complete-password-change",
            json={"new_password": new_password},
        )
        self._access_token = data["access_token"]
        self._refresh_token = data["refresh_token"]
        claims = jwt.decode(self._access_token, options={"verify_signature": False})
        profile = self._request("GET", "/api/v1/auth/me")
        return PasswordChangeCompletion(
            AuthenticatedUser(
                int(claims["sub"]), profile["nome"], profile["perfil"], False
            ),
            data["personal_recovery_key"],
        )

    def change_password(self, current_password: str, new_password: str) -> None:
        self._request(
            "POST",
            "/api/v1/auth/change-password",
            json={
                "current_password": current_password,
                "new_password": new_password,
            },
        )

    def complete_personal_recovery(
        self, identifier: str, recovery_key: str, new_password: str
    ) -> None:
        self._request(
            "POST",
            "/api/v1/auth/personal-recovery",
            authenticated=False,
            json={
                "identifier": identifier,
                "recovery_key": recovery_key,
                "new_password": new_password,
            },
        )

    def logout(self) -> None:
        try:
            if self._access_token and self._refresh_token:
                self._request("POST", "/api/v1/auth/logout", json={"refresh_token": self._refresh_token})
        finally:
            self._access_token = None
            self._refresh_token = None

    def forgot_password(self, email: str) -> str:
        result = self._request("POST", "/api/v1/auth/forgot-password", authenticated=False,
                               json={"email": email})
        return result["message"]

    def create_assisted_recovery_request(self, identifier: str) -> dict[str, Any]:
        return self._request(
            "POST",
            "/api/v1/auth/assisted-recovery/request",
            authenticated=False,
            json={"identifier": identifier},
        )

    def validate_assisted_recovery(self, authorization: str) -> None:
        self._request(
            "POST",
            "/api/v1/auth/assisted-recovery/validate",
            authenticated=False,
            json={"authorization": authorization},
        )

    def complete_assisted_recovery(
        self, authorization: str, new_password: str
    ) -> None:
        self._request(
            "POST",
            "/api/v1/auth/assisted-recovery/complete",
            authenticated=False,
            json={"authorization": authorization, "new_password": new_password},
        )

    def get(self, path: str) -> Any:
        return self._request("GET", path)

    def post(self, path: str, payload: dict[str, Any]) -> Any:
        return self._request("POST", path, json=payload)

    def patch(self, path: str, payload: dict[str, Any]) -> Any:
        return self._request("PATCH", path, json=payload)

    def put(self, path: str, payload: dict[str, Any]) -> Any:
        return self._request("PUT", path, json=payload)

    def get_ranking_parameters(self, year: int) -> dict[str, Any] | None:
        return self._request(
            "GET", f"/api/v1/ranking/parameters/{year}", _allow_not_found=True
        )

    def save_ranking_parameters(
        self, year: int, payload: dict[str, Any]
    ) -> dict[str, Any]:
        return self.put(f"/api/v1/ranking/parameters/{year}", payload)

    def list_users(self) -> list[dict[str, Any]]:
        return self.get("/api/v1/users")

    def create_user(self, payload: dict[str, Any]) -> dict[str, Any]:
        return self.post("/api/v1/users", payload)

    def update_user(self, user_id: int, payload: dict[str, Any]) -> dict[str, Any]:
        return self.patch(f"/api/v1/users/{user_id}", payload)

    def reset_user_password(self, user_id: int, temporary_password: str) -> None:
        self.post(
            f"/api/v1/users/{user_id}/reset-password",
            {"temporary_password": temporary_password},
        )

    def upload(self, path: str, file_path: str, *, import_file: bool = False) -> Any:
        # Importações são atômicas no servidor e podem continuar após o cliente
        # desistir. O read timeout maior é exclusivo deste fluxo; conexão e pool
        # continuam com limites curtos para detectar indisponibilidade real.
        timeout = (
            httpx.Timeout(connect=10.0, read=900.0, write=120.0, pool=10.0)
            if import_file else
            httpx.Timeout(connect=10.0, read=120.0, write=120.0, pool=10.0)
        )
        with open(file_path, "rb") as handle:
            return self._request(
                "POST", path,
                files={"file": (file_path.rsplit("/", 1)[-1].rsplit("\\", 1)[-1], handle)},
                data={"import_file": str(import_file).lower()},
                timeout=timeout,
                _timeout_message=(
                    "A importação está demorando mais que o esperado. "
                    "Verifique o resultado antes de tentar novamente."
                    if import_file else None
                ),
            )

    def download(self, path: str, payload: dict[str, Any]) -> bytes:
        headers = {"Authorization": f"Bearer {self._access_token}"} if self._access_token else {}
        try:
            response = self._client.post(path, headers=headers, json=payload)
        except httpx.ReadTimeout as error:
            raise APIReadTimeoutError(
                "A operação excedeu o tempo limite de resposta."
            ) from error
        except httpx.RequestError as error:
            raise APIConnectionError(
                "Servidor Finance indisponível. Verifique a conexão e tente novamente."
            ) from error
        if response.is_error:
            try:
                detail = response.json().get("detail")
            except ValueError:
                detail = None
            raise RuntimeError(detail or "Não foi possível concluir a operação.")
        return response.content

    def _request(self, method: str, path: str, *, authenticated: bool = True,
                 _allow_refresh: bool = True,
                 _allow_not_found: bool = False,
                 _timeout_message: str | None = None, **kwargs: Any) -> Any:
        headers = dict(kwargs.pop("headers", {}))
        if authenticated and self._access_token:
            headers["Authorization"] = f"Bearer {self._access_token}"
        try:
            response = self._client.request(method, path, headers=headers, **kwargs)
        except httpx.ReadTimeout as error:
            raise APIReadTimeoutError(
                _timeout_message or "A operação excedeu o tempo limite de resposta."
            ) from error
        except httpx.RequestError as error:
            raise APIConnectionError(
                "Servidor Finance indisponível. Verifique a conexão e tente novamente."
            ) from error
        if (response.status_code == 401 and authenticated and _allow_refresh
                and self._refresh_token and path != "/api/v1/auth/refresh"):
            refreshed = self._request(
                "POST", "/api/v1/auth/refresh", authenticated=False,
                _allow_refresh=False, json={"refresh_token": self._refresh_token},
            )
            self._access_token = refreshed["access_token"]
            self._refresh_token = refreshed["refresh_token"]
            return self._request(
                method, path, authenticated=True, _allow_refresh=False,
                _allow_not_found=_allow_not_found,
                _timeout_message=_timeout_message, **kwargs
            )
        if response.status_code == 401:
            raise AuthenticationError("Usuário ou senha inválidos, ou sessão expirada.")
        if response.status_code == 404 and _allow_not_found:
            return None
        if response.is_error:
            try:
                detail = response.json().get("detail")
            except ValueError:
                detail = None
            raise RuntimeError(detail or "Não foi possível concluir a operação.")
        return None if response.status_code == 204 else response.json()

    def close(self) -> None:
        self._client.close()
