# Auto-Paper Exploration Notes

Canonical rules live in [AGENTS.md](/home/tianjianyang/code/Auto-Paper/AGENTS.md) and [README.md](/home/tianjianyang/code/Auto-Paper/README.md). This file keeps the design rationale short.

## Retrieval

- Use the approved `cs` category allowlist as a hard fence and a fixed date window.
- Fetch metadata first, source archives later.
- Skip papers without usable source text.
- Keep requests polite and deterministic.

## Source Normalization

- TeX packages are custom, so routing must be manifest-driven and LLM-assisted.
- Build a manifest with path, suffix, size, preview, and simple TeX hints.
- Let Codex choose the main file and supporting files.
- Extract only the routed text and keep provenance.

## Summarization

- Summaries should answer: what problem, what method, what is new, what is the result, what are the limits.
- Keep the output compact and source-grounded.
- Prefer an evidence-backed summary over a polished but unsupported one.

## Quality Triage

- Use a separate review step from summarization.
- Score on 0-6 for relevance, infra fit, venue fit, technical substance, and evidence quality.
- `skip` only for clearly weak, malformed, or off-topic papers.
- Default to `skim` when uncertain.
- Treat "not obviously acceleration" as a weak signal, not an automatic exclusion. A paper with a novel idea or a plausible new direction can still deserve full reading.

## Daily Digest

- Summarize only papers that survive triage.
- Keep the output Chinese-first, but preserve English technical terms like `token`, `MoE`, and `KV cache`.
- For each paper card, include background, motivation, method, evaluation, results, baseline, novelty, limitations, and takeaway.
- Let scoring decide final inclusion; score-4 and score-5 papers belong in the digest.
- Rank by infra relevance and technical substance.

## MVP

- One category
- One date window
- Metadata fetch
- Source manifest
- LLM routing
- TeX/text extraction
- Review JSON
- Markdown digest
