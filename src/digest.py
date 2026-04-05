from __future__ import annotations

from pathlib import Path

from models import DigestEntry, DigestReport


def _render_paper_card(entry: DigestEntry) -> list[str]:
    lines: list[str] = []
    lines.append(f"### {entry.title} (`{entry.paper_id}`)")
    lines.append(f"- Score: {entry.triage.overall_score}/6")
    lines.append(f"- Decision: {entry.triage.decision}")
    if entry.venue_hint:
        lines.append(f"- Venue: {entry.venue_hint}")
    lines.append(f"- Why it survives: {entry.triage.reason or 'High-scoring paper under current filter.'}")
    lines.append(f"- Baseline: {entry.summary.baseline}")
    lines.append(f"- Novelty: {entry.summary.novelty}")
    lines.append(f"- Background: {entry.summary.background}")
    lines.append(f"- Motivation: {entry.summary.motivation}")
    lines.append(f"- Method: {entry.summary.method}")
    lines.append(f"- Evaluation: {entry.summary.evaluation}")
    lines.append(f"- Results: {entry.summary.results}")
    lines.append(f"- Limitations / risks: {entry.summary.limitations}")
    lines.append(f"- One-sentence takeaway: {entry.summary.one_sentence_summary}")
    if entry.triage.risk_flags:
        lines.append(f"- Risks: {', '.join(entry.triage.risk_flags)}")
    lines.append("")
    return lines


def render_digest(report: DigestReport) -> str:
    lines: list[str] = []
    lines.append(f"# Daily ArXiv Digest - {report.date}")
    lines.append("")
    lines.append("## Summary")
    lines.append(f"- Category: {report.category}")
    lines.append(f"- Total fetched: {report.total_fetched}")
    lines.append(f"- Total routed: {report.total_routed}")
    lines.append(f"- Total skipped: {report.total_skipped}")
    lines.append("")
    high_scoring = [entry for entry in report.entries if entry.triage.decision == "read_now"]
    if high_scoring:
        lines.append("## High-Score Papers")
        for entry in high_scoring:
            lines.extend(_render_paper_card(entry))
    else:
        lines.append("## High-Score Papers")
        lines.append("- None")
        lines.append("")
    return "\n".join(lines).rstrip() + "\n"


def write_digest(path: str | Path, report: DigestReport) -> Path:
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(render_digest(report), encoding="utf-8")
    return path
