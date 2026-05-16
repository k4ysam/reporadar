"""Aggregator: collects per-channel profiles into the PROFILES dict.

Adding a new channel:
    1. Create `<channel>.py` here with a prompt builder + a PROFILE constant.
    2. Add an entry to PROFILES below.
"""
from src.content_generation.media.channels.instagram import INSTAGRAM_PROFILE
from src.content_generation.media.channels.linkedin import LINKEDIN_PROFILE
from src.content_generation.media.profile import ChannelMediaProfile

PROFILES: dict[str, ChannelMediaProfile] = {
    "instagram": INSTAGRAM_PROFILE,
    "linkedin": LINKEDIN_PROFILE,
}


def get_profile(channel: str) -> ChannelMediaProfile:
    if channel not in PROFILES:
        raise NotImplementedError(f"No media profile for channel {channel!r}")
    return PROFILES[channel]


__all__ = ["PROFILES", "get_profile", "ChannelMediaProfile"]
