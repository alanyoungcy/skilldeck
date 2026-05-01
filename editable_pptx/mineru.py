"""MinerU v4 API: single-page PDF upload, poll, download ZIP, extract layout files."""

from __future__ import annotations

import io
import logging
import time
import uuid
import zipfile
from pathlib import Path
from typing import Optional

import requests
from PIL import Image

logger = logging.getLogger(__name__)


class MinerUError(Exception):
    pass


def image_to_pdf(image_path: str, pdf_path: Path) -> None:
    """Single-page PDF for MinerU upload. Prefer img2pdf; fall back to Pillow if missing or broken."""
    pdf_path.parent.mkdir(parents=True, exist_ok=True)
    primary_err: Exception | None = None

    try:
        import img2pdf

        with open(pdf_path, "wb") as f:
            f.write(img2pdf.convert(image_path))
        return
    except ImportError as e:
        primary_err = e
        logger.info("img2pdf not available (%s); using Pillow for PDF", e)
    except Exception as e:
        primary_err = e
        logger.warning("img2pdf failed (%s); trying Pillow", e)

    try:
        im = Image.open(image_path)
        if im.mode in ("RGBA", "P"):
            im = im.convert("RGB")
        elif im.mode != "RGB":
            im = im.convert("RGB")
        im.save(pdf_path, "PDF", resolution=100.0)
    except Exception as e2:
        hint = " Install `img2pdf` (`pip install img2pdf`) or ensure Pillow can save PDF."
        raise MinerUError(
            f"Failed to convert image to PDF (img2pdf: {primary_err}; Pillow: {e2}).{hint}"
        ) from e2


class MinerUClient:
    def __init__(self, token: str, api_base: str, model_version: str = "vlm"):
        if not token:
            raise MinerUError("MINERU_TOKEN is not set.")
        self.token = token
        self.api_base = api_base.rstrip("/")
        self.model_version = model_version
        self._upload_url_api = f"{self.api_base}/api/v4/file-urls/batch"
        self._result_url_tpl = f"{self.api_base}/api/v4/extract-results/batch/{{}}"

    def _headers(self) -> dict[str, str]:
        return {
            "Content-Type": "application/json",
            "Authorization": f"Bearer {self.token}",
        }

    def get_upload_url(self, filename: str) -> tuple[Optional[str], Optional[str], Optional[str]]:
        payload = {"files": [{"name": filename}], "model_version": self.model_version}
        try:
            r = requests.post(self._upload_url_api, headers=self._headers(), json=payload, timeout=60)
            r.raise_for_status()
            body = r.json()
            if body.get("code") != 0:
                return None, None, body.get("msg", "unknown error")
            data = body["data"]
            return data["batch_id"], data["file_urls"][0], None
        except requests.RequestException as e:
            return None, None, str(e)

    def upload_file(self, file_path: Path, upload_url: str) -> Optional[str]:
        try:
            with open(file_path, "rb") as f:
                # Presigned URLs must not send Bearer auth
                r = requests.put(upload_url, data=f, timeout=300, headers={})
            r.raise_for_status()
            return None
        except requests.RequestException as e:
            return str(e)

    def poll_until_zip_url(self, batch_id: str, timeout_sec: int = 600) -> tuple[Optional[str], Optional[str]]:
        url = self._result_url_tpl.format(batch_id)
        start = time.time()
        while time.time() - start < timeout_sec:
            try:
                r = requests.get(url, headers=self._headers(), timeout=60)
                r.raise_for_status()
                body = r.json()
                if body.get("code") != 0:
                    return None, body.get("msg", "poll error")
                item = body["data"]["extract_result"][0]
                state = item["state"]
                if state == "done":
                    return item.get("full_zip_url"), None
                if state == "failed":
                    return None, item.get("err_msg", "MinerU failed")
                time.sleep(2)
            except requests.RequestException as e:
                logger.warning("MinerU poll network error: %s", e)
                time.sleep(2)
        return None, f"timeout after {timeout_sec}s"

    def download_and_extract(self, zip_url: str, dest_dir: Path) -> Path:
        dest_dir.mkdir(parents=True, exist_ok=True)
        r = requests.get(zip_url, timeout=120)
        r.raise_for_status()
        extract_root = dest_dir / str(uuid.uuid4())[:10]
        extract_root.mkdir(parents=True, exist_ok=True)
        with zipfile.ZipFile(io.BytesIO(r.content)) as z:
            z.extractall(extract_root)
        return extract_root


def find_mineru_layout_dir(extract_root: Path) -> Path:
    layouts = list(extract_root.rglob("layout.json"))
    if not layouts:
        raise MinerUError(f"No layout.json under {extract_root}")
    return layouts[0].parent


def parse_slide_image(
    image_path: str,
    *,
    token: str,
    api_base: str,
    model_version: str,
    work_dir: Path,
    poll_timeout: int,
) -> Path:
    """
    Run MinerU on a single slide image. Returns directory containing layout.json
    and MinerU assets (e.g. images/).
    """
    work_dir.mkdir(parents=True, exist_ok=True)
    pdf_path = work_dir / "slide.pdf"
    image_to_pdf(image_path, pdf_path)

    client = MinerUClient(token, api_base, model_version)
    batch_id, upload_url, err = client.get_upload_url(pdf_path.name)
    if err:
        raise MinerUError(f"get upload URL: {err}")
    assert batch_id and upload_url

    up_err = client.upload_file(pdf_path, upload_url)
    if up_err:
        raise MinerUError(f"upload: {up_err}")

    zip_url, perr = client.poll_until_zip_url(batch_id, timeout_sec=poll_timeout)
    if perr or not zip_url:
        raise MinerUError(perr or "no zip url")

    extracted = client.download_and_extract(zip_url, work_dir / "zip_out")
    return find_mineru_layout_dir(extracted)
