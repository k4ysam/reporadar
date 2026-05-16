"""Shared `ChannelMediaProfile` dataclass.

Lives one level above `channels/` so each per-channel module can import the
dataclass without forming an import cycle with `channels/__init__.py`
(which aggregates the per-channel profile constants into PROFILES).
"""
from __future__ import annotations

from dataclasses import dataclass
from typing import Callable

from src.contracts.candidate import Candidate
from src.contracts.content import GeneratedContent
from src.contracts.evaluation import Evaluation


@dataclass(frozen=True)
class ChannelMediaProfile:
    channel: str
    width: int
    height: int
    aspect_ratio: str
    openai_size: str
    image_prompt_version: str
    prompt_builder: Callable[[Candidate, Evaluation, GeneratedContent], str]
    style: str
