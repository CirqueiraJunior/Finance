"""Cliente da API; credenciais e tokens nunca são persistidos localmente."""

from dataclasses import dataclass
from typing import Any

import httpx
import jwt


class APIConnectionError(RuntimeError):
    pass


class AuthenticationError(RuntimeError):
    pass


@dataclass(frozen=True, slots=True)
class AuthenticatedUser:
    user_id: int
    nome: str
    perfil: str


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

    def login(self, identifier: str, password: str) -> AuthenticatedUser:
        data = self._request(
            "POST", "/api/v1/auth/login", authenticated=False,
            json={"identifier": identifier, "password": password},
        )
        self._access_token = data["access_token"]
        self._refresh_token = data["refresh_token"]
        claims = jwt.decode(self._access_token, options={"verify_signature": False})
        profile = self._request("GET", "/api/v1/auth/me")
        return AuthenticatedUser(int(claims["sub"]), profile["nome"], profile["perfil"])

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

    def get(self, path: str) -> Any:
        return self._request("GET", path)

    def post(self, path: str, payload: dict[str, Any]) -> Any:
        return self._request("POST", path, json=payload)

    def patch(self, path: str, payload: dict[str, Any]) -> Any:
        return self._request("PATCH", path, json=payload)

    def upload(self, path: str, file_path: str, *, import_file: bool = False) -> Any:
        with open(file_path, "rb") as handle:
            return self._request(
                "POST", path,
                files={"file": (file_path.rsplit("/", 1)[-1].rsplit("\\", 1)[-1], handle)},
                data={"import_file": str(import_file).lower()},
                timeout=120.0,
            )

    def download(self, path: str, payload: dict[str, Any]) -> bytes:
        headers = {"Authorization": f"Bearer {self._access_token}"} if self._access_token else {}
        try:
            response = self._client.post(path, headers=headers, json=payload)
        except httpx.RequestError as error:
            raise APIConnectionError("Servidor Finance indisponível. Verifique a rede e tente novamente.") from error
        if response.is_error:
            try:
                detail = response.json().get("detail")
            except ValueError:
                detail = None
            raise RuntimeError(detail or "Não foi possível concluir a operação.")
        return response.content

    def _request(self, method: str, path: str, *, authenticated: bool = True,
                 _allow_refresh: bool = True, **kwargs: Any) -> Any:
        headers = dict(kwargs.pop("headers", {}))
        if authenticated and self._access_token:
            headers["Authorization"] = f"Bearer {self._access_token}"
        try:
            response = self._client.request(method, path, headers=headers, **kwargs)
        except httpx.RequestError as error:
            raise APIConnectionError("Servidor Finance indisponível. Verifique a rede e tente novamente.") from error
        if (response.status_code == 401 and authenticated and _allow_refresh
                and self._refresh_token and path != "/api/v1/auth/refresh"):
            refreshed = self._request(
                "POST", "/api/v1/auth/refresh", authenticated=False,
                _allow_refresh=False, json={"refresh_token": self._refresh_token},
            )
            self._access_token = refreshed["access_token"]
            self._refresh_token = refreshed["refresh_token"]
            return self._request(method, path, authenticated=True, _allow_refresh=False, **kwargs)
        if response.status_code == 401:
            raise AuthenticationError("Usuário ou senha inválidos, ou sessão expirada.")
        if response.is_error:
            try:
                detail = response.json().get("detail")
            except ValueError:
                detail = None
            raise RuntimeError(detail or "Não foi possível concluir a operação.")
        return None if response.status_code == 204 else response.json()

    def close(self) -> None:
        self._client.close()
