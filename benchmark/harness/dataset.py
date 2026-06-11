"""Question filtering against locally available benchmark documents."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any


def downloaded_doc_ids(documents_dir: Path) -> set[str]:
    documents_dir = documents_dir.resolve()
    if not documents_dir.is_dir():
        return set()
    return {path.name for path in documents_dir.glob("*.pdf")}


def corpus_ready_doc_ids(corpus_dir: Path) -> set[str]:
    corpus_dir = corpus_dir.resolve()
    if not corpus_dir.is_dir():
        return set()
    return {
        doc_dir.name
        for doc_dir in corpus_dir.iterdir()
        if doc_dir.is_dir() and (doc_dir / "index.md").is_file()
    }


def filter_questions_for_available_docs(
    questions: list[dict[str, Any]],
    *,
    documents_dir: Path,
    corpus_dir: Path,
) -> tuple[list[dict[str, Any]], dict[str, Any]]:
    """Keep questions whose doc has a downloaded PDF and converted corpus."""
    downloaded = downloaded_doc_ids(documents_dir)
    corpus_ready = corpus_ready_doc_ids(corpus_dir)

    kept: list[dict[str, Any]] = []
    excluded_missing_pdf = 0
    excluded_missing_corpus = 0

    for question in questions:
        doc_id = str(question.get("doc_id", ""))
        if doc_id not in downloaded:
            excluded_missing_pdf += 1
            continue
        doc_stem = Path(doc_id).stem
        if doc_stem not in corpus_ready:
            excluded_missing_corpus += 1
            continue
        kept.append(question)

    stats = {
        "questions_total": len(questions),
        "questions_kept": len(kept),
        "excluded_missing_pdf": excluded_missing_pdf,
        "excluded_missing_corpus": excluded_missing_corpus,
        "downloaded_doc_count": len(downloaded),
        "corpus_ready_doc_count": len(corpus_ready),
        "documents_dir": str(documents_dir.resolve()),
        "corpus_dir": str(corpus_dir.resolve()),
    }
    return kept, stats


def load_download_manifest(manifest_path: Path) -> dict[str, Any] | None:
    if not manifest_path.is_file():
        return None
    with manifest_path.open("r", encoding="utf-8") as handle:
        return json.load(handle)
