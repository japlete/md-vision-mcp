"""Normalize MinerU markdown output into the benchmark corpus layout."""

from __future__ import annotations

import argparse
import re
import shutil
from pathlib import Path


MARKDOWN_IMAGE_RE = re.compile(r"!\[([^\]]*)\]\(([^)]+)\)")
HTML_IMAGE_RE = re.compile(
    r"(<img\b[^>]*\bsrc=[\"'])([^\"']+)([\"'][^>]*>)", re.IGNORECASE
)


def find_markdown_file(mineru_output: Path) -> Path:
    candidates = [p for p in mineru_output.rglob("*.md") if p.is_file()]
    if not candidates:
        raise FileNotFoundError(f"No markdown files found under {mineru_output}")
    return max(candidates, key=lambda p: p.stat().st_size)


def unique_asset_path(assets_dir: Path, filename: str) -> Path:
    candidate = assets_dir / filename
    if not candidate.exists():
        return candidate
    stem = candidate.stem
    suffix = candidate.suffix
    i = 2
    while True:
        next_candidate = assets_dir / f"{stem}-{i}{suffix}"
        if not next_candidate.exists():
            return next_candidate
        i += 1


def rewrite_asset(src: str, markdown_dir: Path, assets_dir: Path) -> str:
    if re.match(r"^[a-zA-Z][a-zA-Z0-9+.-]*:", src):
        return src

    raw_src = src.strip()
    source = (markdown_dir / raw_src).resolve()
    if not source.exists() or not source.is_file():
        return src

    assets_dir.mkdir(parents=True, exist_ok=True)
    dest = unique_asset_path(assets_dir, source.name)
    shutil.copy2(source, dest)
    return f"assets/{dest.name}"


def normalize_markdown(markdown_path: Path, corpus_doc_dir: Path, doc_id: str) -> Path:
    text = markdown_path.read_text(encoding="utf-8")
    assets_dir = corpus_doc_dir / "assets"

    def markdown_repl(match: re.Match[str]) -> str:
        alt, src = match.groups()
        rewritten = rewrite_asset(src, markdown_path.parent, assets_dir)
        return f"![{alt}]({rewritten})"

    def html_repl(match: re.Match[str]) -> str:
        prefix, src, suffix = match.groups()
        rewritten = rewrite_asset(src, markdown_path.parent, assets_dir)
        return f"{prefix}{rewritten}{suffix}"

    text = MARKDOWN_IMAGE_RE.sub(markdown_repl, text)
    text = HTML_IMAGE_RE.sub(html_repl, text)

    if not text.startswith("---\n"):
        text = f"---\ndoc_id: {doc_id}\nsource: MMLongBench-Doc\n---\n\n{text}"

    corpus_doc_dir.mkdir(parents=True, exist_ok=True)
    output = corpus_doc_dir / "index.md"
    output.write_text(text, encoding="utf-8")
    return output


def postprocess_document(mineru_output: Path, corpus_doc_dir: Path, doc_id: str) -> Path:
    markdown_path = find_markdown_file(mineru_output)
    return normalize_markdown(markdown_path, corpus_doc_dir, doc_id)


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("mineru_output", type=Path)
    parser.add_argument("corpus_doc_dir", type=Path)
    parser.add_argument("--doc-id", required=True)
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    output = postprocess_document(args.mineru_output, args.corpus_doc_dir, args.doc_id)
    print(output)


if __name__ == "__main__":
    main()
