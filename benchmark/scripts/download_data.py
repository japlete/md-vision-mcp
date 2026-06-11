"""Download MMLongBench-Doc questions and PDFs from Hugging Face."""

from __future__ import annotations

import argparse
import json
import shutil
import tomllib
import urllib.request
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from datasets import load_dataset
from huggingface_hub import get_hf_file_metadata, hf_hub_url, snapshot_download


ROOT = Path(__file__).resolve().parents[1]
DEFAULT_CONFIG = ROOT / "config" / "default.toml"


def load_config(path: Path) -> dict[str, Any]:
    with path.open("rb") as f:
        return tomllib.load(f)


def json_default(value: Any) -> str:
    return str(value)


def write_json(path: Path, data: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=2, default=json_default)
        f.write("\n")


def write_jsonl(path: Path, rows: list[dict[str, Any]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8") as f:
        for row in rows:
            f.write(json.dumps(row, ensure_ascii=False, default=json_default))
            f.write("\n")


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--config", type=Path, default=DEFAULT_CONFIG)
    parser.add_argument("--repo-id", default=None)
    parser.add_argument("--repo-config", default=None)
    parser.add_argument("--split", default=None)
    parser.add_argument("--revision", default=None)
    parser.add_argument("--raw-dir", type=Path, default=None)
    parser.add_argument(
        "--force",
        action="store_true",
        help="Replace existing question exports and copied PDFs.",
    )
    return parser.parse_args()


def clear_incomplete_downloads(snapshot_dir: Path) -> None:
    cache_dir = snapshot_dir / ".cache" / "huggingface" / "download"
    if not cache_dir.exists():
        return
    for incomplete in cache_dir.rglob("*.incomplete"):
        incomplete.unlink(missing_ok=True)


def download_pdf_http(repo_id: str, repo_path: str, dest: Path) -> None:
    """Download a PDF via the resolved CDN URL, bypassing hub size checks."""
    url = hf_hub_url(repo_id, repo_path, repo_type="dataset")
    metadata = get_hf_file_metadata(url)
    dest.parent.mkdir(parents=True, exist_ok=True)
    request = urllib.request.Request(metadata.location, method="GET")
    with urllib.request.urlopen(request, timeout=120) as response:
        dest.write_bytes(response.read())


def repair_missing_pdfs(
    repo_id: str,
    doc_ids: list[str],
    snapshot_dir: Path,
    documents_dir: Path,
    force: bool,
) -> list[str]:
    repaired: list[str] = []
    for doc_id in doc_ids:
        dest = documents_dir / doc_id
        if dest.exists() and not force:
            repaired.append(doc_id)
            continue

        snapshot_pdf = snapshot_dir / "documents" / doc_id
        if snapshot_pdf.exists() and not force:
            shutil.copy2(snapshot_pdf, dest)
            repaired.append(doc_id)
            continue

        repo_path = f"documents/{doc_id}"
        download_pdf_http(repo_id, repo_path, snapshot_pdf)
        shutil.copy2(snapshot_pdf, dest)
        repaired.append(doc_id)
    return repaired


def copy_pdfs(snapshot_dir: Path, documents_dir: Path, force: bool) -> list[str]:
    documents_dir.mkdir(parents=True, exist_ok=True)
    copied: list[str] = []
    for pdf in sorted(snapshot_dir.rglob("*.pdf")):
        dest = documents_dir / pdf.name
        if dest.exists() and not force:
            copied.append(dest.name)
            continue
        shutil.copy2(pdf, dest)
        copied.append(dest.name)
    return copied


def main() -> None:
    args = parse_args()
    config = load_config(args.config)

    dataset_cfg = config["dataset"]
    paths_cfg = config["paths"]

    repo_id = args.repo_id or dataset_cfg["repo_id"]
    repo_config = args.repo_config or dataset_cfg.get("repo_config")
    split = args.split or dataset_cfg.get("split", "train")
    revision = args.revision or dataset_cfg.get("revision", "main")
    raw_dir = (args.raw_dir or ROOT / paths_cfg["raw_dir"]).resolve()
    documents_dir = (raw_dir / "documents") if args.raw_dir else (ROOT / paths_cfg["documents_dir"]).resolve()
    snapshot_dir = raw_dir / "hf_snapshot"

    raw_dir.mkdir(parents=True, exist_ok=True)

    snapshot_path = snapshot_dir
    try:
        snapshot_path = Path(
            snapshot_download(
                repo_id=repo_id,
                repo_type="dataset",
                revision=revision,
                local_dir=snapshot_dir,
                allow_patterns=["**/*.pdf", "**/*.json", "**/*.jsonl", "README.md"],
            )
        )
    except (OSError, RuntimeError) as exc:
        clear_incomplete_downloads(snapshot_dir)
        print(
            "Warning: snapshot_download failed partway through; "
            f"will repair known-bad files via HTTP fallback. ({exc})"
        )

    if repo_config:
        dataset = load_dataset(repo_id, repo_config, split=split, revision=revision)
    else:
        dataset = load_dataset(repo_id, split=split, revision=revision)
    rows = [dict(row, question_id=i) for i, row in enumerate(dataset)]

    write_json(raw_dir / "questions.json", rows)
    write_jsonl(raw_dir / "questions.jsonl", rows)
    copied_pdfs = copy_pdfs(snapshot_path, documents_dir, force=args.force)

    doc_ids = sorted({str(row.get("doc_id", "")) for row in rows if row.get("doc_id")})
    missing_pdfs = [doc_id for doc_id in doc_ids if not (documents_dir / doc_id).exists()]
    if missing_pdfs:
        repaired = repair_missing_pdfs(
            repo_id,
            missing_pdfs,
            snapshot_path,
            documents_dir,
            force=args.force,
        )
        copied_pdfs = sorted(set(copied_pdfs) | set(repaired))
        missing_pdfs = [
            doc_id for doc_id in doc_ids if not (documents_dir / doc_id).exists()
        ]

    document_count = sum(1 for doc_id in doc_ids if (documents_dir / doc_id).exists())

    manifest = {
        "downloaded_at": datetime.now(timezone.utc).isoformat(),
        "repo_id": repo_id,
        "repo_config": repo_config,
        "split": split,
        "requested_revision": revision,
        "snapshot_dir": str(snapshot_path),
        "question_count": len(rows),
        "document_count": document_count,
        "missing_pdf_count": len(missing_pdfs),
        "missing_pdfs": missing_pdfs,
    }
    write_json(raw_dir / "download_manifest.json", manifest)

    print(
        f"Downloaded {len(rows)} questions and {document_count} PDFs to {raw_dir}"
    )
    if missing_pdfs:
        print(f"Warning: {len(missing_pdfs)} doc_id values have no matching PDF.")


if __name__ == "__main__":
    main()
