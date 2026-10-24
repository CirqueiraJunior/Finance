"""Identify workbook sheets by module and approved aliases."""

from __future__ import annotations

from dataclasses import dataclass
import unicodedata


SHEET_ALIASES = {
    "FINANCEIRO": ("FINANCEIRO", "LANCAMENTOS"),
    "ORCAMENTO": ("ORCAMENTO", "ORCADO"),
    "BOE": ("BOE", "TAXA BOE"),
    "METAS": ("METAS",),
}


def normalize_sheet_name(value: object) -> str:
    text = unicodedata.normalize("NFKD", str(value or ""))
    text = "".join(
        character
        for character in text
        if not unicodedata.combining(character)
    )
    return " ".join(text.upper().split())


@dataclass(frozen=True)
class SheetDetection:
    module: str
    sheet_name: str | None
    status: str
    candidates: tuple[str, ...] = ()


def detect_sheet(
    sheet_names: list[str] | tuple[str, ...],
    module: str,
) -> SheetDetection:
    key = normalize_sheet_name(module)
    if key not in SHEET_ALIASES:
        raise ValueError("Modulo de importacao desconhecido.")

    aliases = set(SHEET_ALIASES[key])
    found = tuple(
        name
        for name in sheet_names
        if normalize_sheet_name(name) in aliases
    )

    if not found:
        return SheetDetection(key, None, "NOT_FOUND")

    if len(found) > 1:
        return SheetDetection(key, None, "AMBIGUOUS", found)

    return SheetDetection(key, found[0], "FOUND", found)
