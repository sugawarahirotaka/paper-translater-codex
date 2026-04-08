from __future__ import annotations

import argparse
import sys
from pathlib import Path

from .codex_job import CodexJobConfig, assemble_job, format_status, prepare_job


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Prepare and assemble a Codex-driven paper translation job without API calls."
    )
    subparsers = parser.add_subparsers(dest="command", required=True)

    prepare = subparsers.add_parser("prepare", help="Extract a PDF into chunk files for Codex.")
    prepare.add_argument("pdf", type=Path, help="Path to the input PDF.")
    prepare.add_argument("--job-dir", type=Path, help="Directory for the prepared job.")
    prepare.add_argument("--output", type=Path, help="Path to the final assembled Markdown.")
    prepare.add_argument("--pages-per-chunk", type=int, default=1, help="Pages per translation chunk.")
    prepare.add_argument("--start-page", type=int, help="First page to include.")
    prepare.add_argument("--end-page", type=int, help="Last page to include.")
    prepare.add_argument("--dpi", type=int, default=180, help="PNG render DPI.")
    prepare.add_argument("--force", action="store_true", help="Rebuild the job even if it exists.")

    status = subparsers.add_parser("status", help="Show pending and completed chunks.")
    status.add_argument("job_dir", type=Path, help="Prepared job directory.")

    assemble = subparsers.add_parser("assemble", help="Combine translated chunks into one Markdown file.")
    assemble.add_argument("job_dir", type=Path, help="Prepared job directory.")
    assemble.add_argument(
        "--allow-partial",
        action="store_true",
        help="Assemble even if some chunks are still missing.",
    )
    return parser


def main(argv: list[str] | None = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)

    if args.command == "prepare":
        if args.pages_per_chunk < 1:
            parser.error("--pages-per-chunk must be >= 1")
        job_dir = prepare_job(
            CodexJobConfig(
                pdf_path=args.pdf,
                job_dir=args.job_dir,
                pages_per_chunk=args.pages_per_chunk,
                start_page=args.start_page,
                end_page=args.end_page,
                dpi=args.dpi,
                output_path=args.output,
                force=args.force,
            )
        )
        print(job_dir)
        return 0

    if args.command == "status":
        print(format_status(args.job_dir), end="")
        return 0

    if args.command == "assemble":
        output_path = assemble_job(args.job_dir, allow_partial=args.allow_partial)
        print(output_path)
        return 0

    print(f"Unknown command: {args.command}", file=sys.stderr)
    return 1

