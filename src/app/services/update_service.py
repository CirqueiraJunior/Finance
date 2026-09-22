from __future__ import annotations

from dataclasses import dataclass
from enum import StrEnum

import httpx
from packaging.version import InvalidVersion, Version

from app.core.version import __version__


LATEST_RELEASE_URL = (
    "https://api.github.com/repos/CirqueiraJunior/"
    "JA-Technology-Releases/releases?per_page=100"
)
PRODUCT_TAG_PREFIX = "finance-v"


class UpdateStatus(StrEnum):
    UP_TO_DATE = "UP_TO_DATE"
    UPDATE_AVAILABLE = "UPDATE_AVAILABLE"
    INSTALLED_NEWER = "INSTALLED_NEWER"


@dataclass(frozen=True, slots=True)
class UpdateCheckResult:
    status: UpdateStatus
    installed_version: str
    available_version: str
    release_url: str | None = None


class UpdateCheckUnavailableError(RuntimeError):
    """Raised when the official release cannot be consulted safely."""


class UpdateService:
    def __init__(
        self,
        *,
        endpoint: str = LATEST_RELEASE_URL,
        timeout: float = 5.0,
        transport: httpx.BaseTransport | None = None,
    ) -> None:
        self.endpoint = endpoint
        self.timeout = timeout
        self.transport = transport

    def check(self) -> UpdateCheckResult:
        installed = self._parse_version(__version__)
        try:
            with httpx.Client(
                timeout=self.timeout,
                transport=self.transport,
                headers={
                    "Accept": "application/vnd.github+json",
                    "User-Agent": f"J.A.-Finance/{__version__}",
                },
            ) as client:
                response = client.get(self.endpoint)
        except httpx.RequestError as error:
            raise UpdateCheckUnavailableError(
                "Não foi possível consultar atualizações no momento."
            ) from error

        if response.status_code != httpx.codes.OK:
            raise UpdateCheckUnavailableError(
                "Não foi possível consultar atualizações no momento."
            )

        try:
            payload = response.json()
        except ValueError as error:
            raise UpdateCheckUnavailableError(
                "Não foi possível consultar atualizações no momento."
            ) from error

        release = self._select_finance_release(payload)
        if release is None:
            raise UpdateCheckUnavailableError(
                "Não foi possível consultar atualizações no momento."
            )

        available = self._version_from_tag(release["tag_name"])
        release_url = release.get("html_url")
        if not isinstance(release_url, str):
            release_url = None

        if installed < available:
            status = UpdateStatus.UPDATE_AVAILABLE
        elif installed > available:
            status = UpdateStatus.INSTALLED_NEWER
        else:
            status = UpdateStatus.UP_TO_DATE
        return UpdateCheckResult(
            status=status,
            installed_version=str(installed),
            available_version=str(available),
            release_url=release_url,
        )

    @classmethod
    def _select_finance_release(cls, payload: object) -> dict | None:
        if not isinstance(payload, list):
            return None

        candidates: list[tuple[Version, dict]] = []
        for release in payload:
            if not isinstance(release, dict):
                continue
            if release.get("draft") is True or release.get("prerelease") is True:
                continue
            tag_name = release.get("tag_name")
            if not isinstance(tag_name, str) or not tag_name.startswith(
                PRODUCT_TAG_PREFIX
            ):
                continue
            try:
                version = cls._version_from_tag(tag_name)
            except UpdateCheckUnavailableError:
                continue
            candidates.append((version, release))

        if not candidates:
            return None
        return max(candidates, key=lambda candidate: candidate[0])[1]

    @classmethod
    def _version_from_tag(cls, tag_name: str) -> Version:
        return cls._parse_version(tag_name[len(PRODUCT_TAG_PREFIX):])

    @staticmethod
    def _parse_version(value: str) -> Version:
        normalized = value.strip()
        if normalized[:1].lower() == "v":
            normalized = normalized[1:]
        try:
            return Version(normalized)
        except InvalidVersion as error:
            raise UpdateCheckUnavailableError(
                "Não foi possível consultar atualizações no momento."
            ) from error
