from __future__ import annotations

from pathlib import Path

from models import DigestEntry, DigestReport


def _render_paper_card(entry: DigestEntry) -> list[str]:
    lines: list[str] = []
    lines.append(f"### {entry.title} (`{entry.paper_id}`)")
    lines.append(f"- 评分: {entry.triage.overall_score}/6")
    lines.append(f"- 决策: {entry.triage.decision}")
    if entry.venue_hint:
        lines.append(f"- Venue: {entry.venue_hint}")
    lines.append(f"- Background: {entry.summary.background}")
    lines.append(f"- Motivation: {entry.summary.motivation}")
    lines.append(f"- Method: {entry.summary.method}")
    lines.append(f"- Evaluation: {entry.summary.evaluation}")
    lines.append(f"- Results: {entry.summary.results}")
    lines.append(f"- Baseline: {entry.summary.baseline}")
    lines.append(f"- Novelty: {entry.summary.novelty}")
    lines.append(f"- Limitations / risks: {entry.summary.limitations}")
    lines.append(f"- 一句话总结: {entry.summary.one_sentence_summary}")
    lines.append(f"- 主观评价: {entry.triage.reason or '当前这篇值得收入日报。'}")
    if entry.triage.risk_flags:
        lines.append(f"- 风险: {', '.join(entry.triage.risk_flags)}")
    lines.append("")
    return lines


def render_digest(report: DigestReport) -> str:
    lines: list[str] = []
    lines.append(f"# Daily ArXiv Digest - {report.date}")
    lines.append("")
    lines.append("> 正文中文为主，英文技术名词保留原文，例如 `token`, `MoE`, `KV cache`, `speculative decoding`。")
    lines.append("")
    lines.append("## 摘要")
    lines.append(f"- Query: {report.category}")
    lines.append(f"- Total fetched: {report.total_fetched}")
    lines.append(f"- Total routed: {report.total_routed}")
    lines.append(f"- Total skipped: {report.total_skipped}")
    lines.append("")
    high_scoring = [entry for entry in report.entries if entry.triage.overall_score >= 4]
    if high_scoring:
        lines.append("## 高分论文")
        for entry in high_scoring:
            lines.extend(_render_paper_card(entry))
    else:
        lines.append("## 高分论文")
        lines.append("- 无")
        lines.append("")
    return "\n".join(lines).rstrip() + "\n"


def write_digest(path: str | Path, report: DigestReport) -> Path:
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(render_digest(report), encoding="utf-8")
    return path
