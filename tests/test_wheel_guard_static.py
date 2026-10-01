from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SRC = ROOT / "src" / "app"


def test_no_raw_wheel_sensitive_constructors_remain():
    patterns = (
        "QComboBox(",
        "QSpinBox(",
        "QDoubleSpinBox(",
        "QDateEdit(",
        "QTabWidget(",
    )

    hits = []

    for path in SRC.rglob("*.py"):
        if path.name == "wheel_guard.py":
            continue

        text = path.read_text(encoding="utf-8")

        for pattern in patterns:
            if pattern in text:
                hits.append(f"{path.relative_to(ROOT)} -> {pattern}")

    assert not hits, "\n".join(hits)


def test_custom_widgets_use_protected_bases():
    expected = {
        SRC / "widgets" / "month_combo.py":
            "class MonthComboBox(WheelBlockedComboBox):",
        SRC / "gui" / "pages" / "metas.py":
            "class EntityMultiSelectCombo(WheelBlockedComboBox):",
        SRC / "gui" / "pages" / "boe.py":
            "class BOEPeriodEdit(WheelBlockedDateEdit):",
    }

    missing = []

    for path, fragment in expected.items():
        if fragment not in path.read_text(encoding="utf-8"):
            missing.append(f"{path.relative_to(ROOT)} -> {fragment}")

    assert not missing, "\n".join(missing)
