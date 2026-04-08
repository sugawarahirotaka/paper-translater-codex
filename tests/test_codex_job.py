from __future__ import annotations

import json
import tempfile
import unittest
from pathlib import Path

from paper_translator.codex_job import (
    _extract_markdown_title,
    assemble_job,
    format_status,
    guess_title,
    pending_chunks,
)


class CodexJobTest(unittest.TestCase):
    def test_guess_title_skips_abstract(self) -> None:
        text = "\n".join(
            [
                "A Long Interesting Paper Title",
                "With a Subtitle",
                "",
                "Abstract",
                "This is the abstract.",
            ]
        )
        self.assertEqual(guess_title(text), "A Long Interesting Paper Title With a Subtitle")

    def test_guess_title_stops_before_authors(self) -> None:
        text = "\n".join(
            [
                "Vanilla Bayesian Optimization Performs Great in High Dimensions",
                "",
                "Carl Hvarfner 1 Erik O. Hellsten 1 2 Luigi Nardi 1 2",
                "Abstract",
            ]
        )
        self.assertEqual(
            guess_title(text),
            "Vanilla Bayesian Optimization Performs Great in High Dimensions",
        )

    def test_guess_title_skips_published_banner_and_repairs_split_caps(self) -> None:
        text = "\n".join(
            [
                "Published as a conference paper at ICLR 2025",
                "",
                "S TANDARD G AUSSIAN P ROCESS IS A LL YOU N EED FOR",
                "H IGH -D IMENSIONAL BAYESIAN O PTIMIZATION",
            ]
        )
        self.assertEqual(
            guess_title(text),
            "STANDARD GAUSSIAN PROCESS IS ALL YOU NEED FOR HIGH-DIMENSIONAL BAYESIAN OPTIMIZATION",
        )

    def test_extract_markdown_title_skips_banner_lines(self) -> None:
        content = "\n".join(
            [
                "ICLR 2025 採録論文",
                "",
                "# STANDARD GAUSSIAN PROCESS IS ALL YOU NEED FOR HIGH-DIMENSIONAL BAYESIAN OPTIMIZATION",
            ]
        )
        self.assertEqual(
            _extract_markdown_title(content),
            "STANDARD GAUSSIAN PROCESS IS ALL YOU NEED FOR HIGH-DIMENSIONAL BAYESIAN OPTIMIZATION",
        )

    def test_pending_and_assemble(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            job_dir = Path(tmpdir)
            translations = job_dir / "translations"
            translations.mkdir()
            chunk1 = translations / "chunk_0001.ja.md"
            chunk2 = translations / "chunk_0002.ja.md"
            chunk1.write_text("## 1\n\n本文A\n", encoding="utf-8")

            manifest = {
                "job_dir": str(job_dir),
                "job_dir_explicit": True,
                "pdf_path": "/tmp/paper.pdf",
                "title_guess": "Test Paper",
                "output_path": str(job_dir / "final" / "paper.ja.md"),
                "chunks": [
                    {
                        "chunk_index": 1,
                        "page_numbers": [1],
                        "source_path": str(job_dir / "source" / "chunk_0001.source.md"),
                        "translation_path": str(chunk1),
                    },
                    {
                        "chunk_index": 2,
                        "page_numbers": [2],
                        "source_path": str(job_dir / "source" / "chunk_0002.source.md"),
                        "translation_path": str(chunk2),
                    },
                ],
            }
            (job_dir / "manifest.json").write_text(json.dumps(manifest), encoding="utf-8")

            self.assertEqual([item["chunk_index"] for item in pending_chunks(job_dir)], [2])
            status_text = format_status(job_dir)
            self.assertIn("Progress: 1/2 chunks translated", status_text)

            with self.assertRaises(RuntimeError):
                assemble_job(job_dir)

            chunk2.write_text("## 2\n\n本文B\n", encoding="utf-8")
            output_path = assemble_job(job_dir)
            self.assertTrue(output_path.exists())
            assembled = output_path.read_text(encoding="utf-8")
            self.assertIn("本文A", assembled)
            self.assertIn("本文B", assembled)


if __name__ == "__main__":
    unittest.main()
