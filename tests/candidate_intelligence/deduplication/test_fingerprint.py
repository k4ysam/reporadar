import pytest

from src.candidate_intelligence.deduplication import (
    canonical_key_for_devpost,
    canonical_key_for_github,
)


def test_canonical_key_for_github_url():
    assert (
        canonical_key_for_github("https://github.com/example/example")
        == "github:example/example"
    )


def test_canonical_key_for_github_url_with_trailing_segments():
    assert (
        canonical_key_for_github("https://github.com/example/example/tree/main")
        == "github:example/example"
    )


def test_canonical_key_for_full_name():
    assert canonical_key_for_github("example/example") == "github:example/example"


def test_canonical_key_for_github_rejects_bad_input():
    with pytest.raises(ValueError):
        canonical_key_for_github("https://github.com/")


def test_canonical_key_for_devpost():
    assert (
        canonical_key_for_devpost("https://devpost.com/software/example-project")
        == "devpost:example-project"
    )
    assert (
        canonical_key_for_devpost("https://devpost.com/software/example-project/")
        == "devpost:example-project"
    )
