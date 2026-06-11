# MMLongBench-Doc Benchmark

This workspace runs an A/B agentic RAG comparison on MMLongBench-Doc:

- `baseline`: a Deep Agents agent with filesystem-backed document access.
- `mdvision`: the same agent plus the local `md-vision` MCP tools
  (`index_md`, `read_md_with_images`).

The task prompt is neutral and does not mention benchmarks or the treatment
arm. Each question runs in a fresh agent thread, returns a structured short
answer, and is scored with ANLS logic adapted from MMLongBench-Doc. When ANLS
is below perfect confidence on string-like answers, a Gemini judge on OpenRouter
(`google/gemini-3.5-flash`, flex tier) checks semantic equivalence and can
upgrade the score to 1.0. Disable with `--no-judge`.

## Setup

From this directory:

```bash
uv sync
```

Before running the `mdvision` arm, build the MCP server from the repo root:

```bash
npm run build
```

Create `benchmark/.env`:

```bash
OPENROUTER_API_KEY=...
MINERU_API_TOKEN=...   # from https://mineru.net/apiManage
```

The default model and paths live in `config/default.toml`.

## Download Data

```bash
uv run python scripts/download_data.py
```

This downloads the Hugging Face dataset snapshot and writes:

- `data/raw/questions.jsonl`
- `data/raw/questions.json`
- `data/raw/documents/*.pdf`
- `data/raw/download_manifest.json`

The script records the actual question count from the resolved Hugging Face
revision. Treat that count as the source of truth for run planning.

## Convert PDFs

PDF conversion uses the [MinerU cloud API](https://mineru.net/apiManage/docs).
Documents over 200 pages or 200 MB are skipped automatically (see page report).

```bash
uv run python scripts/page_report.py
uv run python scripts/convert_pdfs.py --limit 2
uv run python scripts/convert_pdfs.py
```

Converted documents are written to `data/corpus/{doc_stem}/index.md` with image
assets under `data/corpus/{doc_stem}/assets/`. Use `--force` to reconvert docs
that already have corpus output (for example after changing `model_version`).

## Run

Smoke test one arm:

```bash
uv run python -m harness.runner --arm baseline --tier smoke --seed 42
```

Compare both arms:

```bash
uv run python -m harness.runner --arm both --tier pilot --seed 42
```

Generate an aggregate report:

```bash
uv run python -m harness.report --run-dir results/latest
```

## License

See `NOTICE.md`. MMLongBench-Doc data is CC BY-NC 4.0 and is downloaded into
gitignored local directories only. Scoring logic is adapted from upstream
Apache-2.0 code.
