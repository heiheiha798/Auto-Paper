from __future__ import annotations

from models import ArxivPaper, ExtractedDocument, TriageResult

SCORE_SCALE = 6


def score_triage(paper: ArxivPaper, extracted: ExtractedDocument, focus: dict) -> TriageResult:
    text = f"{paper.title}\n{paper.summary}\n{extracted.text}".lower()

    relevance_score = _score_relevance(text, focus)
    infra_fit_score = _score_infra_fit(text)
    venue_fit_score = 0
    technical_substance_score = _score_technical_substance(text, extracted.text)
    evidence_quality_score = _score_evidence(text, extracted.text)
    overall_score = min(
        SCORE_SCALE,
        round(
            (relevance_score + infra_fit_score + venue_fit_score + technical_substance_score + evidence_quality_score)
            / 5.0
        ),
    )

    risk_flags: list[str] = []
    if "prompt engineering" in text or "prompting" in text:
        risk_flags.append("prompting_focus")
    if "benchmark-only" in text:
        risk_flags.append("benchmark_only")
    if "pure algorithm" in text:
        risk_flags.append("likely_pure_algorithm")
    if not extracted.text.strip():
        risk_flags.append("empty_extracted_text")

    if not extracted.text.strip():
        decision = "skip"
        reason = "No readable source text extracted."
    elif overall_score >= 5 and infra_fit_score >= 4 and technical_substance_score >= 4:
        decision = "read_now"
        reason = "Strong overall fit for AI infra reading."
    elif overall_score <= 2 or infra_fit_score <= 2 or technical_substance_score <= 2:
        decision = "skip"
        reason = "Low value for the target reading scope."
    else:
        decision = "skim"
        reason = "Relevant enough to skim, but not an immediate deep-read."

    confidence = round(min(0.98, 0.30 + overall_score / 10.0), 2)
    return TriageResult(
        relevance_score=relevance_score,
        infra_fit_score=infra_fit_score,
        venue_fit_score=venue_fit_score,
        technical_substance_score=technical_substance_score,
        evidence_quality_score=evidence_quality_score,
        overall_score=overall_score,
        decision=decision,
        confidence=confidence,
        risk_flags=risk_flags,
        reason=reason,
    )


def _score_relevance(text: str, focus: dict) -> int:
    mission = str(focus.get("mission", "")).lower()
    score = 1 if mission else 0
    hints = [
        "serving",
        "inference",
        "runtime",
        "compiler",
        "deployment",
        "latency",
        "throughput",
        "memory",
        "edge",
        "systems",
        "speculative decoding",
    ]
    score += sum(1 for h in hints if h in text)
    return min(SCORE_SCALE, score)


def _score_infra_fit(text: str) -> int:
    hints = [
        "serving",
        "inference",
        "runtime",
        "scheduler",
        "batching",
        "kv cache",
        "memory",
        "latency",
        "throughput",
        "edge",
        "distributed",
        "speculative decoding",
    ]
    score = sum(1 for h in hints if h in text)
    return min(SCORE_SCALE, score)


def _score_venue(paper: ArxivPaper, focus: dict) -> int:
    return 0


def _score_technical_substance(text: str, raw_text: str) -> int:
    score = 0
    if "evaluation" in text or "experiment" in text or "benchmark" in text:
        score += 2
    if "results" in text or "ablation" in text or "comparison" in text:
        score += 1
    if "we show" in text or "we present" in text or "we introduce" in text:
        score += 1
    if "speculative decoding" in text or "cache" in text or "kernel" in text:
        score += 1
    if len(raw_text) > 2000:
        score += 1
    return min(SCORE_SCALE, score)


def _score_evidence(text: str, raw_text: str) -> int:
    score = 0
    if raw_text.strip():
        score += 1
    if "abstract" in text:
        score += 1
    if "table" in text or "figure" in text:
        score += 1
    if any(token in text for token in ["ms", "tokens/s", "samples/s", "gb", "latency", "throughput"]):
        score += 2
    if "we show" in text or "we present" in text:
        score += 1
    return min(SCORE_SCALE, score)
