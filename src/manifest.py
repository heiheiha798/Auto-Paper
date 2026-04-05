from __future__ import annotations

from pathlib import Path

from models import SourceFileInfo, SourceManifest
from utils import (
    extract_tex_hints,
    extract_tex_includes,
    is_probably_text_file,
    is_skippable_file,
    make_preview,
    read_text,
)


def build_source_manifest(source_dir: str | Path) -> SourceManifest:
    source_dir = Path(source_dir)
    files: list[SourceFileInfo] = []
    for path in sorted(source_dir.rglob("*")):
        if not path.is_file():
            continue
        if is_skippable_file(path):
            continue
        is_text = is_probably_text_file(path)
        preview = ""
        has_documentclass = False
        has_input = False
        has_include = False
        include_targets: list[str] = []
        if is_text:
            text = read_text(path, limit=4000)
            preview = make_preview(text)
            has_documentclass, has_input, has_include = extract_tex_hints(text)
            include_targets = extract_tex_includes(text)
        files.append(
            SourceFileInfo(
                path=str(path.relative_to(source_dir)),
                suffix=path.suffix.lower(),
                size=path.stat().st_size,
                preview=preview,
                has_documentclass=has_documentclass,
                has_input=has_input,
                has_include=has_include,
                include_targets=include_targets if is_text else [],
                is_text=is_text,
            )
        )
    return SourceManifest(source_dir=source_dir, files=files)
