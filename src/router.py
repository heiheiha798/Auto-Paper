from __future__ import annotations

import json
from dataclasses import asdict

from models import RoutingDecision, SourceManifest


ROUTER_SYSTEM_PROMPT = """You are routing a custom arXiv TeX source package.
The package structure is highly variable, so do not assume a fixed layout.

Your job:
- identify the most likely main TeX file
- choose supporting source files that should be read together
- ignore binary/build artifacts
- decide whether a second pass is needed after expanding includes

Return JSON only with:
{
  "main_files": [...],
  "supporting_files": [...],
  "ignore_files": [...],
  "confidence": 0.0-1.0,
  "reasoning_tags": [...],
  "needs_second_pass": true/false,
  "why_not_confident": "..."
}

Be conservative. If unsure, lower confidence and request a second pass.
"""


def build_router_payload(manifest: SourceManifest, paper_context: dict) -> dict:
    return {
        "paper_context": paper_context,
        "files": [
            {
                "path": item.path,
                "suffix": item.suffix,
                "size": item.size,
                "preview": item.preview,
                "has_documentclass": item.has_documentclass,
                "has_input": item.has_input,
                "has_include": item.has_include,
                "is_text": item.is_text,
            }
            for item in manifest.files
        ],
    }


def parse_router_json(payload: str) -> RoutingDecision:
    data = json.loads(payload)
    return RoutingDecision(
        main_files=list(data.get("main_files", [])),
        supporting_files=list(data.get("supporting_files", [])),
        ignore_files=list(data.get("ignore_files", [])),
        confidence=float(data.get("confidence", 0.0)),
        reasoning_tags=list(data.get("reasoning_tags", [])),
        needs_second_pass=bool(data.get("needs_second_pass", False)),
        why_not_confident=str(data.get("why_not_confident", "")),
    )


def routing_decision_to_json(decision: RoutingDecision) -> str:
    return json.dumps(asdict(decision), ensure_ascii=True, indent=2, sort_keys=True)
