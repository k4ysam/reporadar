from __future__ import annotations

import base64
import sys
from datetime import datetime, timezone
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import MagicMock

import pytest

from src.models import Caption, Evaluation, HackathonCandidate
from src.render.image_gen import OpenAIImageClient
from src.render.image_prompt import (
    build_hackathon_image_prompt,
    build_linkedin_repo_image_prompt,
    build_repo_image_prompt,
)
from src.render.renderer import (
    render_hackathon_card,
    render_linkedin_repo_poster,
    render_repo_card,
)

_VALID_1X1_PNG = bytes.fromhex(
    "89504e470d0a1a0a0000000d4948445200000001000000010806000000"
    "1f15c4890000000d49444154789c63f8ffffff7f0009fb03fd2a86e38a"
    "0000000049454e44ae426082"
)


def _eval():
    return Evaluation(
        content_type="repo",
        repo_id=1,
        full_name="awesome-co/zerodb",
        summary="A 1ms KV store in pure Python.",
        why_interesting="Drop-in Redis replacement.",
        audience="Backend devs",
        novelty_score=8.5, explainability_score=9.0, overall_score=8.7,
        stars_48h=420, growth_pct=380.0,
    )


def _caption():
    return Caption(
        hook="A 1ms KV store, in pure Python.",
        body="No C deps. Drop-in for Redis.",
        cta="Star on GitHub.",
        hashtags=["python", "opensource"],
    )


def _seed_run(db, run_id):
    db.execute(
        "INSERT INTO pipeline_runs (run_id, started_at, status) VALUES (?, '2026-05-01', 'running')",
        (run_id,),
    )
    db.commit()


def _mock_openai(monkeypatch, png_bytes: bytes = _VALID_1X1_PNG) -> MagicMock:
    """Install a fake `openai` module that returns one b64-encoded PNG."""
    client_mock = MagicMock()
    b64 = base64.b64encode(png_bytes).decode("ascii")
    client_mock.images.generate.return_value = SimpleNamespace(
        data=[SimpleNamespace(b64_json=b64)]
    )
    openai_cls = MagicMock(return_value=client_mock)
    monkeypatch.setitem(sys.modules, "openai", SimpleNamespace(OpenAI=openai_cls))
    return client_mock


def test_build_repo_image_prompt_includes_headline_and_brand():
    prompt = build_repo_image_prompt(_eval(), _caption(), language="Python")
    assert "A 1MS KV STORE, IN PURE PYTHON." in prompt  # headline upper-cased
    assert "awesome-co/zerodb" in prompt
    assert "REPORADAR" in prompt
    assert "Python" in prompt


def test_build_hackathon_image_prompt_includes_headline_and_prize():
    candidate = HackathonCandidate(
        devpost_url="https://devpost.com/software/pixelchef",
        project_name="PixelChef",
        hackathon_name="HackMIT",
        prize="Best Overall",
        github_url="https://github.com/x/pixelchef",
        first_seen_at=datetime.now(timezone.utc),
        technologies=["python", "ffmpeg"],
    )
    prompt = build_hackathon_image_prompt(_eval(), candidate, _caption())
    assert "A 1MS KV STORE, IN PURE PYTHON." in prompt
    assert "HackMIT" in prompt
    assert "Best Overall" in prompt
    assert "REPORADAR" in prompt


def test_build_linkedin_repo_image_prompt_includes_stats_and_topics():
    prompt = build_linkedin_repo_image_prompt(
        _eval(),
        headline="zerodb turns local files into an agent memory layer",
        language="Python",
        topics=["kv", "storage"],
    )
    assert "ZERODB TURNS LOCAL FILES INTO AN AGENT MEMORY LAYER" in prompt
    assert "+420 STARS" in prompt
    assert "+380% GROWTH" in prompt
    assert "awesome-co/zerodb" in prompt
    assert "Python" in prompt
    assert "kv" in prompt
    assert "REPORADAR" in prompt


def test_render_repo_card_calls_openai_and_writes_jpeg(tmp_path, tmp_db, mock_run_id, monkeypatch):
    _seed_run(tmp_db, mock_run_id)
    client_mock = _mock_openai(monkeypatch)
    out_dir = tmp_path / "cards"

    image_client = OpenAIImageClient(tmp_db, mock_run_id, "sk-test")
    result = render_repo_card(_eval(), _caption(), out_dir, image_client, language="Python")

    assert result.media_type == "single"
    assert len(result.paths) == 1
    output_path = Path(result.paths[0])
    assert output_path.exists()
    assert output_path.suffix == ".jpg"

    client_mock.images.generate.assert_called_once()
    call_kwargs = client_mock.images.generate.call_args.kwargs
    assert call_kwargs["model"] == "gpt-image-1"
    assert call_kwargs["size"] == "1024x1024"
    assert call_kwargs["n"] == 1
    assert "A 1MS KV STORE, IN PURE PYTHON." in call_kwargs["prompt"]

    row = tmp_db.execute(
        "SELECT service, endpoint, status_code FROM api_calls WHERE service='openai'"
    ).fetchone()
    assert row["service"] == "openai"
    assert row["endpoint"] == "images.generate"
    assert row["status_code"] == 200


def test_render_hackathon_card_returns_single_image(tmp_path, tmp_db, mock_run_id, monkeypatch):
    _seed_run(tmp_db, mock_run_id)
    client_mock = _mock_openai(monkeypatch)
    out_dir = tmp_path / "cards"
    candidate = HackathonCandidate(
        devpost_url="https://devpost.com/software/pixelchef",
        project_name="PixelChef",
        hackathon_name="HackMIT",
        prize="Best Overall",
        github_url="https://github.com/x/pixelchef",
        first_seen_at=datetime.now(timezone.utc),
        technologies=["python", "ffmpeg"],
    )

    image_client = OpenAIImageClient(tmp_db, mock_run_id, "sk-test")
    result = render_hackathon_card(_eval(), candidate, _caption(), out_dir, image_client)

    assert result.media_type == "single"
    assert len(result.paths) == 1
    assert Path(result.paths[0]).exists()
    assert client_mock.images.generate.call_count == 1


def test_render_linkedin_repo_poster_uses_openai_and_tall_aspect(tmp_path, tmp_db, mock_run_id, monkeypatch):
    _seed_run(tmp_db, mock_run_id)
    client_mock = _mock_openai(monkeypatch)
    out_dir = tmp_path / "cards"

    image_client = OpenAIImageClient(tmp_db, mock_run_id, "sk-test", size="1024x1536")
    result = render_linkedin_repo_poster(
        _eval(),
        out_dir,
        image_client,
        headline="zerodb turns local files into an agent memory layer",
        language="Python",
        topics=["kv", "storage"],
    )

    assert result.media_type == "single"
    assert len(result.paths) == 1
    assert Path(result.paths[0]).name.startswith("linkedin_repo_")

    client_mock.images.generate.assert_called_once()
    call_kwargs = client_mock.images.generate.call_args.kwargs
    assert call_kwargs["size"] == "1024x1536"
    assert "ZERODB TURNS LOCAL FILES" in call_kwargs["prompt"]
    assert "REPORADAR" in call_kwargs["prompt"]


def test_image_client_logs_failure(tmp_path, tmp_db, mock_run_id, monkeypatch):
    _seed_run(tmp_db, mock_run_id)
    client_mock = MagicMock()
    client_mock.images.generate.side_effect = RuntimeError("boom")
    openai_cls = MagicMock(return_value=client_mock)
    monkeypatch.setitem(sys.modules, "openai", SimpleNamespace(OpenAI=openai_cls))

    image_client = OpenAIImageClient(tmp_db, mock_run_id, "sk-test")
    target = tmp_path / "out.jpg"
    with pytest.raises(RuntimeError):
        image_client.generate("prompt", target)

    row = tmp_db.execute(
        "SELECT status_code FROM api_calls WHERE endpoint='images.generate'"
    ).fetchone()
    assert row["status_code"] == 500
