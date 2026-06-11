"""Stage benchmark corpus documents into a neutral /tmp workspace."""

from __future__ import annotations

import shutil
from pathlib import Path
from typing import Any


STAGED_ROOT = Path("/tmp")


def staged_corpus_dir(run_id: str) -> Path:
    return STAGED_ROOT / f"doc-agent-{run_id}"


def doc_folders_for_questions(questions: list[dict[str, Any]]) -> set[str]:
    return {Path(str(question["doc_id"])).stem for question in questions}


def stage_corpus(source_corpus_dir: Path, run_id: str, doc_folders: set[str]) -> Path:
    """Copy selected document folders into /tmp/doc-agent-{run_id}/."""
    source_corpus_dir = source_corpus_dir.resolve()
    dest = staged_corpus_dir(run_id)
    if dest.exists():
        shutil.rmtree(dest)
    dest.mkdir(parents=True)

    missing: list[str] = []
    for folder in sorted(doc_folders):
        source = source_corpus_dir / folder
        if not source.is_dir():
            missing.append(folder)
            continue
        shutil.copytree(source, dest / folder)

    if missing:
        missing_list = ", ".join(missing)
        raise FileNotFoundError(
            f"Missing converted corpus folders in {source_corpus_dir}: {missing_list}. "
            "Run convert_pdfs.py for the documents referenced by this tier."
        )

    return dest


def cleanup_staged_corpus(run_id: str) -> None:
    shutil.rmtree(staged_corpus_dir(run_id), ignore_errors=True)
