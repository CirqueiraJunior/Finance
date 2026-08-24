from pathlib import Path


def load_stylesheet() -> str:
    path = Path(__file__).parent / "styles" / "base.qss"
    return path.read_text(encoding="utf-8")

