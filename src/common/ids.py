"""Stable short-id helpers.

IDs follow the v2 prefix convention from the architecture doc:
    run_<uuid>          pipeline_runs.run_id
    cand_<uuid8>        candidate_repository_evaluations.id
    proj_<sha1>         project identity (deterministic per canonical_repo_key)
    eval_<uuid8>        evaluations[].evaluation_id
    sel_<uuid8>         selection[].selection_id
    posted_proj_<sha1>  posted_repositories.id (deterministic per project_id)
    post_<channel>_<uuid8>  post instance inside posted_repositories.post_instances
    asset_<uuid8>       media asset id inside post_instances[].media[]
"""
from __future__ import annotations

import hashlib
import uuid


def _short_uuid(n: int = 8) -> str:
    return uuid.uuid4().hex[:n]


def run_id() -> str:
    return f"run_{uuid.uuid4()}"


def candidate_id() -> str:
    return f"cand_{_short_uuid()}"


def evaluation_id() -> str:
    return f"eval_{_short_uuid()}"


def selection_id() -> str:
    return f"sel_{_short_uuid()}"


def asset_id() -> str:
    return f"asset_{_short_uuid()}"


def post_instance_id(channel: str) -> str:
    safe_channel = "".join(c for c in channel.lower() if c.isalnum()) or "post"
    return f"post_{safe_channel}_{_short_uuid()}"


def project_id_for(canonical_repo_key: str) -> str:
    """Deterministic project_id derived from the canonical repo key.

    Same input always yields the same project_id, so the same GitHub repo
    discovered across multiple runs maps to a single project identity without
    needing a separate `projects` lookup table.
    """
    digest = hashlib.sha1(canonical_repo_key.encode("utf-8")).hexdigest()[:12]
    return f"proj_{digest}"


def posted_repo_id_for(project_id: str) -> str:
    return f"posted_{project_id}"
