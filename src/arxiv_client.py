from __future__ import annotations

import asyncio
import html
import re
from datetime import datetime
from urllib.parse import urlencode
from urllib.request import Request, urlopen
from urllib.error import URLError, HTTPError
import xml.etree.ElementTree as ET

from models import ArxivPaper

ATOM_NS = {"atom": "http://www.w3.org/2005/Atom", "arxiv": "http://arxiv.org/schemas/atom"}


def build_query_url(
    base_url: str,
    search_query: str,
    start: int,
    max_results: int,
    sort_by: str = "submittedDate",
    sort_order: str = "descending",
) -> str:
    query = urlencode(
        {
            "search_query": search_query,
            "start": start,
            "max_results": max_results,
            "sortBy": sort_by,
            "sortOrder": sort_order,
        }
    )
    return f"{base_url}?{query}"


def _parse_arxiv_id(raw_id: str) -> tuple[str, int]:
    match = re.search(r"/abs/([^v]+)v(\d+)$", raw_id)
    if not match:
        raise ValueError(f"Cannot parse arXiv id from {raw_id!r}")
    return match.group(1), int(match.group(2))


def _entry_text(entry: ET.Element, tag: str, default: str = "") -> str:
    node = entry.find(f"atom:{tag}", ATOM_NS)
    return html.unescape(node.text.strip()) if node is not None and node.text else default


def _entry_links(entry: ET.Element) -> tuple[str | None, str | None]:
    pdf_url = None
    source_url = None
    for link in entry.findall("atom:link", ATOM_NS):
        href = link.attrib.get("href")
        title = link.attrib.get("title", "")
        rel = link.attrib.get("rel", "")
        if href and link.attrib.get("type") == "application/pdf":
            pdf_url = href
        if href and (rel == "related" or "source" in title.lower() or href.endswith("/src")):
            source_url = href
    return source_url, pdf_url


def parse_feed(xml_text: str) -> list[ArxivPaper]:
    root = ET.fromstring(xml_text)
    papers: list[ArxivPaper] = []
    for entry in root.findall("atom:entry", ATOM_NS):
        raw_id = _entry_text(entry, "id")
        arxiv_id, version = _parse_arxiv_id(raw_id)
        title = _entry_text(entry, "title")
        summary = _entry_text(entry, "summary")
        published = _entry_text(entry, "published")
        updated = _entry_text(entry, "updated")
        primary_cat = entry.find("arxiv:primary_category", ATOM_NS)
        primary_category = primary_cat.attrib.get("term", "") if primary_cat is not None else ""
        categories = [cat.attrib.get("term", "") for cat in entry.findall("atom:category", ATOM_NS)]
        authors = [
            name.text.strip()
            for name in entry.findall("atom:author/atom:name", ATOM_NS)
            if name.text
        ]
        source_url, pdf_url = _entry_links(entry)
        link = ""
        for rel in entry.findall("atom:link", ATOM_NS):
            if rel.attrib.get("type") == "text/html":
                link = rel.attrib.get("href", "")
                break
        venue_hint = _infer_venue_hint(title, summary)
        papers.append(
            ArxivPaper(
                arxiv_id=arxiv_id,
                version=version,
                title=title,
                summary=summary,
                published=published,
                updated=updated,
                primary_category=primary_category,
                categories=categories,
                authors=authors,
                link=link,
                source_url=source_url,
                pdf_url=pdf_url,
                venue_hint=venue_hint,
                raw={"entry_xml": ET.tostring(entry, encoding="unicode")},
            )
        )
    return papers


def _infer_venue_hint(title: str, summary: str) -> str | None:
    text = f"{title}\n{summary}".lower()
    venues = ["osdi", "asplos", "sosp", "nsdi", "eurosys", "atc", "mlsys"]
    for venue in venues:
        if venue in text:
            return venue.upper()
    return None


class ArxivClient:
    def __init__(
        self,
        base_url: str,
        timeout: float = 30.0,
        request_delay: float = 3.0,
        user_agent: str = "Auto-Paper/0.1",
    ):
        self.base_url = base_url
        self.timeout = timeout
        self.request_delay = request_delay
        self.user_agent = user_agent

    async def fetch_feed(
        self,
        search_query: str,
        max_results: int,
        start: int = 0,
        sort_by: str = "submittedDate",
        sort_order: str = "descending",
    ) -> list[ArxivPaper]:
        url = build_query_url(
            self.base_url,
            search_query=search_query,
            start=start,
            max_results=max_results,
            sort_by=sort_by,
            sort_order=sort_order,
        )
        request = Request(url, headers={"User-Agent": self.user_agent})
        try:
            text = await asyncio.to_thread(self._fetch_text, request)
        except (HTTPError, URLError) as exc:
            raise RuntimeError(f"Failed to fetch arXiv feed: {exc}") from exc
        await asyncio.sleep(self.request_delay)
        return parse_feed(text)

    def _fetch_text(self, request: Request) -> str:
        with urlopen(request, timeout=self.timeout) as response:
            raw = response.read()
        return raw.decode("utf-8", errors="replace")
