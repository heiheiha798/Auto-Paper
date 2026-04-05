from __future__ import annotations

from dataclasses import dataclass
import re
from pathlib import Path

from manifest import build_source_manifest
from models import SourceManifest
from utils import make_preview, read_text


@dataclass(slots=True)
class AbstractExtraction:
    text: str
    source_path: str | None
    source_kind: str
    confidence: float


ABSTRACT_ENV_RE = re.compile(r"\\begin\{abstract\}(.*?)\\end\{abstract\}", re.IGNORECASE | re.DOTALL)
ABSTRACT_SECTION_RE = re.compile(
    r"\\section\*?\{abstract\}(.*?)(?=\\section\*?\{|\\begin\{keywords?\}|\\maketitle|\\end\{document\}|$)",
    re.IGNORECASE | re.DOTALL,
)
PLAIN_ABSTRACT_RE = re.compile(r"(?im)^\s*abstract\s*[:.\-]?\s*(.+)$")


def extract_abstract_text(
    source_dir: str | Path,
    manifest: SourceManifest | None = None,
    fallback_text: str = "",
) -> AbstractExtraction:
    source_dir = Path(source_dir)
    manifest = manifest or build_source_manifest(source_dir)

    candidates = sorted(
        manifest.files,
        key=_candidate_score,
        reverse=True,
    )
    for item in candidates:
        if not item.is_text:
            continue
        path = source_dir / item.path
        if not path.exists() or not path.is_file():
            continue
        text = read_text(path, limit=20000)
        extraction = _extract_from_text(text)
        if extraction is not None:
            cleaned = _clean_abstract(extraction)
            if cleaned:
                return AbstractExtraction(
                    text=cleaned,
                    source_path=item.path,
                    source_kind=_source_kind(item.path, text),
                    confidence=_confidence(item.path, text),
                )

    cleaned_fallback = _clean_abstract(fallback_text)
    return AbstractExtraction(
        text=cleaned_fallback,
        source_path=None,
        source_kind="metadata" if cleaned_fallback else "missing",
        confidence=0.2 if cleaned_fallback else 0.0,
    )


def _candidate_score(item) -> int:
    score = 0
    lower_path = item.path.lower()
    if "abstract" in lower_path:
        score += 5
    if item.suffix == ".tex":
        score += 3
    if item.suffix == ".txt":
        score += 2
    if item.has_documentclass:
        score += 2
    if item.has_include or item.has_input:
        score += 1
    return score


def _extract_from_text(text: str) -> str | None:
    for pattern in (ABSTRACT_ENV_RE, ABSTRACT_SECTION_RE):
        match = pattern.search(text)
        if match:
            return match.group(1)

    match = PLAIN_ABSTRACT_RE.search(text)
    if match:
        return match.group(1)

    if "abstract" in text.lower() and len(text) < 5000:
        return text
    return None


def _clean_abstract(text: str) -> str:
    text = re.sub(r"%.*$", "", text, flags=re.MULTILINE)
    text = re.sub(r"\\cite\{[^}]*\}", "", text)
    text = re.sub(r"\\ref\{[^}]*\}", "", text)
    text = re.sub(r"\\label\{[^}]*\}", "", text)
    text = re.sub(r"\\[a-zA-Z]+\*?(?:\[[^\]]*\])?\{([^{}]*)\}", r"\1", text)
    text = re.sub(r"\\[a-zA-Z]+\*?", "", text)
    text = re.sub(r"\s+", " ", text).strip()
    return text


def _source_kind(path: str, text: str) -> str:
    lower_path = path.lower()
    if lower_path.endswith(".txt"):
        return "text-file"
    if "abstract" in lower_path:
        return "abstract-file"
    if "\\begin{abstract}" in text:
        return "tex-abstract"
    return "tex"


def _confidence(path: str, text: str) -> float:
    lower_path = path.lower()
    if "abstract" in lower_path:
        return 0.95
    if "\\begin{abstract}" in text:
        return 0.85
    if lower_path.endswith(".txt"):
        return 0.75
    return 0.6


def render_abstract_snippet(extraction: AbstractExtraction, limit: int = 400) -> str:
    preview = make_preview(extraction.text, limit=limit)
    if not preview:
        return "(no abstract text found)"
    return preview
