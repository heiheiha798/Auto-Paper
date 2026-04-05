from __future__ import annotations

import io
import json
import tarfile
import tempfile
import unittest
from unittest.mock import patch
import asyncio
import sys
import subprocess
import zipfile
import os
from pathlib import Path
from datetime import datetime, timezone

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from abstracts import extract_abstract_text
from config import load_config
from cli import resolve_digest_output_path, resolve_reviews_path, resolve_run_dir
from digest import render_digest
from manifest import build_source_manifest
from models import ArxivPaper
from models import DigestEntry, DigestReport, RoutingDecision, SummaryResult, TriageResult
from source_fetch import extract_source_archive
from workflow import build_date_window_query, build_run_search_query, fetch_arxiv_papers


class CoreTests(unittest.TestCase):
    def test_load_default_config(self) -> None:
        config = load_config()
        self.assertEqual(config.arxiv["search_query"], "")
        self.assertEqual(config.arxiv["search_terms"], [])
        self.assertEqual(config.arxiv["search_terms_mode"], "any")
        self.assertEqual(config.arxiv["query_start_date"], "")
        self.assertEqual(config.arxiv["query_end_date"], "")
        self.assertEqual(
            config.arxiv["allowed_categories"],
            ["cs.AI", "cs.AR", "cs.CL", "cs.DC", "cs.LG", "cs.OS", "cs.PF", "cs.SE", "cs.SY"],
        )
        self.assertEqual(config.arxiv["max_results"], "")
        self.assertEqual(config.digest["top_k"], 5)
        self.assertEqual(config.llm["day_subagent_model"], "gpt-5.4")
        self.assertEqual(config.llm["day_subagent_reasoning_effort"], "high")
        self.assertEqual(config.llm["day_subagent_profile"], "gpt-5.4-high")

    def test_load_default_config_from_install_target(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            target = Path(tmp) / "install"
            subprocess.run(
                [sys.executable, "-m", "pip", "install", "--quiet", "--target", str(target), str(Path(__file__).resolve().parents[1])],
                check=True,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                text=True,
            )
            env = os.environ.copy()
            env["PYTHONPATH"] = str(target)
            proc = subprocess.run(
                [
                    sys.executable,
                    "-c",
                    "from config import load_config; cfg = load_config(); print(cfg.arxiv['search_query']); print(cfg.arxiv['search_terms']); print(cfg.arxiv['query_start_date']); print(cfg.arxiv['allowed_categories']); print(cfg.arxiv['max_results']); print(cfg.digest['top_k'])",
                ],
                check=True,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                text=True,
                env=env,
            )
            self.assertEqual(proc.stdout.splitlines()[0], "")
            self.assertEqual(proc.stdout.splitlines()[1], "[]")
            self.assertEqual(proc.stdout.splitlines()[2], "")
            self.assertIn("cs.AI", proc.stdout)
            self.assertEqual(proc.stdout.splitlines()[4], "")
            self.assertIn("5", proc.stdout)

    def test_build_date_window_query(self) -> None:
        query = build_date_window_query("cat:cs.AI OR cat:cs.OS", "2026-04-05", "UTC", window_days=1)
        self.assertIn("cat:cs.AI OR cat:cs.OS", query)
        self.assertIn("submittedDate:[202604050000 TO 202604060000]", query)

    def test_build_run_search_query(self) -> None:
        config = load_config().raw
        query = build_run_search_query(config, "2025-01-01")
        self.assertIn("cat:cs.AI", query)
        self.assertIn("cat:cs.OS", query)
        self.assertIn("submittedDate:[202412311600 TO 202501011600]", query)

    def test_build_run_search_query_supports_title_abstract_terms_and_date_range(self) -> None:
        config = load_config().raw
        query = build_run_search_query(
            config,
            "2026-04-05",
            search_terms=["Agent Memory", "Position-Independent Caching"],
            search_terms_mode="any",
            query_start_date="2025-01-01",
            now_utc=datetime(2026, 4, 5, 12, 0, tzinfo=timezone.utc),
        )
        self.assertIn("cat:cs.AI", query)
        self.assertIn('ti:"agent memory"', query)
        self.assertIn('abs:"agent memory"', query)
        self.assertIn('ti:"position-independent caching"', query)
        self.assertIn("submittedDate:[202412311600 TO 202604051200]", query)

    def test_fetch_arxiv_papers_uses_unbounded_pagination_when_max_results_blank(self) -> None:
        config = load_config().raw
        config["arxiv"]["max_results"] = ""
        config["arxiv"]["page_size"] = 1
        pages = [
            [ArxivPaper(
                arxiv_id="2401.00001",
                version=1,
                title="Paper A",
                summary="Summary A",
                published="2024-01-01T00:00:00Z",
                updated="2024-01-01T00:00:00Z",
                primary_category="cs.AI",
                categories=["cs.AI"],
                authors=["A"],
                link="https://arxiv.org/abs/2401.00001",
            )],
            [ArxivPaper(
                arxiv_id="2401.00002",
                version=1,
                title="Paper B",
                summary="Summary B",
                published="2024-01-01T00:00:00Z",
                updated="2024-01-01T00:00:00Z",
                primary_category="cs.AI",
                categories=["cs.AI"],
                authors=["B"],
                link="https://arxiv.org/abs/2401.00002",
            )],
            [],
        ]

        class FakeClient:
            def __init__(self) -> None:
                self.calls: list[tuple[str, int, int]] = []

            async def fetch_feed(self, search_query: str, max_results: int, start: int, sort_by: str, sort_order: str):
                self.calls.append((search_query, max_results, start))
                return pages[len(self.calls) - 1]

        fake_client = FakeClient()

        with patch("workflow.ArxivClient", return_value=fake_client):
            result = asyncio.run(fetch_arxiv_papers(config, "2025-01-01"))

        self.assertEqual([paper.arxiv_id for paper in result], ["2401.00001", "2401.00002"])
        self.assertEqual(fake_client.calls[0][1], 1)
        self.assertEqual(fake_client.calls[1][2], 1)
        self.assertEqual(fake_client.calls[2][2], 2)

    def test_fetch_arxiv_papers_passes_search_terms_and_open_date_window(self) -> None:
        config = load_config().raw
        config["arxiv"]["page_size"] = 1
        config["arxiv"]["max_results"] = "1"
        pages = [
            [ArxivPaper(
                arxiv_id="2401.00001",
                version=1,
                title="Paper A",
                summary="Summary A",
                published="2024-01-01T00:00:00Z",
                updated="2024-01-01T00:00:00Z",
                primary_category="cs.AI",
                categories=["cs.AI"],
                authors=["A"],
                link="https://arxiv.org/abs/2401.00001",
            )],
        ]

        class FakeClient:
            def __init__(self) -> None:
                self.calls: list[tuple[str, int, int]] = []

            async def fetch_feed(self, search_query: str, max_results: int, start: int, sort_by: str, sort_order: str):
                self.calls.append((search_query, max_results, start))
                return pages[0]

        fake_client = FakeClient()

        with patch("workflow.ArxivClient", return_value=fake_client):
            result = asyncio.run(
                fetch_arxiv_papers(
                    config,
                    "2026-04-05",
                    search_terms=["Agent Memory", "Position-Independent Caching"],
                    query_start_date="2025-01-01",
                    now_utc=datetime(2026, 4, 5, 12, 0, tzinfo=timezone.utc),
                )
            )

        self.assertEqual([paper.arxiv_id for paper in result], ["2401.00001"])
        self.assertEqual(len(fake_client.calls), 1)
        self.assertIn('ti:"agent memory"', fake_client.calls[0][0])
        self.assertIn('abs:"position-independent caching"', fake_client.calls[0][0])
        self.assertIn("submittedDate:[202412311600 TO 202604051200]", fake_client.calls[0][0])

    def test_fetch_arxiv_papers_filters_to_full_category_subset(self) -> None:
        config = load_config().raw
        config["arxiv"]["max_results"] = ""
        config["arxiv"]["page_size"] = 2

        pages = [
            [
                ArxivPaper(
                    arxiv_id="2401.00001",
                    version=1,
                    title="Allowed",
                    summary="Summary",
                    published="2024-01-01T00:00:00Z",
                    updated="2024-01-01T00:00:00Z",
                    primary_category="cs.AI",
                    categories=["cs.AI"],
                    authors=["A"],
                    link="https://arxiv.org/abs/2401.00001",
                ),
                ArxivPaper(
                    arxiv_id="2401.00002",
                    version=1,
                    title="Mixed",
                    summary="Summary",
                    published="2024-01-01T00:00:00Z",
                    updated="2024-01-01T00:00:00Z",
                    primary_category="cs.AI",
                    categories=["cs.AI", "eess.IV"],
                    authors=["B"],
                    link="https://arxiv.org/abs/2401.00002",
                ),
            ],
            [],
        ]

        class FakeClient:
            def __init__(self) -> None:
                self.calls: list[tuple[str, int, int]] = []

            async def fetch_feed(self, search_query: str, max_results: int, start: int, sort_by: str, sort_order: str):
                self.calls.append((search_query, max_results, start))
                return pages[len(self.calls) - 1]

        fake_client = FakeClient()

        with patch("workflow.ArxivClient", return_value=fake_client):
            result = asyncio.run(fetch_arxiv_papers(config, "2025-01-01"))

        self.assertEqual([paper.arxiv_id for paper in result], ["2401.00001"])

    def test_resolve_history_paths(self) -> None:
        config = load_config().raw
        run_dir = resolve_run_dir(config, "2026-04-05")
        self.assertEqual(run_dir.as_posix(), "data/runs/2026-04-05")
        self.assertEqual(resolve_reviews_path(run_dir).as_posix(), "data/runs/2026-04-05/reviews.json")
        self.assertEqual(
            resolve_digest_output_path(config, "2026-04-05").as_posix(),
            "reports/daily/2026-04-05.md",
        )

    def test_manifest_and_extract_follow_includes(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            (root / "main.tex").write_text(
                "\\documentclass{article}\n\\begin{document}\n\\input{sections/abstract}\n\\end{document}\n",
                encoding="utf-8",
            )
            (root / "sections").mkdir()
            (root / "sections" / "abstract.tex").write_text(
                "\\begin{abstract}A paper about inference systems.\\end{abstract}\n",
                encoding="utf-8",
            )

            manifest = build_source_manifest(root)
            self.assertTrue(any(item.has_documentclass for item in manifest.files))
            extracted = extract_abstract_text(root, manifest=manifest)
            self.assertIn("inference systems", extracted.text)
            self.assertEqual(extracted.source_path, "sections/abstract.tex")

    def test_digest_renders_sections(self) -> None:
        triage_5 = TriageResult(
            relevance_score=5,
            infra_fit_score=5,
            venue_fit_score=4,
            technical_substance_score=5,
            evidence_quality_score=5,
            overall_score=5,
            decision="read_now",
            confidence=0.9,
            risk_flags=[],
            reason="strong fit",
        )
        triage_4 = TriageResult(
            relevance_score=4,
            infra_fit_score=4,
            venue_fit_score=4,
            technical_substance_score=4,
            evidence_quality_score=4,
            overall_score=4,
            decision="skim",
            confidence=0.8,
            risk_flags=[],
            reason="worth including at score 4",
        )
        summary = SummaryResult(
            one_sentence_summary="This paper improves inference serving.",
            background="background",
            motivation="motivation",
            method="method",
            evaluation="eval",
            results="results",
            baseline="baseline",
            novelty="novelty",
            limitations="limits",
            quote_or_evidence="evidence",
        )
        report = DigestReport(
            date="2026-04-05",
            category="cat:cs.*",
            total_fetched=1,
            total_routed=1,
            total_skipped=0,
            entries=[
                DigestEntry(
                    paper_id="2401.00001v1",
                    title="Inference for infra",
                    venue_hint=None,
                    triage=triage_5,
                    summary=summary,
                    source_files=["main.tex"],
                ),
                DigestEntry(
                    paper_id="2401.00002v1",
                    title="Inference candidate at 4",
                    venue_hint=None,
                    triage=triage_4,
                    summary=summary,
                    source_files=["main.tex"],
                ),
            ],
        )
        rendered = render_digest(report)
        self.assertIn("Daily ArXiv Digest - 2026-04-05", rendered)
        self.assertIn("Inference for infra", rendered)
        self.assertIn("Inference candidate at 4", rendered)
        self.assertIn("高分论文", rendered)
        self.assertIn("Method:", rendered)
        self.assertIn("Results:", rendered)
        self.assertIn("Baseline:", rendered)
        self.assertIn("Novelty:", rendered)
        self.assertIn("正文中文为主", rendered)
        self.assertIn("主观评价:", rendered)
        self.assertNotIn("为什么保留", rendered)

    def test_extract_source_archive_tar_and_zip(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            tar_path = root / "sample.tar.gz"
            with tarfile.open(tar_path, "w:gz") as archive:
                payload = b"hello"
                info = tarfile.TarInfo("a.txt")
                info.size = len(payload)
                archive.addfile(info, io.BytesIO(payload))

            tar_extract = root / "tar_out"
            extract_source_archive(tar_path, tar_extract)
            self.assertEqual((tar_extract / "a.txt").read_text(encoding="utf-8"), "hello")

            zip_path = root / "sample.zip"
            with zipfile.ZipFile(zip_path, "w") as archive:
                archive.writestr("b.txt", "world")

            zip_extract = root / "zip_out"
            extract_source_archive(zip_path, zip_extract)
            self.assertEqual((zip_extract / "b.txt").read_text(encoding="utf-8"), "world")


if __name__ == "__main__":
    unittest.main()
