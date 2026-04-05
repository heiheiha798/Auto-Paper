from __future__ import annotations

from collections import deque
from pathlib import Path

from models import ExtractedDocument, RoutingDecision, SourceManifest
from utils import extract_tex_includes, unique_preserve_order
from utils import read_text


def extract_selected_text(
    manifest: SourceManifest,
    routing: RoutingDecision,
) -> ExtractedDocument:
    source_dir = manifest.source_dir
    selected_paths = unique_preserve_order(routing.main_files + routing.supporting_files)
    selected_set = set(selected_paths)
    provenance: list[str] = []
    text_parts: list[str] = []

    file_map = {f.path: f for f in manifest.files}
    queue: deque[str] = deque(selected_paths)
    while queue:
        rel_path = queue.popleft()
        if rel_path in provenance:
            continue
        info = file_map.get(rel_path)
        if info is None:
            continue
        path = source_dir / rel_path
        if not path.exists() or not path.is_file():
            continue
        if not info.is_text:
            continue
        content = read_text(path)
        provenance.append(rel_path)
        text_parts.append(f"\n\n[FILE: {rel_path}]\n{content}")

        for include_name in extract_tex_includes(content):
            candidate = _resolve_include(source_dir, rel_path, include_name, file_map)
            if candidate and candidate not in selected_set:
                selected_set.add(candidate)
                queue.append(candidate)

    paper_id = source_dir.name
    return ExtractedDocument(
        paper_id=paper_id,
        text="\n".join(text_parts).strip(),
        provenance=provenance,
        source_dir=source_dir,
    )


def _resolve_include(
    source_dir: Path,
    current_rel_path: str,
    include_name: str,
    file_map: dict[str, object],
) -> str | None:
    include_path = Path(include_name)
    candidates = [include_path]
    if not include_path.suffix:
        candidates.extend(
            [
                include_path.with_suffix(".tex"),
                include_path.with_suffix(".txt"),
                include_path.with_suffix(".md"),
            ]
        )

    current_dir = Path(current_rel_path).parent
    for candidate in candidates:
        rel_candidate = str((current_dir / candidate).as_posix())
        if rel_candidate in file_map:
            return rel_candidate
        if candidate.as_posix() in file_map:
            return candidate.as_posix()
        for base in (source_dir / current_dir, source_dir):
            absolute_candidate = base / candidate
            if absolute_candidate.exists() and absolute_candidate.is_file():
                try:
                    return str(absolute_candidate.relative_to(source_dir))
                except ValueError:
                    continue
    return None
