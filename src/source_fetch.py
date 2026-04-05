from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from urllib.error import HTTPError, URLError
from urllib.request import Request, urlopen
import shutil
import tarfile
import zipfile
from collections.abc import Sequence


@dataclass(slots=True)
class SourceArchiveResult:
    archive_path: Path
    extract_dir: Path
    archive_kind: str


def build_source_url(template: str, paper_id: str) -> str:
    return template.format(paper_id=paper_id, arxiv_id=paper_id)


def download_source_archive(
    paper_id: str,
    dest_dir: str | Path,
    source_url_template: str | Sequence[str],
    user_agent: str = "Auto-Paper/0.1",
    timeout: float = 60.0,
) -> Path:
    dest_dir = Path(dest_dir)
    dest_dir.mkdir(parents=True, exist_ok=True)
    temp_path = dest_dir / "source.download"
    templates = [source_url_template] if isinstance(source_url_template, str) else list(source_url_template)
    last_error: Exception | None = None

    for template in templates:
        url = build_source_url(template, paper_id)
        request = Request(url, headers={"User-Agent": user_agent})
        try:
            with urlopen(request, timeout=timeout) as response, temp_path.open("wb") as handle:
                shutil.copyfileobj(response, handle)
            break
        except (HTTPError, URLError) as exc:
            last_error = exc
            if temp_path.exists():
                temp_path.unlink()
    else:
        raise RuntimeError(f"Failed to download arXiv source for {paper_id}: {last_error}") from last_error

    archive_path = _final_archive_path(temp_path)
    if archive_path != temp_path:
        if archive_path.exists():
            archive_path.unlink()
        temp_path.replace(archive_path)
    return archive_path


def extract_source_archive(archive_path: str | Path, extract_dir: str | Path) -> Path:
    archive_path = Path(archive_path)
    extract_dir = Path(extract_dir)
    extract_dir.mkdir(parents=True, exist_ok=True)

    if zipfile.is_zipfile(archive_path):
        with zipfile.ZipFile(archive_path) as archive:
            _safe_extract_zip(archive, extract_dir)
        return extract_dir

    if tarfile.is_tarfile(archive_path):
        with tarfile.open(archive_path, mode="r:*") as archive:
            _safe_extract_tar(archive, extract_dir)
        return extract_dir

    raise ValueError(f"Unsupported archive format: {archive_path}")


def download_and_extract_source(
    paper_id: str,
    dest_dir: str | Path,
    source_url_template: str | Sequence[str],
    user_agent: str = "Auto-Paper/0.1",
    timeout: float = 60.0,
) -> SourceArchiveResult:
    dest_dir = Path(dest_dir)
    archive_path = download_source_archive(
        paper_id=paper_id,
        dest_dir=dest_dir,
        source_url_template=source_url_template,
        user_agent=user_agent,
        timeout=timeout,
    )
    extract_dir = dest_dir / "source"
    extract_source_archive(archive_path, extract_dir)
    return SourceArchiveResult(
        archive_path=archive_path,
        extract_dir=extract_dir,
        archive_kind=_archive_kind(archive_path),
    )


def _final_archive_path(temp_path: Path) -> Path:
    if zipfile.is_zipfile(temp_path):
        return temp_path.with_suffix(".zip")
    if tarfile.is_tarfile(temp_path):
        with temp_path.open("rb") as handle:
            magic = handle.read(3)
        if magic[:2] == b"\x1f\x8b":
            return temp_path.with_name(temp_path.stem + ".tar.gz")
        return temp_path.with_suffix(".tar")
    return temp_path.with_suffix(".bin")


def _archive_kind(archive_path: Path) -> str:
    if archive_path.suffix == ".zip":
        return "zip"
    if archive_path.name.endswith(".tar.gz"):
        return "tar.gz"
    if archive_path.suffix == ".tar":
        return "tar"
    return "binary"


def _safe_extract_tar(archive: tarfile.TarFile, extract_dir: Path) -> None:
    root = extract_dir.resolve()
    for member in archive.getmembers():
        member_path = (extract_dir / member.name).resolve()
        if not member_path.is_relative_to(root):
            raise RuntimeError(f"Unsafe tar member path: {member.name}")
    archive.extractall(extract_dir)


def _safe_extract_zip(archive: zipfile.ZipFile, extract_dir: Path) -> None:
    root = extract_dir.resolve()
    for member in archive.infolist():
        member_path = (extract_dir / member.filename).resolve()
        if not member_path.is_relative_to(root):
            raise RuntimeError(f"Unsafe zip member path: {member.filename}")
    archive.extractall(extract_dir)
