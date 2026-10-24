from app.importers.workbook_sheet_detector import detect_sheet


def test_financeiro_accepts_legacy_sheet_name():
    result = detect_sheet(["Orçado", "Lançamentos"], "FINANCEIRO")
    assert result.status == "FOUND"
    assert result.sheet_name == "Lançamentos"


def test_financeiro_accepts_standard_name():
    result = detect_sheet(["Financeiro"], "FINANCEIRO")
    assert result.sheet_name == "Financeiro"


def test_budget_accepts_legacy_name():
    result = detect_sheet(["Lançamentos", "Orçado"], "ORCAMENTO")
    assert result.sheet_name == "Orçado"


def test_boe_accepts_existing_official_name():
    result = detect_sheet(["Taxa BOE"], "BOE")
    assert result.sheet_name == "Taxa BOE"


def test_case_and_accents_are_normalized():
    result = detect_sheet(["  lançamentos  "], "financeiro")
    assert result.status == "FOUND"


def test_missing_sheet_is_reported():
    result = detect_sheet(["Resumo"], "FINANCEIRO")
    assert result.status == "NOT_FOUND"


def test_ambiguous_sheets_are_blocked():
    result = detect_sheet(
        ["Financeiro", "Lançamentos"], "FINANCEIRO"
    )
    assert result.status == "AMBIGUOUS"
    assert len(result.candidates) == 2


def test_unknown_module_is_rejected():
    try:
        detect_sheet(["Dados"], "DESCONHECIDO")
    except ValueError:
        pass
    else:
        raise AssertionError("Modulo desconhecido aceito")
