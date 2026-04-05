from __future__ import annotations

import json
import re
from pathlib import Path
from typing import Any


TEXT_SUFFIXES = {".tex", ".txt", ".md", ".sty", ".cls", ".bib", ".bbl"}
SKIP_SUFFIXES = {
    ".pdf",
    ".png",
    ".jpg",
    ".jpeg",
    ".svg",
    ".ivenn",
    ".aux",
    ".blg",
    ".out",
    ".log",
    ".synctex.gz",
    ".fdb_latexmk",
    ".fls",
}


def read_text(path: Path, limit: int | None = None) -> str:
    data = path.read_text(encoding="utf-8", errors="ignore")
    if limit is not None and len(data) > limit:
        return data[:limit]
    return data


def is_probably_text_file(path: Path) -> bool:
    suffix = "".join(path.suffixes[-2:]) if path.name.endswith(".synctex.gz") else path.suffix
    return suffix in TEXT_SUFFIXES or path.name == "README"


def is_skippable_file(path: Path) -> bool:
    suffix = "".join(path.suffixes[-2:]) if path.name.endswith(".synctex.gz") else path.suffix
    return suffix in SKIP_SUFFIXES


def make_preview(text: str, limit: int = 240) -> str:
    cleaned = re.sub(r"\s+", " ", text).strip()
    return cleaned[:limit]


def extract_tex_hints(text: str) -> tuple[bool, bool, bool]:
    return (
        "\\documentclass" in text,
        "\\input" in text,
        "\\include" in text,
    )


TEX_INCLUDE_RE = re.compile(r"\\(?:input|include)\{([^}]+)\}")


def extract_tex_includes(text: str) -> list[str]:
    includes: list[str] = []
    for raw_include in TEX_INCLUDE_RE.findall(text):
        include = raw_include.strip()
        if include:
            includes.append(include)
    return includes


def unique_preserve_order(items: list[str]) -> list[str]:
    seen: set[str] = set()
    deduped: list[str] = []
    for item in items:
        if item in seen:
            continue
        seen.add(item)
        deduped.append(item)
    return deduped


def json_dumps(obj: Any) -> str:
    return json.dumps(obj, ensure_ascii=True, indent=2, sort_keys=True)


def safe_slug(text: str) -> str:
    text = text.lower().strip()
    text = re.sub(r"[^a-z0-9]+", "-", text)
    text = re.sub(r"-+", "-", text).strip("-")
    return text or "item"
