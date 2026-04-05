# Auto-Paper

Auto-Paper is a TeX-first arXiv workflow for Codex-driven paper reading.

## Startup

Codex should read [AGENTS.md](/home/tianjianyang/code/Auto-Paper/AGENTS.md) first.

## Core Rules

- Fetch broadly from `cat:cs.*` first, then let Codex decide relevance.
- The reading scope is not limited to acceleration; any paper with a novel idea or a plausible paper-worthy direction can be routed into full reading.
- The final digest only keeps papers that survive scoring.
- Keep the pipeline TeX/source only. No PDF or OCR fallback.
- Keep all scores on a 6-point scale.
- Keep runtime artifacts under `data/runs/<date>/`.
- Keep daily Markdown under `reports/daily/`.

## Workflow

1. `auto-paper prepare`
   - Fetches arXiv metadata for the date window.
   - Writes `screening_queue.json`, `screening_queue.md`, and `screening_prompt.md`.
2. Codex reads the queue and writes `screening_decisions.json`.
3. `auto-paper materialize`
   - Downloads arXiv source archives.
   - Builds `manifest.json` and `routing_prompt.md`.
4. Codex reads the routing prompt and writes `routing_decisions.json`.
5. `auto-paper extract`
   - Expands the routed TeX/text files.
   - Follows `\input` and `\include`.
   - Writes `extracted.txt` and `extracted.json`.
6. Codex writes `reviews.json` with 6-point scores and short summaries.
7. `auto-paper digest` renders the daily Markdown report from the scored survivors only.

For long backfills, the main process should schedule one date per subagent and persist completion state between runs. Do not implement a single serial loop in the main process when dates can be processed independently.

## Commands

- `auto-paper prepare [--date YYYY-MM-DD]`
- `auto-paper screening-template`
- `auto-paper materialize --run-dir <run-dir> [--screening-decisions <path>]`
- `auto-paper extract --run-dir <run-dir> --routing-decisions <path>`
- `auto-paper digest --date <YYYY-MM-DD> [--run-dir <run-dir>] [--reviews <path>] [--output <path>]`
  - Defaults to `data/runs/<date>/reviews.json` and `reports/daily/<date>.md` when paths are omitted.

## Layout

- `data/runs/<date>/` for runtime artifacts
- `data/runs/<date>/papers/<arxiv_idvN>/` for per-paper source and extraction files
- `reports/daily/` for daily Markdown
