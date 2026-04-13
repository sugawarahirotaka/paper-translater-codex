# PaperTranslater

`PaperTranslater` は、論文 PDF をページまたは小チャンクに分割し、Codex に逐語訳させながら日本語 Markdown に再構成するためのローカル補助ツールです。

このリポジトリの主目的は、`ChatGPT Plus + Codex` の範囲で翻訳作業を進めやすくすることです。PDF の分割、抽出、再開、結合はローカルで行い、翻訳そのものは Codex に担当させます。

## Features

- PDF を小さな chunk に分割して処理するため、長い論文でも途中再開しやすい
- `pdftotext` による抽出テキストとページ画像を併用できる
- `prepare`, `status`, `assemble` の 3 段階で進捗を管理できる
- appendix や supplement を含む PDF にもそのまま対応しやすい
- 出力 Markdown は翻訳本文中心で整理しやすい

## Requirements

- Python 3.11+
- `uv`
- `pdftotext`
- `pdftoppm`

`pdftotext` と `pdftoppm` はどちらも Poppler に含まれます。MacPorts では次で入ります:

```bash
sudo port install poppler
```

## Quick Start

すべてのコマンドはリポジトリ直下で実行します。

1. リポジトリ直下でテストを確認する

```bash
UV_CACHE_DIR=.uv-cache uv run python -m unittest discover -s tests
```

2. PDF を翻訳ジョブに変換する

```bash
UV_CACHE_DIR=.uv-cache uv run python codex_paper.py prepare "/absolute/path/to/paper.pdf"
```

3. 進捗を確認する

```bash
UV_CACHE_DIR=.uv-cache uv run python codex_paper.py status "/absolute/path/to/job-dir"
```

4. Codex に `source/chunk_XXXX.source.md` を読ませて、対応する `translations/chunk_XXXX.ja.md` を埋める

5. 全 chunk が埋まったら最終 Markdown を結合する

```bash
UV_CACHE_DIR=.uv-cache uv run python codex_paper.py assemble "/absolute/path/to/job-dir"
```

`assemble` 実行後、完成版 Markdown は job ディレクトリ内の `final/` に保存され、さらに Obsidian 用の
`/Users/sugawara/Library/Mobile Documents/iCloud~md~obsidian/Documents/Obsidian_vault/02_Read-only/Papers`
にも同名でコピーされます。このコピー先パスは現状 `paper_translator/codex_job.py` にハードコードされています。

## Codex Skill はどこまで自動か

`paper-translator` skill は、Codex との会話の中で使うための手順定義です。常駐プロセスではないので、PDF が置かれたディレクトリを勝手に監視して自動実行することはありません。

動作は次の 2 パターンです。

- `Codex に依頼する場合`
  - PDF の絶対パスを伝えて、「この PDF を翻訳して」「この job を続きから回して」と依頼すれば、Codex が `prepare`, chunk 翻訳, `assemble` を会話内で代行できます。
  - この場合、通常は自分でコマンドを打つ必要はありません。
- `自分でローカル実行する場合`
  - Codex を使わずに進めるなら、自分で `uv run python codex_paper.py ...` を実行します。
  - このリポジトリの CLI は、`prepare`, `status`, `assemble` のみを担当します。翻訳本文そのものは Codex に書かせる前提です。

つまり、`skills により勝手に回る` ではなく、`Codex に依頼すれば Codex が回す` です。ローカル単体では自動監視も自動翻訳も行いません。

## How To Run

出力先を明示したい場合:

```bash
UV_CACHE_DIR=.uv-cache uv run python codex_paper.py prepare "/absolute/path/to/paper.pdf" \
  --output "/absolute/path/to/output/paper.ja.md"
```

2 ページずつ chunk 化したい場合:

```bash
UV_CACHE_DIR=.uv-cache uv run python codex_paper.py prepare "/absolute/path/to/paper.pdf" \
  --pages-per-chunk 2
```

特定ページ範囲だけ試したい場合:

```bash
UV_CACHE_DIR=.uv-cache uv run python codex_paper.py prepare "/absolute/path/to/paper.pdf" \
  --start-page 1 \
  --end-page 2 \
  --pages-per-chunk 2
```

## Translation Rules

- 要約ではなく、見えている本文を逐語的に訳す
- 論文タイトルは和訳せず、英語のまま残す
- 見出し構造は Markdown の見出しとして明確に分ける
- 数式は可能な限り `$...$` または `$$ ... $$` で整える
- display math は `$$` を単独行に置き、数式本体をインデントしない
- supplement や appendix があればそこまで処理する

## Long Papers And Context

長い論文では、Codex に全 chunk を 1 会話で処理させ続けるより、数 chunk ごとに会話を切り替えた方が安定します。

- 5 から 10 chunk ほど処理したら、会話を compact するか新しい会話に切り替える
- 新しい会話では、既存 job ディレクトリを渡して `status` から再開する
- job 状態は `.paper-translator-jobs/` に保存されているので、会話を切り替えても進捗は失われない

再開例:

```bash
UV_CACHE_DIR=.uv-cache uv run python codex_paper.py status "/absolute/path/to/existing-job-dir"
```

## Repository Layout

- `codex_paper.py`: Codex 向け CLI エントリポイント
- `paper_translator/codex_cli.py`: `prepare`, `status`, `assemble` の CLI 実装
- `paper_translator/codex_job.py`: ジョブ生成、進捗管理、結合
- `paper_translator/pdf_tools.py`: PDF のページ抽出と画像生成
- `paper_translator/models.py`: job 内部で使うデータ構造
- `paper_translator/text_utils.py`: slug や Markdown 整形の小物関数
- `.agents/skills/paper-translator/`: Codex skill 定義

## Codex Skill

同じワークフローを Codex から再利用するための skill を `.agents/skills/paper-translator/` に同梱しています。
