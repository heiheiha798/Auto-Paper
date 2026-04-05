from __future__ import annotations

import io
import json
import tarfile
import tempfile
import unittest
import sys
import zipfile
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from abstracts import extract_abstract_text
from config import load_config
from digest import render_digest
from manifest import build_source_manifest
from models import DigestEntry, DigestReport, RoutingDecision, SummaryResult, TriageResult
from source_fetch import extract_source_archive
from workflow import build_date_window_query


class CoreTests(unittest.TestCase):
    def test_load_default_config(self) -> None:
        config = load_config()
        self.assertEqual(config.arxiv["search_query"], "cat:cs.*")
        self.assertEqual(config.digest["top_k"], 5)

    def test_build_date_window_query(self) -> None:
        query = build_date_window_query("cat:cs.*", "2026-04-05", "UTC", window_days=1)
        self.assertIn("cat:cs.*", query)
        self.assertIn("submittedDate:[202604050000 TO 202604060000]", query)

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
        triage = TriageResult(
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
                    venue_hint="OSDI",
                    triage=triage,
                    summary=summary,
                    source_files=["main.tex"],
                )
            ],
        )
        rendered = render_digest(report)
        self.assertIn("Daily ArXiv Digest - 2026-04-05", rendered)
        self.assertIn("Inference for infra", rendered)
        self.assertIn("High-Score Papers", rendered)
        self.assertIn("Baseline:", rendered)
        self.assertIn("Novelty:", rendered)
        self.assertIn("Method:", rendered)

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
