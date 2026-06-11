"""Convert MMLongBench-Doc PDFs to markdown via the MinerU cloud API."""

from __future__ import annotations

import argparse
import json
import os
import sys
import tomllib
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from dotenv import load_dotenv

try:
    from .mineru_cloud import MinerUCloudClient, PdfLimits, check_pdf_limits
    from .postprocess import postprocess_document
except ImportError:
    sys.path.insert(0, str(Path(__file__).resolve().parent))
    from mineru_cloud import MinerUCloudClient, PdfLimits, check_pdf_limits
    from postprocess import postprocess_document


ROOT = Path(__file__).resolve().parents[1]
DEFAULT_CONFIG = ROOT / "config" / "default.toml"


def load_config(path: Path) -> dict[str, Any]:
    with path.open("rb") as f:
        return tomllib.load(f)


def read_manifest(path: Path) -> dict[str, Any]:
    if not path.exists():
        return {"documents": {}}
    with path.open("r", encoding="utf-8") as f:
        return json.load(f)


def write_manifest(path: Path, manifest: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8") as f:
        json.dump(manifest, f, ensure_ascii=False, indent=2)
        f.write("\n")


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--config", type=Path, default=DEFAULT_CONFIG)
    parser.add_argument("--documents-dir", type=Path, default=None)
    parser.add_argument("--corpus-dir", type=Path, default=None)
    parser.add_argument("--work-dir", type=Path, default=None)
    parser.add_argument("--model-version", default=None)
    parser.add_argument("--doc-id", action="append", default=[])
    parser.add_argument("--limit", type=int, default=None)
    parser.add_argument(
        "--include-over-limit",
        action="store_true",
        help="attempt PDFs that exceed cloud page/size limits",
    )
    parser.add_argument(
        "--force",
        action="store_true",
        help="reconvert even when corpus output already exists",
    )
    parser.add_argument("--dry-run", action="store_true")
    return parser.parse_args()


def convert_pdf(
    pdf: Path,
    corpus_dir: Path,
    work_dir: Path,
    client: MinerUCloudClient,
    limits: PdfLimits,
    force: bool,
    dry_run: bool,
    include_over_limit: bool,
) -> dict[str, Any]:
    doc_id = pdf.name
    doc_stem = pdf.stem
    corpus_doc_dir = corpus_dir / doc_stem
    index_path = corpus_doc_dir / "index.md"
    if index_path.exists() and not force:
        return {"status": "skipped", "output": str(index_path)}

    limit_reason = check_pdf_limits(pdf, limits)
    if limit_reason and not include_over_limit:
        return {"status": "skipped", "reason": limit_reason}

    if dry_run:
        return {
            "status": "dry-run",
            "model_version": client.model_version,
            "limit_reason": limit_reason,
        }

    try:
        mineru_output = client.parse_pdf(pdf, work_dir)
        output = postprocess_document(mineru_output, corpus_doc_dir, doc_id)
        return {
            "status": "completed",
            "model_version": client.model_version,
            "output": str(output),
            "limit_reason": limit_reason,
        }
    except Exception as exc:  # noqa: BLE001 - manifest should capture any failure.
        return {"status": "failed", "error": str(exc)}


def main() -> None:
    load_dotenv(ROOT / ".env")
    args = parse_args()
    config = load_config(args.config)
    paths_cfg = config["paths"]
    mineru_cfg = config["mineru"]

    documents_dir = (args.documents_dir or ROOT / paths_cfg["documents_dir"]).resolve()
    corpus_dir = (args.corpus_dir or ROOT / paths_cfg["corpus_dir"]).resolve()
    work_dir = (args.work_dir or ROOT / mineru_cfg["work_dir"]).resolve()
    manifest_path = work_dir / "conversion_manifest.json"

    token = os.environ.get("MINERU_API_TOKEN", "").strip()
    if not token and not args.dry_run:
        raise SystemExit(
            "MINERU_API_TOKEN is required. "
            "Add it to benchmark/.env (create a token at https://mineru.net/apiManage)."
        )

    model_version = args.model_version or mineru_cfg.get("model_version", "vlm")
    limits = PdfLimits(
        max_pages=int(mineru_cfg.get("max_pages", 200)),
        max_size_bytes=int(mineru_cfg.get("max_file_size_mb", 200)) * 1024 * 1024,
    )

    client: MinerUCloudClient | None = None
    if token:
        client = MinerUCloudClient(
            token,
            api_base=mineru_cfg.get("api_base_url", "https://mineru.net/api/v4"),
            model_version=model_version,
            poll_interval_seconds=float(mineru_cfg.get("poll_interval_seconds", 10)),
            poll_timeout_seconds=float(mineru_cfg.get("poll_timeout_seconds", 3600)),
        )

    manifest = read_manifest(manifest_path)
    manifest.update(
        {
            "updated_at": datetime.now(timezone.utc).isoformat(),
            "model_version": model_version,
            "documents_dir": str(documents_dir),
            "corpus_dir": str(corpus_dir),
        }
    )

    selected = set(args.doc_id)
    pdfs = sorted(documents_dir.glob("*.pdf"))
    if selected:
        pdfs = [pdf for pdf in pdfs if pdf.name in selected or pdf.stem in selected]
    if args.limit is not None:
        pdfs = pdfs[: args.limit]

    if not pdfs:
        raise SystemExit(f"No PDFs found in {documents_dir}")

    for pdf in pdfs:
        print(f"{pdf.name}:", flush=True)
        if client is None:
            client = MinerUCloudClient(
                "dry-run",
                api_base=mineru_cfg.get("api_base_url", "https://mineru.net/api/v4"),
                model_version=model_version,
            )
        result = convert_pdf(
            pdf=pdf,
            corpus_dir=corpus_dir,
            work_dir=work_dir,
            client=client,
            limits=limits,
            force=args.force,
            dry_run=args.dry_run,
            include_over_limit=args.include_over_limit,
        )
        manifest["documents"][pdf.name] = {
            **result,
            "updated_at": datetime.now(timezone.utc).isoformat(),
        }
        write_manifest(manifest_path, manifest)
        detail = result.get("reason") or result.get("error") or result.get("output", "")
        print(f"  {result['status']}{f' ({detail})' if detail else ''}")


if __name__ == "__main__":
    main()
