from __future__ import annotations

import hashlib
import json
import re
import subprocess
from dataclasses import dataclass
from pathlib import Path

from .models import ChunkInput, PageArtifact
from .pdf_tools import ensure_pdf_commands, extract_pages, get_page_count
from .text_utils import normalize_markdown, slugify_title


@dataclass(slots=True)
class CodexJobConfig:
    pdf_path: Path
    job_dir: Path | None = None
    pages_per_chunk: int = 1
    start_page: int | None = None
    end_page: int | None = None
    dpi: int = 180
    output_path: Path | None = None
    force: bool = False


def prepare_job(config: CodexJobConfig) -> Path:
    ensure_pdf_commands()
    pdf_path = config.pdf_path.expanduser().resolve()
    initial_title_guess = guess_pdf_title(pdf_path)
    job_dir = _resolve_job_dir(pdf_path, config.job_dir, initial_title_guess)
    manifest_path = job_dir / "manifest.json"

    if manifest_path.exists() and not config.force:
        return job_dir

    job_dir.mkdir(parents=True, exist_ok=True)
    pages = extract_pages(
        pdf_path=pdf_path,
        work_dir=job_dir,
        start_page=config.start_page,
        end_page=config.end_page,
        dpi=config.dpi,
    )
    chunks = _build_chunks(pages, config.pages_per_chunk)
    title_guess = guess_title(pages[0].text if pages else initial_title_guess or pdf_path.stem)
    title_slug = slugify_title(title_guess, fallback=pdf_path.stem)
    output_path = (
        config.output_path.expanduser().resolve()
        if config.output_path is not None
        else job_dir / "final" / f"{title_slug}.ja.md"
    )

    sources_dir = job_dir / "source"
    translations_dir = job_dir / "translations"
    sources_dir.mkdir(parents=True, exist_ok=True)
    translations_dir.mkdir(parents=True, exist_ok=True)
    (job_dir / "final").mkdir(parents=True, exist_ok=True)

    manifest = {
        "version": 1,
        "pdf_path": str(pdf_path),
        "job_dir": str(job_dir),
        "title_guess": title_guess,
        "total_pages": get_page_count(pdf_path),
        "pages_per_chunk": config.pages_per_chunk,
        "start_page": pages[0].page_number if pages else None,
        "end_page": pages[-1].page_number if pages else None,
        "output_path": str(output_path),
        "output_path_explicit": config.output_path is not None,
        "job_dir_explicit": config.job_dir is not None,
        "chunks": [],
    }

    for chunk in chunks:
        source_path = sources_dir / f"chunk_{chunk.chunk_index:04d}.source.md"
        translation_path = translations_dir / f"chunk_{chunk.chunk_index:04d}.ja.md"
        source_path.write_text(_render_source_chunk(chunk), encoding="utf-8")
        manifest["chunks"].append(
            {
                "chunk_index": chunk.chunk_index,
                "page_numbers": chunk.page_numbers,
                "source_path": str(source_path),
                "translation_path": str(translation_path),
                "image_paths": [str(path) for path in chunk.image_paths],
            }
        )

    manifest_path.write_text(
        json.dumps(manifest, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )
    return job_dir


def read_manifest(job_dir: Path) -> dict:
    manifest_path = job_dir.expanduser().resolve() / "manifest.json"
    if not manifest_path.exists():
        raise FileNotFoundError(f"Manifest not found: {manifest_path}")
    return json.loads(manifest_path.read_text(encoding="utf-8"))


def pending_chunks(job_dir: Path) -> list[dict]:
    manifest = read_manifest(job_dir)
    pending: list[dict] = []
    for chunk in manifest["chunks"]:
        translation_path = Path(chunk["translation_path"])
        if not translation_path.exists() or not translation_path.read_text(encoding="utf-8").strip():
            pending.append(chunk)
    return pending


def assemble_job(job_dir: Path, allow_partial: bool = False) -> Path:
    manifest = read_manifest(job_dir)
    preferred_title = _preferred_title(manifest)
    job_dir = _maybe_relocate_job_dir(job_dir.expanduser().resolve(), manifest, preferred_title)
    manifest = read_manifest(job_dir)
    parts: list[str] = []
    missing: list[int] = []

    for chunk in manifest["chunks"]:
        translation_path = Path(chunk["translation_path"])
        if not translation_path.exists():
            missing.append(chunk["chunk_index"])
            continue
        content = translation_path.read_text(encoding="utf-8").strip()
        if not content:
            missing.append(chunk["chunk_index"])
            continue
        parts.append(content)

    if missing and not allow_partial:
        joined = ", ".join(str(item) for item in missing)
        raise RuntimeError(f"Cannot assemble because these chunks are still missing: {joined}")

    output_path = _resolve_output_path_for_manifest(job_dir, manifest, preferred_title)
    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(normalize_markdown("\n\n".join(parts)), encoding="utf-8")
    _rewrite_manifest_paths(
        job_dir=job_dir,
        manifest=manifest,
        title=preferred_title,
        output_path=output_path,
    )
    return output_path


def guess_title(first_page_text: str) -> str:
    lines = [_normalize_title_line(line) for line in first_page_text.splitlines()]
    filtered = [
        line
        for line in lines
        if line
        and len(line) >= 8
        and not line.lower().startswith(
            (
                "abstract",
                "arxiv:",
                "keywords",
                "introduction",
                "published as",
                "accepted to",
                "proceedings of",
                "supplementary material",
            )
        )
    ]
    if not filtered:
        return "translated-paper"

    title_lines: list[str] = []
    for line in filtered[:5]:
        if len(title_lines) >= 3:
            break
        if any(char.isdigit() for char in line) and title_lines:
            break
        if "@" in line and title_lines:
            break
        if line.endswith("."):
            if not title_lines:
                continue
            break
        if len(line.split()) <= 1 and title_lines:
            break
        title_lines.append(line)
        if len(" ".join(title_lines)) >= 120:
            break

    title = " ".join(title_lines).strip()
    return title or filtered[0]


def guess_pdf_title(pdf_path: Path) -> str:
    metadata_title = _read_pdfinfo_title(pdf_path)
    if metadata_title:
        return metadata_title
    first_page_text = _read_first_page_text(pdf_path)
    return guess_title(first_page_text or pdf_path.stem)


def format_status(job_dir: Path) -> str:
    manifest = read_manifest(job_dir)
    pending = pending_chunks(job_dir)
    total = len(manifest["chunks"])
    done = total - len(pending)
    lines = [
        f"Job: {manifest['job_dir']}",
        f"PDF: {manifest['pdf_path']}",
        f"Title guess: {manifest['title_guess']}",
        f"Progress: {done}/{total} chunks translated",
        f"Output: {manifest['output_path']}",
    ]
    if pending:
        lines.append("Pending chunks:")
        for chunk in pending:
            lines.append(
                f"- chunk {chunk['chunk_index']:04d} pages {_page_label(chunk['page_numbers'])} -> {chunk['source_path']}"
            )
    else:
        lines.append("Pending chunks: none")
    return "\n".join(lines) + "\n"


def _build_chunks(pages: list[PageArtifact], pages_per_chunk: int) -> list[ChunkInput]:
    chunks: list[ChunkInput] = []
    for index, start in enumerate(range(0, len(pages), pages_per_chunk), start=1):
        group = pages[start : start + pages_per_chunk]
        source_text = "\n\n".join(
            f"[Page {page.page_number}]\n{page.text.strip()}" for page in group
        ).strip()
        chunks.append(
            ChunkInput(
                chunk_index=index,
                page_numbers=[page.page_number for page in group],
                source_text=source_text,
                image_paths=[page.image_path for page in group],
            )
        )
    return chunks


def _render_source_chunk(chunk: ChunkInput) -> str:
    lines = [
        f"# Source Chunk {chunk.chunk_index:04d}",
        "",
        f"Pages: {_page_label(chunk.page_numbers)}",
        "",
        "Use this chunk as the sole source for a faithful Japanese Markdown translation.",
        "Translate all visible paper content in these pages, including appendix or supplement text when present.",
        "Do not summarize. Keep equations, numbering, and citation markers.",
        "Keep the paper title in English without translating it.",
        "For display math, use an unindented block with $$ on its own lines.",
        "",
        "## Page Images",
        "",
    ]
    for image_path in chunk.image_paths:
        lines.append(f"- {image_path}")
    lines.extend(
        [
            "",
            "## Extracted Text",
            "",
            "```text",
            chunk.source_text,
            "```",
            "",
        ]
    )
    return "\n".join(lines)


def _resolve_job_dir(pdf_path: Path, job_dir: Path | None, title_guess: str) -> Path:
    if job_dir is not None:
        return job_dir.expanduser().resolve()
    slug = slugify_title(title_guess, fallback=pdf_path.stem)
    base = Path.cwd() / ".paper-translator-jobs" / slug
    if not base.exists():
        return base
    digest = hashlib.sha1(str(pdf_path).encode("utf-8")).hexdigest()[:10]
    return Path.cwd() / ".paper-translator-jobs" / f"{slug}-{digest}"


def _normalize_title_line(line: str) -> str:
    value = re.sub(r"\s+", " ", line.strip())
    if not value:
        return value
    if not re.search(r"[a-z]", value):
        previous = None
        while previous != value:
            previous = value
            value = re.sub(r"\b([A-Z]) ([A-Z]{2,})\b", r"\1\2", value)
            value = re.sub(r"\b([A-Z]) ([A-Z][a-zA-Z-]+)\b", r"\1\2", value)
    value = re.sub(r"\s*-\s*", "-", value)
    return value.strip()


def _read_pdfinfo_title(pdf_path: Path) -> str:
    result = subprocess.run(
        ["pdfinfo", str(pdf_path)],
        check=True,
        capture_output=True,
        text=True,
    )
    for line in result.stdout.splitlines():
        if not line.startswith("Title:"):
            continue
        title = _normalize_title_line(line.partition(":")[2])
        if title:
            return title
    return ""


def _read_first_page_text(pdf_path: Path) -> str:
    result = subprocess.run(
        [
            "pdftotext",
            "-enc",
            "UTF-8",
            "-layout",
            "-f",
            "1",
            "-l",
            "1",
            str(pdf_path),
            "-",
        ],
        check=True,
        capture_output=True,
        text=True,
    )
    return result.stdout


def _preferred_title(manifest: dict) -> str:
    for chunk in manifest["chunks"]:
        translation_path = Path(chunk["translation_path"])
        if not translation_path.exists():
            continue
        title = _extract_markdown_title(translation_path.read_text(encoding="utf-8"))
        if title:
            return title
    return manifest.get("title_guess", "translated-paper")


def _extract_markdown_title(content: str) -> str:
    for line in content.splitlines():
        stripped = line.strip()
        if not stripped:
            continue
        if stripped.startswith("# "):
            return stripped[2:].strip()
    return ""


def _resolve_output_path_for_manifest(job_dir: Path, manifest: dict, title: str) -> Path:
    current_output = Path(manifest["output_path"])
    if manifest.get("output_path_explicit", False):
        return current_output

    canonical_name = f"{slugify_title(title, fallback=current_output.stem)}.ja.md"
    canonical_output = job_dir / "final" / canonical_name
    if current_output != canonical_output and current_output.exists():
        current_output.unlink()
    return canonical_output


def _rewrite_manifest_paths(job_dir: Path, manifest: dict, title: str, output_path: Path) -> None:
    old_job_dir = Path(manifest["job_dir"])
    manifest["job_dir"] = str(job_dir)
    manifest["title_guess"] = title
    manifest["output_path"] = str(output_path)
    for chunk in manifest["chunks"]:
        chunk["source_path"] = _replace_path_root(chunk["source_path"], old_job_dir, job_dir)
        chunk["translation_path"] = _replace_path_root(chunk["translation_path"], old_job_dir, job_dir)
        if "image_paths" in chunk:
            chunk["image_paths"] = [
                _replace_path_root(path, old_job_dir, job_dir) for path in chunk["image_paths"]
            ]
        source_path = Path(chunk["source_path"])
        if source_path.exists():
            source_path.write_text(
                source_path.read_text(encoding="utf-8").replace(str(old_job_dir), str(job_dir)),
                encoding="utf-8",
            )
    (job_dir / "manifest.json").write_text(
        json.dumps(manifest, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )


def _replace_path_root(path_str: str, old_root: Path, new_root: Path) -> str:
    path = Path(path_str)
    try:
        relative = path.relative_to(old_root)
    except ValueError:
        return str(path)
    return str(new_root / relative)


def _maybe_relocate_job_dir(job_dir: Path, manifest: dict, title: str) -> Path:
    if manifest.get("job_dir_explicit", False):
        return job_dir

    desired_name = slugify_title(title, fallback=job_dir.name)
    desired_job_dir = job_dir.parent / desired_name
    if desired_job_dir == job_dir:
        return job_dir
    if desired_job_dir.exists():
        digest = hashlib.sha1(manifest["pdf_path"].encode("utf-8")).hexdigest()[:10]
        desired_job_dir = job_dir.parent / f"{desired_name}-{digest}"
    job_dir.rename(desired_job_dir)
    moved_old_output = Path(_replace_path_root(manifest["output_path"], job_dir, desired_job_dir))
    canonical_output = _resolve_output_path_for_manifest(desired_job_dir, manifest, title)
    if moved_old_output != canonical_output and moved_old_output.exists():
        moved_old_output.unlink()
    _rewrite_manifest_paths(
        job_dir=desired_job_dir,
        manifest=manifest,
        title=title,
        output_path=canonical_output,
    )
    return desired_job_dir


def _page_label(page_numbers: list[int]) -> str:
    if not page_numbers:
        return "(none)"
    if len(page_numbers) == 1:
        return str(page_numbers[0])
    return f"{page_numbers[0]}-{page_numbers[-1]}"
