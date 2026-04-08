---
name: paper-translator
description: Translate academic PDFs into faithful Japanese Markdown with equations preserved by using Codex itself for chunk-by-chunk translation and local helper scripts for extraction, resume, and assembly. Use when the user wants a paper, appendix, supplement, or technical PDF translated without API charges or summary drift.
---

# Paper Translator

Use this skill when the user wants a PDF paper translated faithfully into Japanese Markdown, including appendix or supplement pages, while staying inside the ChatGPT Plus and Codex workflow.

## Workflow

1. Confirm the absolute PDF path.
2. Prepare a local job:

```bash
uv run python /Users/sugawara/Documents/PaperTranslater/codex_paper.py prepare /absolute/path/to/paper.pdf
```

3. Check progress any time:

```bash
uv run python /Users/sugawara/Documents/PaperTranslater/codex_paper.py status /absolute/path/to/job-dir
```

4. Translate pending chunks by reading each `source/chunk_XXXX.source.md` file and writing the Japanese Markdown to the matching `translations/chunk_XXXX.ja.md` path.
5. Translate faithfully and completely. Never summarize. Preserve equations with `$...$` and `$$...$$` where possible, keep section structure explicit, include supplement text when present, and keep the paper title in English without translating it.
6. For display equations, write `$$` on its own line, the equation body on following lines with no indentation, and the closing `$$` on its own line.
7. For large papers, process chunks in small batches and resume later. The local job keeps state, so continuing later is safe.
8. If the conversation grows too long, continue in a fresh thread and resume from `status` using the existing job directory.
9. When all chunks are translated, assemble the final Markdown:

```bash
uv run python /Users/sugawara/Documents/PaperTranslater/codex_paper.py assemble /absolute/path/to/job-dir
```

10. Report the final Markdown path. Do not paraphrase the paper in chat unless the user asks.

## Notes

- This workflow does not require `OPENAI_API_KEY`.
- This skill is not a background watcher. It runs when Codex is explicitly asked to handle a PDF path or an existing job.
- The helper scripts store extracted text, rendered page images, source chunk files, and translated chunk files under `.paper-translator-jobs/`, so rerunning resumes work.
- The source chunk files list absolute image paths for the rendered pages when visual cross-checking is needed.
- The final Markdown should contain translated content only; it is meant to be the paper translation, not a summary.
