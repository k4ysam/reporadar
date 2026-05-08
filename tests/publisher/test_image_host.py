from __future__ import annotations

from unittest.mock import MagicMock, patch

import pytest

from src.config import Settings
from src.publisher.image_host import LocalFileHost, S3Host, get_image_host


def _settings(**overrides):
    base = dict(gh_token="x", gemini_api_key="AIza")
    base.update(overrides)
    return Settings(**base)


def test_local_host_returns_file_uri(tmp_path):
    img = tmp_path / "x.jpg"
    img.write_bytes(b"\x89PNG")
    host = LocalFileHost(_settings(output_dir=str(tmp_path)))
    url = host.upload(str(img))
    assert url.startswith("file://")
    assert url.endswith("x.jpg")


def test_get_image_host_falls_back_to_local():
    host = get_image_host(_settings())
    assert isinstance(host, LocalFileHost)


def test_s3_host_uploads_to_bucket(tmp_path):
    img = tmp_path / "x.jpg"
    img.write_bytes(b"\xff\xd8\xff")  # tiny jpeg header
    settings = _settings(
        image_host_bucket="bucket",
        image_host_access_key="ak",
        image_host_secret_key="sk",
        image_host_public_base_url="https://cdn.example.com",
        image_host_endpoint="https://r2.example.com",
    )
    fake_client = MagicMock()
    with patch("boto3.client", return_value=fake_client) as boto:
        host = S3Host(settings)
        url = host.upload(str(img))
    boto.assert_called_once()
    fake_client.put_object.assert_called_once()
    kwargs = fake_client.put_object.call_args.kwargs
    assert kwargs["Bucket"] == "bucket"
    assert kwargs["Key"] == "cards/x.jpg"
    assert kwargs["ACL"] == "public-read"
    assert url == "https://cdn.example.com/cards/x.jpg"


def test_s3_host_requires_full_config():
    with pytest.raises(RuntimeError, match="IMAGE_HOST_BUCKET"):
        S3Host(_settings(image_host_bucket=None))
