"""Cross-service domain models. Importing from here gives every service the
same shape for Candidate, Evaluation, GeneratedContent, MediaAsset, PostPackage,
etc. — independent of any database serialization."""

from src.contracts.candidate import (
    Candidate,
    CandidateSource,
    DiscoverySignals,
    GithubSnapshot,
    HackathonSnapshot,
    RepoEnrichment,
)
from src.contracts.content import GeneratedContent
from src.contracts.evaluation import Evaluation, EvaluationScores
from src.contracts.media import MediaAsset, RenderResult
from src.contracts.package import PostPackage, PostStatus
from src.contracts.run import PipelineRun, RunStatus
from src.contracts.selection import RankingBreakdown, SelectionDecision

__all__ = [
    "Candidate",
    "CandidateSource",
    "DiscoverySignals",
    "GithubSnapshot",
    "HackathonSnapshot",
    "RepoEnrichment",
    "Evaluation",
    "EvaluationScores",
    "SelectionDecision",
    "RankingBreakdown",
    "GeneratedContent",
    "MediaAsset",
    "RenderResult",
    "PostPackage",
    "PostStatus",
    "PipelineRun",
    "RunStatus",
]
