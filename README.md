# Auto-Paper

Auto-Paper is a TeX-first arXiv workflow for Codex-driven paper reading.

## Startup

Codex should read [AGENTS.md](/home/tianjianyang/code/Auto-Paper/AGENTS.md) first.

## Notes

- TeX/source only, no PDF or OCR fallback.
- 6-point scoring throughout.
- Chinese-first output with English technical terms preserved.
- `reports/tracks/README.md` is a manual track reference.
- `auto-paper prepare` supports `--search-term` plus `--query-start-date` / `--query-end-date`.

## Workflow

1. `auto-paper prepare`
   - Fetches arXiv metadata for the date window from the approved `cs` category allowlist only, with the allowlist enforced as a hard fence.
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
7. `auto-paper digest` renders the daily Markdown report from score-4 and score-5 survivors.

For long backfills, the main process should schedule one date per subagent and persist completion state between runs. Do not implement a single serial loop in the main process when dates can be processed independently.
Default day-level subagents should run as `gpt-5.4` with `reasoning_effort=high`.

## Commands

- `auto-paper prepare [--date YYYY-MM-DD]`
- `auto-paper prepare [--date YYYY-MM-DD] [--search-query <raw>] [--search-term <phrase> ...] [--search-terms-mode any|all] [--query-start-date YYYY-MM-DD] [--query-end-date YYYY-MM-DD]`
- `auto-paper screening-template`
- `auto-paper materialize --run-dir <run-dir> [--screening-decisions <path>]`
- `auto-paper extract --run-dir <run-dir> --routing-decisions <path>`
- `auto-paper digest --date <YYYY-MM-DD> [--run-dir <run-dir>] [--reviews <path>] [--output <path>]`
  - Defaults to `data/runs/<date>/reviews.json` and `reports/daily/<date>.md` when paths are omitted.

## Layout

- `data/runs/<date>/` for runtime artifacts
- `data/runs/<date>/papers/<arxiv_idvN>/` for per-paper source and extraction files
- `reports/daily/` for daily Markdown
- `reports/tracks/README.md` for track reference buckets
