import json
from datetime import datetime, timezone

from src.contracts.content import GeneratedContent
from src.contracts.media import MediaAsset
from src.contracts.package import PostPackage
from src.publishing.adapters.manual_export import export_to_disk


def _now():
    return datetime(2026, 5, 16, tzinfo=timezone.utc)


def _package(tmp_path):
    content = GeneratedContent(
        channel="linkedin",
        content_format="commentary",
        text="A LinkedIn post.",
        generated_at=_now(),
        model="m",
        prompt_version="v",
        character_count=20,
    )
    asset = MediaAsset(
        asset_id="asset_x",
        channel="linkedin",
        local_path=str(tmp_path / "poster.jpg"),
        width=1024,
        height=1536,
        aspect_ratio="2:3",
        alt_text="alt",
        image_prompt_version="v",
        generated_at=_now(),
    )
    return PostPackage(
        post_id="post_linkedin_abc",
        project_id="proj_1",
        candidate_id="cand_1",
        run_id="run_1",
        channel="linkedin",
        content=content,
        media=[asset],
        source_links=["https://github.com/example/x"],
        created_at=_now(),
    )


def test_export_writes_json_with_expected_fields(tmp_path):
    pkg = _package(tmp_path)
    json_path = export_to_disk(pkg, tmp_path)

    assert json_path.exists()
    data = json.loads(json_path.read_text())
    assert data["post_id"] == "post_linkedin_abc"
    assert data["channel"] == "linkedin"
    assert data["content"]["text"] == "A LinkedIn post."
    assert data["media"][0]["asset_id"] == "asset_x"
