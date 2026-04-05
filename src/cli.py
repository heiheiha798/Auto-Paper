from __future__ import annotations

import argparse
from pathlib import Path

from config import load_config
from digest import write_digest
from workflow import (
    build_digest_report,
    extract_routed_text,
    materialize_selected_papers,
    prepare_run,
    render_digest_for_run,
    write_screening_decisions_template,
)


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog="auto-paper", description="TeX-first arXiv paper workflow for Codex.")
    parser.add_argument("--config", default=None, help="Path to config TOML file.")

    subparsers = parser.add_subparsers(dest="command", required=True)

    prepare = subparsers.add_parser("prepare", help="Fetch arXiv metadata and write the screening queue.")
    prepare.add_argument("--date", default=None, help="Run date in YYYY-MM-DD.")

    materialize = subparsers.add_parser("materialize", help="Download and unpack source for screened papers.")
    materialize.add_argument("--run-dir", required=True, help="Run directory created by prepare.")
    materialize.add_argument("--screening-decisions", default=None, help="Path to screening_decisions.json.")

    extract = subparsers.add_parser("extract", help="Extract routed TeX/text for selected papers.")
    extract.add_argument("--run-dir", required=True, help="Run directory created by prepare.")
    extract.add_argument("--routing-decisions", required=True, help="Path to routing_decisions.json.")

    digest = subparsers.add_parser("digest", help="Render the daily Markdown digest.")
    digest.add_argument("--run-dir", required=True, help="Run directory created by prepare.")
    digest.add_argument("--reviews", required=True, help="Path to review JSON.")
    digest.add_argument("--date", required=True, help="Run date in YYYY-MM-DD.")
    digest.add_argument("--output", default=None, help="Digest output path.")

    template = subparsers.add_parser("screening-template", help="Write a blank screening decision template.")
    template.add_argument("--run-dir", required=True, help="Run directory created by prepare.")
    template.add_argument("--output", default=None, help="Template output path.")

    return parser


def main() -> None:
    parser = build_parser()
    args = parser.parse_args()
    config = load_config(args.config).raw

    if args.command == "prepare":
        result = prepare_run(config, run_date=args.date)
        print(result.run_dir)
        if result.screening_queue_path:
            print(result.screening_queue_path)
        return

    if args.command == "materialize":
        results = materialize_selected_papers(config, args.run_dir, args.screening_decisions)
        for item in results:
            print(f"{item.paper.id_version}\t{item.status}\t{item.reason}")
        return

    if args.command == "extract":
        results = extract_routed_text(args.run_dir, args.routing_decisions)
        for item in results:
            print(f"{item.paper.id_version}\t{item.status}\t{item.extracted and item.extracted.source_dir}")
        return

    if args.command == "digest":
        if args.output:
            output = Path(args.output)
        else:
            output = Path(config.get("run", {}).get("daily_root", "reports/daily")) / f"{args.date}.md"
        path = render_digest_for_run(args.run_dir, args.reviews, args.date, output)
        print(path)
        return

    if args.command == "screening-template":
        output = Path(args.output) if args.output else Path(args.run_dir) / "screening_decisions.json"
        path = write_screening_decisions_template(args.run_dir, output)
        print(path)
        return


if __name__ == "__main__":
    main()
