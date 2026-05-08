from __future__ import annotations

import logging
import mimetypes
from pathlib import Path
from typing import Protocol

from src.config import Settings

_log = logging.getLogger(__name__)


class ImageHost(Protocol):
    def upload(self, local_path: str) -> str: ...


class S3Host:
    """boto3-compatible host. Works with AWS S3, Cloudflare R2, Backblaze B2."""

    def __init__(self, settings: Settings):
        if not all((
            settings.image_host_bucket,
            settings.image_host_access_key,
            settings.image_host_secret_key,
            settings.image_host_public_base_url,
        )):
            raise RuntimeError(
                "S3Host requires IMAGE_HOST_BUCKET, IMAGE_HOST_ACCESS_KEY, "
                "IMAGE_HOST_SECRET_KEY, IMAGE_HOST_PUBLIC_BASE_URL"
            )
        import boto3

        self._bucket = settings.image_host_bucket
        self._public_base = settings.image_host_public_base_url.rstrip("/")
        client_kwargs = {
            "aws_access_key_id": settings.image_host_access_key,
            "aws_secret_access_key": settings.image_host_secret_key,
            "region_name": settings.image_host_region,
        }
        if settings.image_host_endpoint:
            client_kwargs["endpoint_url"] = settings.image_host_endpoint
        self._client = boto3.client("s3", **client_kwargs)

    def upload(self, local_path: str) -> str:
        path = Path(local_path)
        if not path.exists():
            raise FileNotFoundError(local_path)
        key = f"cards/{path.name}"
        content_type = mimetypes.guess_type(path.name)[0] or "image/jpeg"
        with path.open("rb") as f:
            self._client.put_object(
                Bucket=self._bucket,
                Key=key,
                Body=f,
                ContentType=content_type,
                ACL="public-read",
            )
        return f"{self._public_base}/{key}"


class LocalFileHost:
    """Dev fallback: write to local output, return file:// URL.

    Instagram Graph API will reject file:// URLs, so this is only useful for
    --dry-run testing or pairing with a tunnel like ngrok.
    """

    def __init__(self, settings: Settings):
        self._dir = Path(settings.output_dir).resolve()
        self._dir.mkdir(parents=True, exist_ok=True)

    def upload(self, local_path: str) -> str:
        path = Path(local_path).resolve()
        return path.as_uri()


def get_image_host(settings: Settings) -> ImageHost:
    if settings.image_host_bucket:
        return S3Host(settings)
    _log.warning(
        "No IMAGE_HOST_BUCKET configured — using LocalFileHost. "
        "Instagram requires public HTTPS URLs; only useful for --dry-run."
    )
    return LocalFileHost(settings)
