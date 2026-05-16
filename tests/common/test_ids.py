from src.common.ids import (
    asset_id,
    candidate_id,
    evaluation_id,
    post_instance_id,
    posted_repo_id_for,
    project_id_for,
    run_id,
    selection_id,
)


def test_prefixes_match_v2_convention():
    assert run_id().startswith("run_")
    assert candidate_id().startswith("cand_")
    assert evaluation_id().startswith("eval_")
    assert selection_id().startswith("sel_")
    assert asset_id().startswith("asset_")


def test_project_id_is_deterministic():
    a = project_id_for("github:owner/repo")
    b = project_id_for("github:owner/repo")
    c = project_id_for("github:owner/other-repo")
    assert a == b
    assert a != c
    assert a.startswith("proj_")


def test_posted_repo_id_derives_from_project_id():
    pid = project_id_for("github:example/example")
    posted = posted_repo_id_for(pid)
    assert posted == f"posted_{pid}"


def test_post_instance_id_includes_channel():
    pid = post_instance_id("linkedin")
    assert pid.startswith("post_linkedin_")
    assert post_instance_id("Instagram").startswith("post_instagram_")
