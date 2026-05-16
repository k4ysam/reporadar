"""Discovery adapters: github_discovery, devpost_discovery, manual_submission.

Each adapter returns `list[Candidate]` plus writes rows to
`candidate_repository_evaluations` via the shared repository module.
"""
