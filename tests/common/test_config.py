import pytest

from src.common.config import Settings


def _kwargs(**overrides):
    base = dict(
        database_url="postgresql://u:p@h:5432/db",
        gh_token="t",
        openai_api_key="o",
    )
    base.update(overrides)
    return base


def test_settings_constructs_with_required_fields():
    s = Settings(**_kwargs())
    assert s.llm_provider == "openai"
    assert s.llm_model == s.openai_model


def test_settings_requires_openai_key_even_for_claude():
    with pytest.raises(ValueError, match="OPENAI_API_KEY"):
        Settings(
            database_url="postgresql://u:p@h:5432/db",
            gh_token="t",
            llm_provider="claude",
            anthropic_api_key="a",
            openai_api_key=None,
        )


def test_settings_requires_provider_key_for_selected_provider():
    with pytest.raises(ValueError, match="ANTHROPIC_API_KEY"):
        Settings(
            database_url="postgresql://u:p@h:5432/db",
            gh_token="t",
            llm_provider="claude",
            openai_api_key="o",
        )


def test_settings_requires_database_url():
    with pytest.raises(ValueError):
        Settings(database_url="", gh_token="t", openai_api_key="o")
