from __future__ import annotations

import base64
import sqlite3
import time
from pathlib import Path

from src.db import log_api_call


class OpenAIImageClient:
    """Wraps OpenAI's images.generate endpoint and writes the result to disk.

    Logs each call to api_calls with service='openai', endpoint='images.generate'
    so it rolls under the same daily-budget accounting as text calls.
    """

    name = "openai"

    def __init__(
        self,
        db: sqlite3.Connection,
        run_id: str,
        api_key: str,
        model: str = "gpt-image-2",
        size: str = "1024x1024",
    ):
        from openai import OpenAI

        self._db = db
        self._run_id = run_id
        self._client = OpenAI(api_key=api_key)
        self._model = model
        self._size = size

    def generate(self, prompt: str, output_path: Path) -> Path:
        """Generate one image from prompt and write a JPEG to output_path.

        Returns output_path. The OpenAI response is base64 PNG; we decode,
        write a temp PNG, then convert to JPEG via Pillow for size parity
        with the previous Playwright-based renderer.
        """
        t0 = time.monotonic()
        try:
            resp = self._client.images.generate(
                model=self._model,
                prompt=prompt,
                size=self._size,
                n=1,
            )
            self._log_call("images.generate", 200, t0)
        except Exception:
            self._log_call("images.generate", 500, t0)
            raise

        b64 = resp.data[0].b64_json
        png_bytes = base64.b64decode(b64)
        png_path = output_path.with_suffix(".png")
        png_path.write_bytes(png_bytes)

        if output_path.suffix.lower() in (".jpg", ".jpeg"):
            _png_to_jpeg(png_path, output_path)
        else:
            png_path.replace(output_path)
        return output_path

    def _log_call(self, endpoint: str, status_code: int, started_at: float) -> None:
        latency_ms = int((time.monotonic() - started_at) * 1000)
        log_api_call(self._db, self._run_id, self.name, endpoint, status_code, latency_ms)


def _png_to_jpeg(png_path: Path, jpeg_path: Path) -> None:
    """Convert PNG to JPEG. Falls back to renaming if Pillow is unavailable."""
    try:
        from PIL import Image  # type: ignore

        with Image.open(png_path) as im:
            im.convert("RGB").save(jpeg_path, "JPEG", quality=92)
        png_path.unlink(missing_ok=True)
    except ImportError:
        png_path.replace(jpeg_path)
