"""MinerU cloud API client (https://mineru.net/api/v4)."""

from __future__ import annotations

import hashlib
import time
import zipfile
from dataclasses import dataclass
from pathlib import Path
from typing import Any

import requests
from pypdf import PdfReader


DEFAULT_API_BASE = "https://mineru.net/api/v4"
MAX_CLOUD_DATA_ID_LEN = 128
TERMINAL_STATES = {"done", "failed"}
ACTIVE_STATES = {"waiting-file", "pending", "running", "converting"}


class MinerUCloudError(RuntimeError):
    """Raised when the MinerU cloud API returns an error."""


@dataclass(frozen=True)
class PdfLimits:
    max_pages: int = 200
    max_size_bytes: int = 200 * 1024 * 1024


def pdf_page_count(pdf: Path) -> int:
    return len(PdfReader(pdf).pages)


def check_pdf_limits(pdf: Path, limits: PdfLimits) -> str | None:
    size = pdf.stat().st_size
    if size > limits.max_size_bytes:
        size_mb = size / (1024 * 1024)
        max_mb = limits.max_size_bytes / (1024 * 1024)
        return f"file size {size_mb:.1f} MB exceeds {max_mb:.0f} MB limit"
    pages = pdf_page_count(pdf)
    if pages > limits.max_pages:
        return f"page count {pages} exceeds {limits.max_pages}-page limit"
    return None


def cloud_data_id(doc_stem: str, *, max_len: int = MAX_CLOUD_DATA_ID_LEN) -> str:
    """MinerU data_id must be <= 128 chars; hash long stems deterministically."""
    if len(doc_stem) <= max_len:
        return doc_stem
    digest = hashlib.sha256(doc_stem.encode("utf-8")).hexdigest()
    return f"doc-{digest}"


class MinerUCloudClient:
    def __init__(
        self,
        token: str,
        *,
        api_base: str = DEFAULT_API_BASE,
        model_version: str = "vlm",
        poll_interval_seconds: float = 10.0,
        poll_timeout_seconds: float = 3600.0,
        session: requests.Session | None = None,
    ) -> None:
        self.token = token
        self.api_base = api_base.rstrip("/")
        self.model_version = model_version
        self.poll_interval_seconds = poll_interval_seconds
        self.poll_timeout_seconds = poll_timeout_seconds
        self.session = session or requests.Session()

    @property
    def _headers(self) -> dict[str, str]:
        return {
            "Authorization": f"Bearer {self.token}",
            "Content-Type": "application/json",
            "Accept": "*/*",
        }

    def _check_response(self, response: requests.Response) -> dict[str, Any]:
        response.raise_for_status()
        payload = response.json()
        if payload.get("code") != 0:
            raise MinerUCloudError(payload.get("msg") or f"API error: {payload}")
        return payload

    def request_upload(self, pdf: Path, *, data_id: str) -> tuple[str, str]:
        url = f"{self.api_base}/file-urls/batch"
        body = {
            "files": [{"name": pdf.name, "data_id": data_id}],
            "model_version": self.model_version,
        }
        payload = self._check_response(
            self.session.post(url, headers=self._headers, json=body, timeout=60)
        )
        data = payload["data"]
        return data["batch_id"], data["file_urls"][0]

    def upload_file(self, upload_url: str, pdf: Path) -> None:
        with pdf.open("rb") as handle:
            response = self.session.put(upload_url, data=handle, timeout=600)
        if response.status_code != 200:
            raise MinerUCloudError(
                f"upload failed for {pdf.name}: HTTP {response.status_code}"
            )

    def poll_batch(self, batch_id: str) -> dict[str, Any]:
        url = f"{self.api_base}/extract-results/batch/{batch_id}"
        deadline = time.monotonic() + self.poll_timeout_seconds
        while time.monotonic() < deadline:
            payload = self._check_response(
                self.session.get(url, headers=self._headers, timeout=60)
            )
            results = payload["data"]["extract_result"]
            if isinstance(results, dict):
                results = [results]
            if not results:
                time.sleep(self.poll_interval_seconds)
                continue

            result = results[0]
            state = result.get("state", "")
            if state in TERMINAL_STATES:
                if state == "failed":
                    raise MinerUCloudError(
                        result.get("err_msg") or f"parse failed (state={state})"
                    )
                return result
            if state not in ACTIVE_STATES:
                raise MinerUCloudError(f"unexpected task state: {state}")

            progress = result.get("extract_progress") or {}
            extracted = progress.get("extracted_pages")
            total = progress.get("total_pages")
            if extracted is not None and total is not None:
                print(f"  parsing {extracted}/{total} pages...", flush=True)
            time.sleep(self.poll_interval_seconds)

        raise MinerUCloudError(
            f"polling timed out after {self.poll_timeout_seconds:.0f}s (batch_id={batch_id})"
        )

    def download_result_zip(self, zip_url: str, dest_zip: Path) -> None:
        dest_zip.parent.mkdir(parents=True, exist_ok=True)
        with self.session.get(zip_url, stream=True, timeout=600) as response:
            response.raise_for_status()
            with dest_zip.open("wb") as handle:
                for chunk in response.iter_content(chunk_size=1024 * 1024):
                    if chunk:
                        handle.write(chunk)

    def extract_zip(self, zip_path: Path, output_dir: Path) -> None:
        if output_dir.exists():
            for child in output_dir.iterdir():
                if child.is_dir():
                    for nested in child.rglob("*"):
                        if nested.is_file():
                            nested.unlink()
                    for nested in sorted(child.rglob("*"), reverse=True):
                        if nested.is_dir():
                            nested.rmdir()
                    child.rmdir()
                else:
                    child.unlink()
        output_dir.mkdir(parents=True, exist_ok=True)
        with zipfile.ZipFile(zip_path) as archive:
            archive.extractall(output_dir)

    def parse_pdf(self, pdf: Path, work_dir: Path) -> Path:
        output_dir = work_dir / pdf.stem
        zip_path = work_dir / f"{pdf.stem}.zip"
        data_id = cloud_data_id(pdf.stem)

        batch_id, upload_url = self.request_upload(pdf, data_id=data_id)
        print(f"  batch_id={batch_id}, uploading...", flush=True)
        self.upload_file(upload_url, pdf)

        print("  waiting for parse...", flush=True)
        result = self.poll_batch(batch_id)
        zip_url = result.get("full_zip_url")
        if not zip_url:
            raise MinerUCloudError("parse completed but full_zip_url is missing")

        print("  downloading result...", flush=True)
        self.download_result_zip(zip_url, zip_path)
        self.extract_zip(zip_path, output_dir)
        return output_dir
