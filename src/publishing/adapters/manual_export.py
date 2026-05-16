"""Manual export adapter — writes JSON next to the rendered image so the
operator has everything in one folder for copy/paste posting.

The image binary already lives at `media[0].local_path`; this just emits
a sidecar JSON containing the caption text, source links, alt text, and
platform metadata.
"""
from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path

from src.contracts.package import PostPackage


def export_to_disk(package: PostPackage, output_dir: str | Path) -> Path:
    out = Path(output_dir)
    out.mkdir(parents=True, exist_ok=True)
    timestamp = datetime.now(timezone.utc).strftime("%Y%m%d-%H%M%S")
    json_path = out / f"{package.channel}_{package.post_id}_{timestamp}.json"
    json_path.write_text(
        json.dumps(package.model_dump(mode="json"), indent=2) + "\n",
        encoding="utf-8",
    )
    return json_path
