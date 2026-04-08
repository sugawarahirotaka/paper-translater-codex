from __future__ import annotations

import re
import shutil
import subprocess
from pathlib import Path

from .models import PageArtifact


REQUIRED_COMMANDS = ("pdfinfo", "pdftotext", "pdftoppm")


def ensure_pdf_commands() -> None:
    missing = [command for command in REQUIRED_COMMANDS if shutil.which(command) is None]
    if missing:
        joined = ", ".join(missing)
        raise RuntimeError(f"Missing required PDF tools: {joined}")


def get_page_count(pdf_path: Path) -> int:
    result = subprocess.run(
        ["pdfinfo", str(pdf_path)],
        check=True,
        capture_output=True,
        text=True,
    )
    match = re.search(r"^Pages:\s+(\d+)", result.stdout, re.MULTILINE)
    if not match:
        raise RuntimeError("Could not determine page count from pdfinfo output.")
    return int(match.group(1))


def extract_page_text(pdf_path: Path, page_number: int, output_path: Path) -> str:
    if output_path.exists():
        return output_path.read_text(encoding="utf-8")

    result = subprocess.run(
        [
            "pdftotext",
            "-enc",
            "UTF-8",
            "-layout",
            "-f",
            str(page_number),
            "-l",
            str(page_number),
            str(pdf_path),
            "-",
        ],
        check=True,
        capture_output=True,
        text=True,
    )
    text = result.stdout
    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(text, encoding="utf-8")
    return text


def render_page_image(pdf_path: Path, page_number: int, output_path: Path, dpi: int) -> Path:
    if output_path.exists():
        return output_path

    output_path.parent.mkdir(parents=True, exist_ok=True)
    prefix = output_path.with_suffix("")
    subprocess.run(
        [
            "pdftoppm",
            "-f",
            str(page_number),
            "-l",
            str(page_number),
            "-singlefile",
            "-png",
            "-r",
            str(dpi),
            str(pdf_path),
            str(prefix),
        ],
        check=True,
        capture_output=True,
        text=True,
    )
    if not output_path.exists():
        raise RuntimeError(f"Expected rendered image was not created: {output_path}")
    return output_path


def extract_pages(
    pdf_path: Path,
    work_dir: Path,
    start_page: int | None,
    end_page: int | None,
    dpi: int,
) -> list[PageArtifact]:
    total_pages = get_page_count(pdf_path)
    start = start_page or 1
    end = end_page or total_pages

    if start < 1 or end > total_pages or start > end:
        raise ValueError(f"Invalid page range {start}-{end} for a {total_pages}-page PDF.")

    pages: list[PageArtifact] = []
    text_dir = work_dir / "text"
    image_dir = work_dir / "images"

    for page_number in range(start, end + 1):
        text_path = text_dir / f"page_{page_number:04d}.txt"
        image_path = image_dir / f"page_{page_number:04d}.png"
        text = extract_page_text(pdf_path, page_number, text_path)
        render_page_image(pdf_path, page_number, image_path, dpi)
        pages.append(
            PageArtifact(
                page_number=page_number,
                text=text,
                text_path=text_path,
                image_path=image_path,
            )
        )

    return pages

