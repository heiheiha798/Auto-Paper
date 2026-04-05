from __future__ import annotations

import ast
from dataclasses import dataclass
from pathlib import Path
from typing import Any

try:  # pragma: no cover - Python 3.11+
    import tomllib  # type: ignore[attr-defined]
except ImportError:  # pragma: no cover - Python 3.10 fallback
    tomllib = None


@dataclass(slots=True)
class AutoPaperConfig:
    raw: dict[str, Any]
    path: Path

    @property
    def arxiv(self) -> dict[str, Any]:
        return self.raw["arxiv"]

    @property
    def digest(self) -> dict[str, Any]:
        return self.raw["digest"]

    @property
    def llm(self) -> dict[str, Any]:
        return self.raw.get("llm", {})

    @property
    def focus(self) -> dict[str, Any]:
        return self.raw.get("focus", {})

    @property
    def run(self) -> dict[str, Any]:
        return self.raw.get("run", {})


def load_config(path: str | Path | None = None) -> AutoPaperConfig:
    if path is None:
        path = Path(__file__).resolve().parents[1] / "configs" / "default.toml"
    else:
        path = Path(path)
    if tomllib is not None:
        with path.open("rb") as handle:
            data = tomllib.load(handle)
    else:
        data = _load_minimal_toml(path.read_text(encoding="utf-8"))
    return AutoPaperConfig(raw=data, path=path)


def _load_minimal_toml(text: str) -> dict[str, Any]:
    data: dict[str, Any] = {}
    current: dict[str, Any] = data
    for raw_line in text.splitlines():
        line = raw_line.strip()
        if not line or line.startswith("#"):
            continue
        if line.startswith("[") and line.endswith("]"):
            section = line[1:-1].strip()
            if not section:
                raise ValueError("Empty TOML section name")
            current = data.setdefault(section, {})
            if not isinstance(current, dict):
                raise ValueError(f"Invalid TOML section: {section}")
            continue
        if "=" not in line:
            raise ValueError(f"Invalid TOML line: {raw_line!r}")
        key, raw_value = line.split("=", 1)
        current[key.strip()] = _parse_minimal_toml_value(raw_value.strip())
    return data


def _parse_minimal_toml_value(raw: str) -> Any:
    lowered = raw.lower()
    if lowered == "true":
        return True
    if lowered == "false":
        return False
    if lowered == "none" or lowered == "null":
        return None
    try:
        return ast.literal_eval(raw)
    except Exception:
        return raw
