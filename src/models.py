from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path
from typing import Any


@dataclass(slots=True)
class ArxivPaper:
    arxiv_id: str
    version: int
    title: str
    summary: str
    published: str
    updated: str
    primary_category: str
    categories: list[str]
    authors: list[str]
    link: str
    source_url: str | None = None
    pdf_url: str | None = None
    venue_hint: str | None = None
    raw: dict[str, Any] = field(default_factory=dict)

    @property
    def id_version(self) -> str:
        return f"{self.arxiv_id}v{self.version}"


@dataclass(slots=True)
class SourceFileInfo:
    path: str
    suffix: str
    size: int
    preview: str = ""
    has_documentclass: bool = False
    has_input: bool = False
    has_include: bool = False
    include_targets: list[str] = field(default_factory=list)
    is_text: bool = False


@dataclass(slots=True)
class SourceManifest:
    source_dir: Path
    files: list[SourceFileInfo]


@dataclass(slots=True)
class RoutingDecision:
    main_files: list[str] = field(default_factory=list)
    supporting_files: list[str] = field(default_factory=list)
    ignore_files: list[str] = field(default_factory=list)
    confidence: float = 0.0
    reasoning_tags: list[str] = field(default_factory=list)
    needs_second_pass: bool = False
    why_not_confident: str = ""


@dataclass(slots=True)
class ExtractedDocument:
    paper_id: str
    text: str
    provenance: list[str]
    source_dir: Path


@dataclass(slots=True)
class ScreeningResult:
    selected_for_full_read: bool
    screening_score: int
    confidence: float
    reason: str
    risk_flags: list[str] = field(default_factory=list)


@dataclass(slots=True)
class TriageResult:
    relevance_score: int
    infra_fit_score: int
    venue_fit_score: int
    technical_substance_score: int
    evidence_quality_score: int
    overall_score: int
    decision: str
    confidence: float
    risk_flags: list[str] = field(default_factory=list)
    reason: str = ""


@dataclass(slots=True)
class SummaryResult:
    one_sentence_summary: str
    background: str
    motivation: str
    method: str
    evaluation: str
    results: str
    baseline: str
    novelty: str
    limitations: str
    quote_or_evidence: str


@dataclass(slots=True)
class DigestEntry:
    paper_id: str
    title: str
    venue_hint: str | None
    triage: TriageResult
    summary: SummaryResult
    source_files: list[str] = field(default_factory=list)


@dataclass(slots=True)
class DigestReport:
    date: str
    category: str
    total_fetched: int
    total_routed: int
    total_skipped: int
    entries: list[DigestEntry]


@dataclass(slots=True)
class PaperRunResult:
    paper: ArxivPaper
    status: str
    reason: str = ""
    source_dir: Path | None = None
    paper_dir: Path | None = None
    metadata_path: Path | None = None
    abstract_path: Path | None = None
    source_archive_path: Path | None = None
    source_extract_dir: Path | None = None
    manifest_path: Path | None = None
    screening_path: Path | None = None
    review_path: Path | None = None
    queue_path: Path | None = None
    manifest: SourceManifest | None = None
    screening: ScreeningResult | None = None
    routing: RoutingDecision | None = None
    extracted: ExtractedDocument | None = None
    summary: SummaryResult | None = None
    triage: TriageResult | None = None
    artifact_dir: Path | None = None


@dataclass(slots=True)
class WorkflowResult:
    date: str
    query: str
    run_dir: Path
    fetched_papers: list[ArxivPaper] = field(default_factory=list)
    runs: list[PaperRunResult] = field(default_factory=list)
    screening_queue_path: Path | None = None
    queue_path: Path | None = None
    review_template_path: Path | None = None
    digest_path: Path | None = None
