"""Report PDF page counts and cloud API eligibility."""

from __future__ import annotations

import argparse
import json
import sys
import tomllib
from pathlib import Path
from typing import Any

try:
    from .mineru_cloud import PdfLimits, check_pdf_limits, pdf_page_count
except ImportError:
    sys.path.insert(0, str(Path(__file__).resolve().parent))
    from mineru_cloud import PdfLimits, check_pdf_limits, pdf_page_count


ROOT = Path(__file__).resolve().parents[1]
DEFAULT_CONFIG = ROOT / "config" / "default.toml"


def load_config(path: Path) -> dict[str, Any]:
    with path.open("rb") as f:
        return tomllib.load(f)


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--config", type=Path, default=DEFAULT_CONFIG)
    parser.add_argument("--documents-dir", type=Path, default=None)
    parser.add_argument("--json", action="store_true")
    args = parser.parse_args()

    config = load_config(args.config)
    documents_dir = (
        args.documents_dir or ROOT / config["paths"]["documents_dir"]
    ).resolve()
    mineru_cfg = config["mineru"]
    limits = PdfLimits(
        max_pages=int(mineru_cfg.get("max_pages", 200)),
        max_size_bytes=int(mineru_cfg.get("max_file_size_mb", 200)) * 1024 * 1024,
    )

    rows: list[dict[str, Any]] = []
    for pdf in sorted(documents_dir.glob("*.pdf")):
        pages = pdf_page_count(pdf)
        reason = check_pdf_limits(pdf, limits)
        rows.append(
            {
                "name": pdf.name,
                "pages": pages,
                "size_mb": round(pdf.stat().st_size / (1024 * 1024), 2),
                "eligible": reason is None,
                "skip_reason": reason,
            }
        )

    eligible = [r for r in rows if r["eligible"]]
    ineligible = [r for r in rows if not r["eligible"]]

    if args.json:
        print(
            json.dumps(
                {
                    "total": len(rows),
                    "eligible": len(eligible),
                    "ineligible": len(ineligible),
                    "max_pages": limits.max_pages,
                    "documents": rows,
                },
                indent=2,
            )
        )
        return

    print(f"Documents: {len(rows)}")
    print(f"Eligible (≤{limits.max_pages} pages, ≤{limits.max_size_bytes // (1024*1024)} MB): {len(eligible)}")
    print(f"Ineligible: {len(ineligible)}")
    if ineligible:
        print("\nIneligible:")
        for row in sorted(ineligible, key=lambda r: -r["pages"]):
            print(f"  {row['pages']:4d} pages  {row['size_mb']:6.1f} MB  {row['name']}")
            print(f"         {row['skip_reason']}")


if __name__ == "__main__":
    main()
