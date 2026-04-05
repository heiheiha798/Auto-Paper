from __future__ import annotations

import asyncio
from dataclasses import asdict
from datetime import date, datetime, timedelta, timezone
import json
from pathlib import Path
from zoneinfo import ZoneInfo

from abstracts import extract_abstract_text
from arxiv_client import ArxivClient
from digest import render_digest, write_digest
from manifest import build_source_manifest
from models import (
    ArxivPaper,
    DigestEntry,
    DigestReport,
    ExtractedDocument,
    PaperRunResult,
    RoutingDecision,
    ScreeningResult,
    SourceManifest,
    SummaryResult,
    TriageResult,
    WorkflowResult,
)
from router import ROUTER_SYSTEM_PROMPT, build_router_payload
from source_fetch import download_and_extract_source
from triage import score_triage
from utils import json_dumps


def build_run_date(now_tz: str, explicit_date: str | None = None) -> str:
    if explicit_date:
        return explicit_date
    tz = ZoneInfo(now_tz)
    return datetime.now(tz).date().isoformat()


def build_date_window_query(base_query: str, run_date: str, timezone_name: str, window_days: int = 1) -> str:
    tz = ZoneInfo(timezone_name)
    day = date.fromisoformat(run_date)
    start_local = datetime.combine(day, datetime.min.time(), tz) - timedelta(days=window_days - 1)
    end_local = datetime.combine(day + timedelta(days=1), datetime.min.time(), tz)
    start_utc = start_local.astimezone(timezone.utc)
    end_utc = end_local.astimezone(timezone.utc)
    return f"({base_query}) AND submittedDate:[{start_utc:%Y%m%d%H%M} TO {end_utc:%Y%m%d%H%M}]"


async def fetch_arxiv_papers(config: dict, run_date: str | None = None) -> list[ArxivPaper]:
    arxiv_cfg = config["arxiv"]
    run_cfg = config.get("run", {})
    tz_name = run_cfg.get("timezone", "UTC")
    window_days = int(run_cfg.get("window_days", 1))
    date_string = build_run_date(tz_name, run_date)
    search_query = build_date_window_query(arxiv_cfg["search_query"], date_string, tz_name, window_days=window_days)

    client = ArxivClient(
        base_url=arxiv_cfg["base_url"],
        timeout=float(arxiv_cfg.get("request_timeout_seconds", 30.0)),
        request_delay=float(arxiv_cfg.get("request_delay_seconds", 3.0)),
        user_agent=arxiv_cfg.get("user_agent", "Auto-Paper/0.1"),
    )
    page_size = int(arxiv_cfg.get("page_size", 50))
    max_results = int(arxiv_cfg.get("max_results", 100))
    papers: list[ArxivPaper] = []
    start = 0

    while len(papers) < max_results:
        page = await client.fetch_feed(
            search_query=search_query,
            max_results=min(page_size, max_results - len(papers)),
            start=start,
            sort_by="submittedDate",
            sort_order="descending",
        )
        if not page:
            break
        papers.extend(page)
        if len(page) < page_size:
            break
        start += page_size
    return papers[:max_results]


def prepare_run(config: dict, run_date: str | None = None) -> WorkflowResult:
    run_cfg = config.get("run", {})
    tz_name = run_cfg.get("timezone", "UTC")
    date_string = build_run_date(tz_name, run_date)
    run_root = Path(run_cfg.get("run_root", "data/runs"))
    run_dir = run_root / date_string
    run_dir.mkdir(parents=True, exist_ok=True)

    papers = asyncio.run(fetch_arxiv_papers(config, run_date=date_string))
    paper_runs: list[PaperRunResult] = []
    paper_payloads: list[dict] = []
    screening_rows: list[dict] = []
    paper_dirs_root = run_dir / "papers"
    paper_dirs_root.mkdir(parents=True, exist_ok=True)

    for paper in papers:
        paper_dir = paper_dirs_root / paper.id_version
        paper_dir.mkdir(parents=True, exist_ok=True)
        metadata_path = paper_dir / "metadata.json"
        paper_payload = _paper_payload(paper)
        metadata_path.write_text(json_dumps(paper_payload), encoding="utf-8")
        abstract_path = paper_dir / "abstract.txt"
        abstract_path.write_text(paper.summary.strip() + "\n", encoding="utf-8")

        run_result = PaperRunResult(
            paper=paper,
            status="fetched",
            source_dir=None,
            paper_dir=paper_dir,
            metadata_path=metadata_path,
            abstract_path=abstract_path,
            artifact_dir=paper_dir,
        )
        paper_runs.append(run_result)
        paper_payloads.append(
            {
                **paper_payload,
                "abstract_path": str(abstract_path.relative_to(run_dir)),
                "abstract": paper.summary,
            }
        )
        screening_rows.append(
            {
                "paper_id": paper.id_version,
                "title": paper.title,
                "summary_path": str(abstract_path.relative_to(run_dir)),
                "abstract": paper.summary,
                "categories": paper.categories,
                "primary_category": paper.primary_category,
                "published": paper.published,
                "updated": paper.updated,
                "authors": paper.authors,
            }
        )

    papers_path = run_dir / "papers.json"
    papers_path.write_text(json_dumps(paper_payloads), encoding="utf-8")

    screening_queue_path = run_dir / "screening_queue.json"
    screening_queue_path.write_text(json_dumps(screening_rows), encoding="utf-8")

    screening_prompt_path = run_dir / "screening_prompt.md"
    screening_prompt_path.write_text(
        _render_screening_prompt(date_string, config, screening_rows),
        encoding="utf-8",
    )

    screening_markdown_path = run_dir / "screening_queue.md"
    screening_markdown_path.write_text(
        _render_screening_queue_markdown(date_string, config, screening_rows),
        encoding="utf-8",
    )

    run_meta_path = run_dir / "run.json"
    run_meta_path.write_text(
        json_dumps(
            {
                "date": date_string,
                "query": search_query,
                "total_fetched": len(papers),
                "run_dir": str(run_dir),
                "screening_queue_path": str(screening_queue_path),
                "screening_prompt_path": str(screening_prompt_path),
                "screening_markdown_path": str(screening_markdown_path),
            }
        ),
        encoding="utf-8",
    )

    return WorkflowResult(
        date=date_string,
        query=search_query,
        run_dir=run_dir,
        fetched_papers=papers,
        runs=paper_runs,
        screening_queue_path=screening_queue_path,
        queue_path=screening_markdown_path,
        review_template_path=screening_prompt_path,
    )


def materialize_selected_papers(
    config: dict,
    run_dir: str | Path,
    screening_decisions_path: str | Path | None = None,
) -> list[PaperRunResult]:
    run_dir = Path(run_dir)
    arxiv_cfg = config["arxiv"]
    source_url_template = arxiv_cfg.get(
        "source_url_template",
        [
            "https://arxiv.org/e-print/{paper_id}",
            "https://arxiv.org/src/{paper_id}",
        ],
    )
    user_agent = arxiv_cfg.get("user_agent", "Auto-Paper/0.1")
    timeout = float(arxiv_cfg.get("source_timeout_seconds", 60.0))
    paper_dir_root = run_dir / "papers"
    papers = _load_papers(run_dir)
    screening = _load_screening_decisions(screening_decisions_path or run_dir / "screening_decisions.json")
    selected_ids = {paper_id for paper_id, decision in screening.items() if decision.selected_for_full_read}

    results: list[PaperRunResult] = []
    for paper in papers:
        paper_dir = paper_dir_root / paper.id_version
        paper_dir.mkdir(parents=True, exist_ok=True)
        paper_result = PaperRunResult(
            paper=paper,
            status="skipped",
            source_dir=None,
            paper_dir=paper_dir,
            artifact_dir=paper_dir,
            metadata_path=paper_dir / "metadata.json",
            abstract_path=paper_dir / "abstract.txt",
        )

        decision = screening.get(paper.id_version)
        if decision is not None:
            paper_result.screening = decision
            paper_result.screening_path = paper_dir / "screening.json"
            paper_result.screening_path.write_text(json_dumps(asdict(decision)), encoding="utf-8")

        if paper.id_version not in selected_ids:
            paper_result.reason = "Not selected during abstract screening."
            results.append(paper_result)
            continue

        try:
            archive_result = download_and_extract_source(
                paper_id=paper.arxiv_id,
                dest_dir=paper_dir,
                source_url_template=source_url_template,
                user_agent=user_agent,
                timeout=timeout,
            )
            source_extract_dir = archive_result.extract_dir
            manifest = build_source_manifest(source_extract_dir)
            manifest_path = paper_dir / "manifest.json"
            manifest_path.write_text(_render_manifest_json(manifest), encoding="utf-8")
            source_abstract = extract_abstract_text(source_extract_dir, manifest=manifest, fallback_text=paper.summary)
            source_abstract_path = paper_dir / "source_abstract.txt"
            source_abstract_path.write_text(source_abstract.text + "\n", encoding="utf-8")
            routing_prompt_path = paper_dir / "routing_prompt.md"
            routing_prompt_path.write_text(
                _render_routing_prompt(paper, manifest, source_abstract.text, config),
                encoding="utf-8",
            )
            paper_result.status = "materialized"
            paper_result.reason = "Source archive downloaded and extracted."
            paper_result.source_archive_path = archive_result.archive_path
            paper_result.source_extract_dir = source_extract_dir
            paper_result.manifest = manifest
            paper_result.manifest_path = manifest_path
            paper_result.queue_path = routing_prompt_path
            results.append(paper_result)
        except Exception as exc:  # pragma: no cover - recorded as artifact
            paper_result.reason = str(exc)
            results.append(paper_result)

    return results


def extract_routed_text(
    run_dir: str | Path,
    routing_decisions_path: str | Path,
) -> list[PaperRunResult]:
    run_dir = Path(run_dir)
    papers = _load_papers(run_dir)
    routing = _load_routing_decisions(routing_decisions_path)
    results: list[PaperRunResult] = []

    for paper in papers:
        paper_dir = run_dir / "papers" / paper.id_version
        if paper.id_version not in routing:
            continue
        decision = routing[paper.id_version]
        manifest_path = paper_dir / "manifest.json"
        if not manifest_path.exists():
            continue
        manifest = _load_manifest_from_json(manifest_path)
        from extract import extract_selected_text

        extracted = extract_selected_text(manifest, decision)
        extracted_path = paper_dir / "extracted.txt"
        extracted_path.write_text(extracted.text + "\n", encoding="utf-8")
        extracted_meta_path = paper_dir / "extracted.json"
        extracted_meta_path.write_text(
            json_dumps(
                {
                    "paper_id": extracted.paper_id,
                    "provenance": extracted.provenance,
                    "source_dir": str(extracted.source_dir),
                    "text_path": str(extracted_path),
                }
            ),
            encoding="utf-8",
        )
        result = PaperRunResult(
            paper=paper,
            status="extracted",
            source_dir=manifest.source_dir,
            paper_dir=paper_dir,
            artifact_dir=paper_dir,
            manifest=manifest,
            manifest_path=manifest_path,
            routing=decision,
            extracted=extracted,
            queue_path=extracted_path,
        )
        results.append(result)
    return results


def build_digest_report(
    run_dir: str | Path,
    reviews_path: str | Path,
    date_string: str,
) -> DigestReport:
    run_dir = Path(run_dir)
    reviews = _load_reviews(reviews_path)
    entries: list[DigestEntry] = []
    for paper_id, review in reviews.items():
        paper = review["paper"]
        triage = TriageResult(**review["triage"])
        summary = SummaryResult(**review["summary"])
        paper_payload = review["paper"]
        if isinstance(paper_payload, str):
            paper_payload = {"title": paper_payload, "venue_hint": None}
        entries.append(
            DigestEntry(
                paper_id=paper_id,
                title=paper_payload["title"],
                venue_hint=paper_payload.get("venue_hint"),
                triage=triage,
                summary=summary,
                source_files=review.get("source_files", []),
            )
        )

    total_fetched = 0
    if (run_dir / "papers.json").exists():
        total_fetched = len(json.loads((run_dir / "papers.json").read_text(encoding="utf-8")))
    total_skipped = sum(1 for entry in entries if entry.triage.decision == "skip")
    total_routed = len(entries)
    return DigestReport(
        date=date_string,
        category=_load_run_query(run_dir),
        total_fetched=total_fetched,
        total_routed=total_routed,
        total_skipped=total_skipped,
        entries=entries,
    )


def render_digest_for_run(
    run_dir: str | Path,
    reviews_path: str | Path,
    date_string: str,
    output_path: str | Path,
) -> Path:
    report = build_digest_report(run_dir, reviews_path, date_string)
    return write_digest(output_path, report)


def write_screening_decisions_template(run_dir: str | Path, output_path: str | Path) -> Path:
    run_dir = Path(run_dir)
    papers = _load_papers(run_dir)
    output_path = Path(output_path)
    output_path.parent.mkdir(parents=True, exist_ok=True)
    decisions = {
        paper.id_version: {
            "selected_for_full_read": False,
            "screening_score": 0,
            "confidence": 0.0,
            "reason": "",
            "risk_flags": [],
        }
        for paper in papers
    }
    output_path.write_text(json_dumps(decisions), encoding="utf-8")
    return output_path


def score_screening_queue(papers: list[ArxivPaper], focus: dict | None = None) -> dict[str, ScreeningResult]:
    focus = focus or {}
    results: dict[str, ScreeningResult] = {}
    for paper in papers:
        text = f"{paper.title}\n{paper.summary}".lower()
        score = 0
        for hint in ["serving", "inference", "runtime", "latency", "throughput", "memory", "edge", "quantization", "speculative decoding", "batching", "scheduler"]:
            if hint in text:
                score += 1
        if any(venue.lower() in text for venue in focus.get("venue_hints", [])):
            score += 1
        selected = score >= 2
        results[paper.id_version] = ScreeningResult(
            selected_for_full_read=selected,
            screening_score=min(6, score),
            confidence=0.5 if selected else 0.3,
            reason="heuristic pre-screen; Codex should override when needed",
            risk_flags=[],
        )
    return results


def build_review_stub(
    paper: ArxivPaper,
    extracted_text: str,
    source_files: list[str],
    focus: dict | None = None,
) -> dict:
    extracted = ExtractedDocument(
        paper_id=paper.id_version,
        text=extracted_text,
        provenance=source_files,
        source_dir=Path("."),
    )
    triage = score_triage(paper, extracted, focus or {})
    summary = _build_summary_stub(paper, extracted_text)
    return {
        "paper": _paper_payload(paper),
        "triage": asdict(triage),
        "summary": asdict(summary),
        "source_files": source_files,
    }


def _paper_screening_payload(paper: ArxivPaper, abstract_path: Path) -> dict:
    return {
        "paper_id": paper.id_version,
        "title": paper.title,
        "authors": paper.authors,
        "categories": paper.categories,
        "primary_category": paper.primary_category,
        "published": paper.published,
        "updated": paper.updated,
        "abstract_path": str(abstract_path),
        "abstract": paper.summary,
        "link": paper.link,
    }


def _paper_payload(paper: ArxivPaper) -> dict:
    return {
        "arxiv_id": paper.arxiv_id,
        "version": paper.version,
        "id_version": paper.id_version,
        "title": paper.title,
        "summary": paper.summary,
        "published": paper.published,
        "updated": paper.updated,
        "primary_category": paper.primary_category,
        "categories": paper.categories,
        "authors": paper.authors,
        "link": paper.link,
        "source_url": paper.source_url,
        "pdf_url": paper.pdf_url,
        "venue_hint": paper.venue_hint,
        "raw": paper.raw,
    }


def _render_screening_prompt(date_string: str, config: dict, rows: list[dict]) -> str:
    lines: list[str] = []
    lines.append(f"# Auto-Paper Screening Prompt - {date_string}")
    lines.append("")
    lines.append("Read the abstracts below and write `screening_decisions.json` in the same run directory.")
    lines.append("Score on a 6-point scale. Select papers for full TeX reading when they are likely relevant.")
    lines.append("Do not apply a hard infra-only filter at retrieval time; use the abstract to decide.")
    lines.append("")
    lines.append("## Selection Focus")
    lines.append(f"- Target: {config.get('focus', {}).get('name', 'AI infra')}")
    lines.append(f"- Venue hints: {', '.join(config.get('focus', {}).get('venue_hints', []))}")
    lines.append("")
    lines.append("## Papers")
    for row in rows:
        lines.append(f"- `{row['paper_id']}` {row['title']}")
        lines.append(f"  - Categories: {', '.join(row['categories'])}")
        lines.append(f"  - Abstract: {row['summary_path']}")
    lines.append("")
    lines.append("## Output Schema")
    lines.append("For each paper, write:")
    lines.append("- `selected_for_full_read`")
    lines.append("- `screening_score` from 0 to 6")
    lines.append("- `confidence` from 0 to 1")
    lines.append("- `reason`")
    lines.append("- `risk_flags`")
    return "\n".join(lines).rstrip() + "\n"


def _render_screening_queue_markdown(date_string: str, config: dict, rows: list[dict]) -> str:
    lines: list[str] = []
    lines.append(f"# Screening Queue - {date_string}")
    lines.append("")
    lines.append(f"- Query: {config['arxiv']['search_query']}")
    lines.append(f"- Total papers: {len(rows)}")
    lines.append("")
    for row in rows:
        lines.append(f"## `{row['paper_id']}` {row['title']}")
        lines.append(f"- Categories: {', '.join(row['categories'])}")
        lines.append(f"- Abstract file: `{row['summary_path']}`")
        if row.get("abstract"):
            lines.append(f"- Abstract: {row['abstract'][:500]}")
    return "\n".join(lines).rstrip() + "\n"


def _render_manifest_json(manifest: SourceManifest) -> str:
    return json_dumps(
        {
            "source_dir": str(manifest.source_dir),
            "files": [asdict(item) for item in manifest.files],
        }
    )


def _render_routing_prompt(
    paper: ArxivPaper,
    manifest: SourceManifest,
    abstract_text: str,
    config: dict,
) -> str:
    payload = build_router_payload(
        manifest,
        {
            "paper_id": paper.id_version,
            "title": paper.title,
            "abstract": abstract_text,
            "categories": paper.categories,
            "primary_category": paper.primary_category,
            "venue_hint": paper.venue_hint,
            "focus": config.get("focus", {}),
        },
    )
    lines: list[str] = []
    lines.append(f"# Routing Prompt - {paper.id_version}")
    lines.append("")
    lines.append("Choose the TeX/text files that should be read for full paper review.")
    lines.append("The source structure may be custom, so use the manifest and previews.")
    lines.append("Return only JSON matching `ROUTER_SYSTEM_PROMPT`.")
    lines.append("")
    lines.append("## System Prompt")
    lines.append("```text")
    lines.append(ROUTER_SYSTEM_PROMPT.strip())
    lines.append("```")
    lines.append("")
    lines.append("## Payload")
    lines.append("```json")
    lines.append(json.dumps(payload, indent=2, sort_keys=True, ensure_ascii=True))
    lines.append("```")
    return "\n".join(lines).rstrip() + "\n"


def _load_papers(run_dir: Path) -> list[ArxivPaper]:
    papers_path = run_dir / "papers.json"
    raw = json.loads(papers_path.read_text(encoding="utf-8"))
    papers: list[ArxivPaper] = []
    for item in raw:
        payload = {k: v for k, v in item.items() if k not in {"id_version", "abstract_path"}}
        papers.append(ArxivPaper(**payload))
    return papers


def _load_run_query(run_dir: Path) -> str:
    run_path = run_dir / "run.json"
    if run_path.exists():
        return json.loads(run_path.read_text(encoding="utf-8")).get("query", "")
    return ""


def _load_screening_decisions(path: str | Path) -> dict[str, ScreeningResult]:
    path = Path(path)
    if not path.exists():
        return {}
    raw = json.loads(path.read_text(encoding="utf-8"))
    return {
        paper_id: ScreeningResult(
            selected_for_full_read=bool(item.get("selected_for_full_read", False)),
            screening_score=int(item.get("screening_score", 0)),
            confidence=float(item.get("confidence", 0.0)),
            reason=str(item.get("reason", "")),
            risk_flags=list(item.get("risk_flags", [])),
        )
        for paper_id, item in raw.items()
    }


def _load_routing_decisions(path: str | Path) -> dict[str, RoutingDecision]:
    path = Path(path)
    raw = json.loads(path.read_text(encoding="utf-8"))
    return {
        paper_id: (RoutingDecision(**item) if isinstance(item, dict) else item)
        for paper_id, item in raw.items()
    }


def _load_manifest_from_json(path: Path) -> SourceManifest:
    raw = json.loads(path.read_text(encoding="utf-8"))
    from models import SourceFileInfo

    return SourceManifest(
        source_dir=Path(raw["source_dir"]),
        files=[SourceFileInfo(**item) for item in raw["files"]],
    )


def _load_reviews(path: str | Path) -> dict:
    path = Path(path)
    raw = json.loads(path.read_text(encoding="utf-8"))
    return raw


def _build_summary_stub(paper: ArxivPaper, extracted_text: str) -> SummaryResult:
    preview = extracted_text.strip().splitlines()[0] if extracted_text.strip() else paper.summary.strip()
    if len(preview) > 220:
        preview = preview[:217] + "..."
    return SummaryResult(
        one_sentence_summary=preview or "No summary available.",
        background="LLM-generated summary pending.",
        motivation="LLM-generated summary pending.",
        method="LLM-generated summary pending.",
        evaluation="LLM-generated summary pending.",
        results="LLM-generated summary pending.",
        baseline="LLM-generated summary pending.",
        novelty="LLM-generated summary pending.",
        limitations="LLM-generated summary pending.",
        quote_or_evidence=preview or paper.summary[:220],
    )
