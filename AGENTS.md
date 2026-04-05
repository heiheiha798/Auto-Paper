# Auto-Paper

This repository is a TeX-first arXiv workflow for AI infra reading.

Codex startup contract:
- Read this file first.
- Treat `_upstream/` as reference material only.
- Keep scoring on a 6-point scale everywhere. Use strong baseline comparison as the main reference; genuinely novel ideas can earn high scores when the evidence is credible.
- Prefer Codex-driven routing, summarization, triage, and review. The code should prepare artifacts, not hide the reasoning layer.
- Fetch only the approved `cs` category allowlist first, and treat it as a hard fence: keep only papers whose arXiv categories are fully inside the allowlist, then let Codex decide what is infra-relevant.
- The reading scope is broader than pure acceleration: include papers with a novel idea or a paper-worthy direction even if the main gain is not speed.
- The daily digest should include the score-4 and score-5 papers that survive scoring/filtering.
- The daily digest should be Chinese-first, with English technical terms preserved as English names, e.g. `token`, `MoE`, `KV cache`, and `speculative decoding`.
- Do not add PDF/OCR extraction paths.
- Keep runtime artifacts under `data/runs/` and daily Markdown under `reports/daily/`.
- For long backfills, the main process must act as a persistent scheduler and delegate one day to one subagent.
- Do not have the main process loop over days serially when independent subagents can run in parallel.
- Treat each date as an independently resumable unit with explicit completion state.
- Default day-level subagents run as `gpt-5.4` with `reasoning_effort=high` (`gpt-5.4-high` shorthand).
- Update or add tests in `tests/` when workflow behavior changes.

Canonical workflow:
1. `auto-paper prepare` fetches metadata and writes a screening queue.
2. Codex reads the queue and writes `screening_decisions.json`.
3. `auto-paper materialize` downloads source archives and builds manifests.
4. Codex reads routing prompts and writes `routing_decisions.json`.
5. `auto-paper extract` extracts TeX/text for routed files.
6. Codex writes `reviews.json` with 6-point scores and concise summaries.
7. `auto-paper digest` renders the daily Markdown report.

For command syntax and defaults, see `README.md` and `configs/default.toml`.
