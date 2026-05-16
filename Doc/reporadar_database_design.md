# RepoRadar v2 Database Design

This document redesigns the RepoRadar database around the new modular architecture.

The proposed design uses two main containers:

1. `posted_repositories` - stores repos/projects that have been posted, exported, or manually marked as posted.
2. `candidate_repository_evaluations` - stores repos/projects discovered, enriched, evaluated, ranked, skipped, or selected during the discovery process.

This is a good MVP database design for RepoRadar because it maps cleanly to the two most important product questions:

```text
What should we post next?
What have we already posted?
```

However, the design should be implemented carefully so that it can grow into a more service-oriented architecture later.

---

## 1. Recommended high-level structure

```text
RepoRadar Database
├── posted_repositories
│   └── Repos that have been posted, exported, or manually marked as posted
│
└── candidate_repository_evaluations
    └── Repos discovered, enriched, evaluated, skipped, ranked, or selected
```

The data flow should look like this:

```text
Discovery + Evaluation Service
        writes to
candidate_repository_evaluations

Selection Service
        reads ranked candidates from
candidate_repository_evaluations

Content Generation Service
Media Rendering Service
Post Packaging Service
        generate final post artifacts

Publishing / Manual Export Service
        writes final historical records to
posted_repositories
```

---

## 2. Is the two-container design good?

Yes. For RepoRadar's current stage, this is a strong practical design.

It gives the project:

```text
Simple mental model
Easy dashboard queries
Easy deduplication
Clear separation between candidates and posted repos
Easy manual workflow
Easy ranking view
Easy historical archive of posts
```

The two containers should be understood as two different domain areas:

```text
candidate_repository_evaluations
  = working pipeline data
  = discovery, enrichment, scoring, ranking, selection

posted_repositories
  = permanent posting archive
  = repo snapshot, final caption, platform, image, posting status
```

The biggest improvement I recommend is to make `posted_repositories` a historical snapshot, not just a reference to a candidate. When a repo is posted, copy the final GitHub info, evaluation summary, ranking snapshot, caption, media metadata, and platform status into the posted container.

That way, months later, you can still answer:

```text
What exactly did we post?
Where did we post it?
Which image did we attach?
What caption did we use?
Why was this repo selected?
What did the repo look like at the time of posting?
```

---

## 3. Important design rules

### 3.1 Do not store image binaries in the database

Do not store image files directly as binary or base64 inside the database.

Instead, store images in object storage or the local filesystem:

```text
S3
MinIO
Cloudflare R2
Local output/ folder during development
```

Then store only metadata and file paths in the database:

```json
{
  "asset_id": "asset_88d12f",
  "uri": "s3://reporadar/media/post_123/poster.jpg",
  "local_path": "output/linkedin_project_20260515.jpg",
  "mime_type": "image/jpeg",
  "width": 1024,
  "height": 1536,
  "content_hash": "sha256:abc123"
}
```

### 3.2 Do not only store rank position

A rank like `1`, `2`, or `3` is not enough.

Store:

```text
ranking_score
rank_in_run
ranking_version
score_breakdown
ranking_reasons
```

This matters because rankings can change when the ranking algorithm changes.

### 3.3 Store raw large content outside the database

Avoid storing these directly in the database:

```text
Full README text
Full raw GitHub API response
Full raw LLM output
Image binary or base64
Large generated image prompts
```

Instead, store them in object storage and keep references in the database:

```json
{
  "readme_uri": "s3://reporadar/raw/readmes/proj_9f2a81c7.md",
  "raw_llm_output_uri": "s3://reporadar/evaluations/eval_a81d33f1.json",
  "image_uri": "s3://reporadar/media/post_123/poster.jpg"
}
```

---

## 4. Container 1: `posted_repositories`

### Purpose

This container stores the permanent history of repos that RepoRadar has posted, exported, or manually marked as posted.

It answers questions like:

```text
Have we posted this repo before?
Which platforms did we post it on?
What caption did we use?
What image was attached?
When was it posted?
Which evaluation caused us to post it?
What did the repo look like at posting time?
```

### Recommended document model

One document should represent one canonical repo/project that has been posted.

```json
{
  "id": "posted_proj_9f2a81c7",
  "type": "posted_repository",

  "project_id": "proj_9f2a81c7",
  "canonical_repo_url": "https://github.com/example/example-project",
  "canonical_repo_key": "github:example/example-project",

  "github": {
    "owner": "example",
    "repo": "example-project",
    "full_name": "example/example-project",
    "url": "https://github.com/example/example-project",
    "description": "A short GitHub repo description.",
    "homepage_url": "https://example.com",
    "primary_language": "Python",
    "topics": ["ai", "developer-tools", "cli"],
    "license": "MIT",
    "stars_count": 1840,
    "forks_count": 120,
    "open_issues_count": 18,
    "watchers_count": 1840,
    "default_branch": "main",
    "created_at": "2025-11-10T12:00:00Z",
    "pushed_at": "2026-05-14T18:44:00Z",
    "last_fetched_at": "2026-05-15T13:00:00Z"
  },

  "project_description": {
    "github_description": "A short GitHub repo description.",
    "readme_summary": "A concise summary extracted from the README.",
    "ai_summary": "RepoRadar's final summary of what the project does.",
    "why_interesting": "Why this project is worth sharing with developers and CS students.",
    "target_audience": ["developers", "college_students", "cs_students"],
    "learning_value": "Useful for learning about AI agents and CLI design.",
    "tags": ["open-source", "ai", "cli", "developer-tools"]
  },

  "source": {
    "original_source_type": "github_discovery",
    "source_urls": [
      "https://github.com/example/example-project"
    ],
    "discovery_run_id": "run_2026_05_15_001",
    "candidate_id": "cand_6ac92d12",
    "evaluation_id": "eval_a81d33f1",
    "selection_id": "sel_33cc9021"
  },

  "evaluation_snapshot": {
    "evaluated_at": "2026-05-15T13:20:00Z",
    "model": "gpt-5.5-pro",
    "prompt_version": "repo_eval_v4",
    "summary": "A developer tool that helps users build and test AI workflows locally.",
    "why_interesting": "It gives students and developers a practical way to understand agent workflows.",
    "audience": ["developers", "college_students"],
    "scores": {
      "novelty": 8.0,
      "usefulness": 8.5,
      "explainability": 9.0,
      "freshness": 7.5,
      "developer_relevance": 9.0,
      "student_learning_value": 8.5,
      "overall": 8.6
    },
    "skip": false,
    "skip_reason": null,
    "risks": ["README is strong, but production-readiness is unclear."],
    "evidence_quality": "medium"
  },

  "ranking_snapshot": {
    "ranking_version": "ranker_v2",
    "ranking_score": 8.72,
    "rank_in_run": 1,
    "total_candidates_in_run": 42,
    "ranked_at": "2026-05-15T13:25:00Z",
    "selection_reason": "Highest score with strong developer relevance and clear explanation potential."
  },

  "post_instances": [
    {
      "post_id": "post_linkedin_20260515_001",
      "platform": "linkedin",
      "status": "manually_posted",

      "content": {
        "content_version": 1,
        "format": "linkedin_commentary",
        "text": "Longform LinkedIn commentary goes here...",
        "hook": "A promising open-source project for learning AI workflow design.",
        "cta": "Check out the repo and explore how it works.",
        "hashtags": ["#OpenSource", "#DeveloperTools", "#AI"],
        "source_links": [
          "https://github.com/example/example-project"
        ],
        "character_count": 1375,
        "generated_at": "2026-05-15T13:32:00Z",
        "model": "gpt-5.5-pro",
        "prompt_version": "linkedin_repo_v3"
      },

      "media": [
        {
          "asset_id": "asset_88d12f",
          "type": "poster",
          "platform": "linkedin",
          "uri": "s3://reporadar/media/post_linkedin_20260515_001/poster.jpg",
          "local_path": "output/linkedin_example_project_20260515.jpg",
          "mime_type": "image/jpeg",
          "width": 1024,
          "height": 1536,
          "aspect_ratio": "2:3",
          "alt_text": "A poster introducing the example-project GitHub repository.",
          "image_prompt_version": "linkedin_poster_v2",
          "generated_by": "openai_image",
          "generated_at": "2026-05-15T13:34:00Z",
          "content_hash": "sha256:abc123"
        }
      ],

      "review": {
        "approved_by": "operator",
        "approved_at": "2026-05-15T13:40:00Z",
        "review_notes": "Looks good for LinkedIn."
      },

      "publication": {
        "publishing_mode": "manual",
        "posted_by": "operator",
        "posted_at": "2026-05-15T14:05:00Z",
        "external_post_url": "https://www.linkedin.com/feed/update/example",
        "external_post_id": null
      }
    },
    {
      "post_id": "post_instagram_20260515_001",
      "platform": "instagram",
      "status": "exported",

      "content": {
        "content_version": 1,
        "format": "instagram_caption",
        "text": "Instagram caption goes here...",
        "hook": "Found a cool open-source AI tool.",
        "cta": "Would you try building with this?",
        "hashtags": ["#OpenSource", "#GitHub", "#Coding"],
        "source_links": [
          "https://github.com/example/example-project"
        ],
        "character_count": 984,
        "generated_at": "2026-05-15T13:36:00Z",
        "model": "gpt-5.5-pro",
        "prompt_version": "instagram_repo_caption_v3"
      },

      "media": [
        {
          "asset_id": "asset_761ab0",
          "type": "poster",
          "platform": "instagram",
          "uri": "s3://reporadar/media/post_instagram_20260515_001/poster.jpg",
          "local_path": "output/instagram_example_project_20260515.jpg",
          "mime_type": "image/jpeg",
          "width": 1024,
          "height": 1024,
          "aspect_ratio": "1:1",
          "alt_text": "A square poster introducing the example-project repository.",
          "image_prompt_version": "instagram_square_poster_v2",
          "generated_by": "openai_image",
          "generated_at": "2026-05-15T13:37:00Z",
          "content_hash": "sha256:def456"
        }
      ],

      "review": {
        "approved_by": "operator",
        "approved_at": "2026-05-15T13:45:00Z",
        "review_notes": null
      },

      "publication": {
        "publishing_mode": "manual",
        "posted_by": null,
        "posted_at": null,
        "external_post_url": null,
        "external_post_id": null
      }
    }
  ],

  "posting_state": {
    "has_been_posted": true,
    "posted_platforms": ["linkedin"],
    "exported_platforms": ["instagram"],
    "first_posted_at": "2026-05-15T14:05:00Z",
    "last_posted_at": "2026-05-15T14:05:00Z",
    "do_not_repost": true
  },

  "audit": {
    "created_at": "2026-05-15T13:40:00Z",
    "updated_at": "2026-05-15T14:05:00Z",
    "created_by": "publishing_service",
    "updated_by": "operator_api",
    "schema_version": 1
  }
}
```

### Important fields in `posted_repositories`

| Field | Purpose |
|---|---|
| `canonical_repo_key` | Main deduplication key, for example `github:owner/repo`. |
| `github` | Snapshot of GitHub metadata at time of posting. |
| `project_description` | Human-readable and AI-generated explanation of the project. |
| `source` | Links the posted item back to discovery, evaluation, and selection. |
| `evaluation_snapshot` | The evaluation that justified posting the repo. |
| `ranking_snapshot` | The ranking state when the repo was selected. |
| `post_instances` | One entry per platform post: LinkedIn, Instagram, newsletter, etc. |
| `media` | Image metadata, not the image binary itself. |
| `publication` | Manual or automated posting status. |
| `posting_state.do_not_repost` | Prevents accidental reposting. |

---

## 5. Container 2: `candidate_repository_evaluations`

### Purpose

This container stores every repo that was discovered and evaluated during the discovery process.

It answers questions like:

```text
What repos did we discover today?
Which repos scored highest?
Why was a repo skipped?
Which repo should we post next?
What evidence did the evaluator use?
Was this repo already posted?
Which prompt and model evaluated this repo?
```

### Recommended document model

One document should represent one candidate repo inside one discovery/evaluation run.

That means the same repo can appear in multiple runs over time, but each run gets its own evaluation record.

```json
{
  "id": "cand_6ac92d12",
  "type": "candidate_repository_evaluation",

  "run_id": "run_2026_05_15_001",
  "project_id": "proj_9f2a81c7",
  "candidate_id": "cand_6ac92d12",

  "status": "evaluated",

  "source": {
    "source_type": "github_discovery",
    "source_name": "github_search_api",
    "source_url": "https://github.com/example/example-project",
    "discovered_at": "2026-05-15T13:00:00Z",
    "discovery_reason": "High star growth in the last 7 days.",
    "manual_submission": null
  },

  "discovery": {
    "query": "created:>2026-05-08 stars:>50",
    "window": {
      "from": "2026-05-08T00:00:00Z",
      "to": "2026-05-15T00:00:00Z"
    },
    "raw_result_uri": "s3://reporadar/raw/github_search/run_2026_05_15_001/example-project.json",
    "initial_signals": {
      "stars_at_discovery": 1840,
      "star_delta_1d": 110,
      "star_delta_7d": 760,
      "growth_percent_7d": 70.4,
      "forks_at_discovery": 120,
      "recent_commit_count_7d": 38,
      "recent_release_count_30d": 2,
      "pushed_recently": true
    }
  },

  "github": {
    "owner": "example",
    "repo": "example-project",
    "full_name": "example/example-project",
    "url": "https://github.com/example/example-project",
    "clone_url": "https://github.com/example/example-project.git",
    "description": "A short GitHub repo description.",
    "homepage_url": "https://example.com",
    "primary_language": "Python",
    "languages": {
      "Python": 82.4,
      "TypeScript": 12.0,
      "Shell": 5.6
    },
    "topics": ["ai", "developer-tools", "cli"],
    "license": "MIT",
    "stars_count": 1840,
    "forks_count": 120,
    "open_issues_count": 18,
    "watchers_count": 1840,
    "default_branch": "main",
    "created_at": "2025-11-10T12:00:00Z",
    "updated_at": "2026-05-15T10:15:00Z",
    "pushed_at": "2026-05-14T18:44:00Z",
    "archived": false,
    "disabled": false,
    "is_fork": false
  },

  "enrichment": {
    "readme": {
      "found": true,
      "readme_uri": "s3://reporadar/raw/readmes/proj_9f2a81c7.md",
      "readme_hash": "sha256:readme123",
      "readme_summary": "A concise summary of the README.",
      "has_installation_instructions": true,
      "has_usage_examples": true,
      "has_demo": true
    },
    "activity": {
      "commit_count_7d": 38,
      "commit_count_30d": 122,
      "contributors_count": 9,
      "latest_commit_at": "2026-05-14T18:44:00Z",
      "latest_release_at": "2026-05-12T11:30:00Z"
    },
    "quality_signals": {
      "has_license": true,
      "has_tests": true,
      "has_ci": true,
      "has_docs": true,
      "has_examples": true,
      "has_security_policy": false
    },
    "links": {
      "demo_url": "https://example.com/demo",
      "docs_url": "https://docs.example.com",
      "package_url": null,
      "devpost_url": null
    }
  },

  "deduplication": {
    "canonical_repo_url": "https://github.com/example/example-project",
    "canonical_repo_key": "github:example/example-project",
    "fingerprint": "sha256:github-example-example-project",
    "already_posted": false,
    "posted_project_id": null,
    "duplicate_of_project_id": null,
    "duplicate_reason": null
  },

  "evaluation": {
    "evaluation_id": "eval_a81d33f1",
    "status": "success",
    "evaluated_at": "2026-05-15T13:20:00Z",
    "model": "gpt-5.5-pro",
    "provider": "openai",
    "prompt_version": "repo_eval_v4",
    "system_prompt_version": "repo_eval_system_v2",
    "raw_llm_output_uri": "s3://reporadar/evaluations/eval_a81d33f1.json",

    "summary": "A developer tool that helps users build and test AI workflows locally.",
    "why_interesting": "It gives students and developers a practical way to understand agent workflows.",
    "audience": ["developers", "college_students", "cs_students"],
    "suggested_angle": "A practical open-source project for learning how AI agents are built.",
    "content_potential": "high",

    "scores": {
      "novelty": 8.0,
      "usefulness": 8.5,
      "explainability": 9.0,
      "freshness": 7.5,
      "developer_relevance": 9.0,
      "student_learning_value": 8.5,
      "visual_post_potential": 8.0,
      "overall": 8.6
    },

    "skip": false,
    "skip_reason": null,

    "risks": [
      "Production readiness is unclear.",
      "The README may overstate some capabilities."
    ],

    "evidence": {
      "positive": [
        "Recent commit activity is strong.",
        "README includes installation and usage examples.",
        "Project has clear educational value."
      ],
      "negative": [
        "Security policy is missing."
      ],
      "evidence_quality": "medium"
    }
  },

  "ranking": {
    "ranking_version": "ranker_v2",
    "ranking_score": 8.72,
    "rank_in_run": 1,
    "total_candidates_in_run": 42,
    "ranked_at": "2026-05-15T13:25:00Z",

    "score_breakdown": {
      "evaluation_overall_score": 8.6,
      "github_velocity_score": 9.1,
      "freshness_bonus": 0.3,
      "audience_fit_bonus": 0.4,
      "weak_evidence_penalty": 0.2,
      "already_posted_penalty": 0.0
    },

    "ranking_reasons": [
      "Strong developer relevance.",
      "High GitHub velocity.",
      "Clear explanation potential.",
      "Good fit for CS students."
    ]
  },

  "selection": {
    "eligible": true,
    "selected": true,
    "selected_at": "2026-05-15T13:28:00Z",
    "selection_id": "sel_33cc9021",
    "selected_for_platforms": ["linkedin", "instagram"],
    "not_selected_reason": null
  },

  "post_link": {
    "posted": true,
    "posted_project_id": "posted_proj_9f2a81c7",
    "post_ids": [
      "post_linkedin_20260515_001",
      "post_instagram_20260515_001"
    ],
    "posted_at": "2026-05-15T14:05:00Z"
  },

  "audit": {
    "created_at": "2026-05-15T13:00:00Z",
    "updated_at": "2026-05-15T14:05:00Z",
    "created_by": "candidate_intelligence_service",
    "updated_by": "selection_service",
    "schema_version": 1
  }
}
```

---

## 6. Candidate statuses

The `status` field in `candidate_repository_evaluations` should use clear lifecycle values.

```text
discovered
enriched
evaluation_pending
evaluated
skipped
ranked
selected
post_generation_requested
posted
rejected
failed
archived
```

Example skipped candidate:

```json
{
  "status": "skipped",
  "evaluation": {
    "skip": true,
    "skip_reason": "Repo is too early-stage and README does not explain usage."
  }
}
```

---

## 7. Ranking design

You should not physically sort documents inside the database.

Instead, store a ranking score and query the candidates sorted by that score.

Example query behavior:

```text
Get all candidates for run_2026_05_15_001
where evaluation.skip = false
and deduplication.already_posted = false
order by ranking.ranking_score descending
```

The ranking object should include:

```json
{
  "ranking": {
    "ranking_version": "ranker_v2",
    "ranking_score": 8.72,
    "rank_in_run": 1,
    "total_candidates_in_run": 42,
    "score_breakdown": {
      "evaluation_overall_score": 8.6,
      "github_velocity_score": 9.1,
      "freshness_bonus": 0.3,
      "audience_fit_bonus": 0.4,
      "weak_evidence_penalty": 0.2,
      "already_posted_penalty": 0.0
    }
  }
}
```

A simple ranking formula could be:

```text
ranking_score =
  0.35 * evaluation.overall
+ 0.20 * evaluation.developer_relevance
+ 0.15 * evaluation.student_learning_value
+ 0.10 * evaluation.explainability
+ 0.10 * github_velocity_score
+ 0.10 * freshness_score
- penalties
```

Possible penalties:

```text
already_posted_penalty
weak_readme_penalty
inactive_repo_penalty
missing_license_penalty
low_evidence_quality_penalty
duplicate_project_penalty
```

This lets you rank from best to worst while still understanding why each repo ranked highly.

---

## 8. Suggested indexes

### Indexes for `posted_repositories`

Recommended indexes:

```text
unique index on canonical_repo_key
index on project_id
index on posting_state.has_been_posted
index on posting_state.posted_platforms
index on posting_state.first_posted_at
index on post_instances.platform
index on github.owner
index on github.primary_language
index on project_description.tags
```

The most important index is:

```text
unique index on canonical_repo_key
```

That prevents reposting the same GitHub repo by accident.

### Indexes for `candidate_repository_evaluations`

Recommended indexes:

```text
index on run_id
index on project_id
index on candidate_id
unique index on run_id + canonical_repo_key
index on deduplication.canonical_repo_key
index on deduplication.already_posted
index on evaluation.skip
index on evaluation.scores.overall
index on ranking.ranking_score
compound index on run_id + ranking.ranking_score descending
compound index on run_id + evaluation.skip + ranking.ranking_score descending
index on selection.selected
index on github.primary_language
index on github.topics
index on source.source_type
```

The most important ranking query is:

```text
run_id + ranking.ranking_score descending
```

That gives you the ranked list from best to worst for each discovery run.

---

## 9. Partition key recommendation

Assuming these are NoSQL-style containers, such as Azure Cosmos DB containers or MongoDB-like collections:

### `posted_repositories`

Use:

```text
partition key: /project_id
```

This works well because each posted repo document is centered around one project.

Alternative:

```text
partition key: /canonical_repo_key
```

This is also valid if deduplication lookup is the most important operation.

My recommendation:

```text
/project_id
```

### `candidate_repository_evaluations`

Use:

```text
partition key: /run_id
```

This makes the main ranking query efficient:

```text
Get the top candidates from this run.
```

For project history, add secondary indexes on:

```text
project_id
canonical_repo_key
deduplication.canonical_repo_key
```

---

## 10. Data movement between the containers

The candidate container is the working area.

The posted container is the permanent historical archive.

```text
1. Discovery finds repo
   -> create document in candidate_repository_evaluations

2. Enrichment fetches README, metadata, activity
   -> update candidate document

3. Evaluation scores repo
   -> update candidate document

4. Ranking service ranks candidates
   -> update candidate ranking fields

5. Selection chooses best repo
   -> mark candidate as selected

6. Content and media services generate post package
   -> candidate may link to generated draft

7. Operator approves, exports, or posts
   -> create or update posted_repositories document

8. Candidate document gets post_link back to posted document
```

Important: when moving to the posted container, copy a snapshot. Do not only reference the candidate document.

---

## 11. Minimal MVP schema

The full schema above is robust, but you can start with a smaller version.

### Minimal `posted_repositories`

```json
{
  "id": "posted_proj_123",
  "project_id": "proj_123",
  "canonical_repo_key": "github:owner/repo",

  "github": {
    "owner": "owner",
    "repo": "repo",
    "url": "https://github.com/owner/repo",
    "description": "Repo description",
    "stars_count": 1200,
    "forks_count": 90,
    "primary_language": "TypeScript",
    "topics": ["ai", "developer-tools"]
  },

  "summary": "AI-generated summary.",
  "why_interesting": "Why this repo is worth posting.",

  "evaluation_snapshot": {
    "evaluation_id": "eval_123",
    "overall_score": 8.6,
    "novelty_score": 8,
    "explainability_score": 9,
    "audience": ["developers", "cs_students"]
  },

  "posts": [
    {
      "post_id": "post_123",
      "platform": "linkedin",
      "status": "manually_posted",
      "caption": "Final post text...",
      "hashtags": ["#OpenSource", "#AI"],
      "image_uri": "s3://reporadar/media/post_123.jpg",
      "alt_text": "Image alt text.",
      "posted_at": "2026-05-15T14:05:00Z",
      "external_post_url": "https://linkedin.com/..."
    }
  ],

  "created_at": "2026-05-15T13:40:00Z",
  "updated_at": "2026-05-15T14:05:00Z"
}
```

### Minimal `candidate_repository_evaluations`

```json
{
  "id": "cand_123",
  "run_id": "run_2026_05_15_001",
  "project_id": "proj_123",
  "canonical_repo_key": "github:owner/repo",

  "source": {
    "source_type": "github_discovery",
    "discovered_at": "2026-05-15T13:00:00Z"
  },

  "github": {
    "owner": "owner",
    "repo": "repo",
    "url": "https://github.com/owner/repo",
    "description": "Repo description",
    "stars_count": 1200,
    "forks_count": 90,
    "primary_language": "TypeScript",
    "topics": ["ai", "developer-tools"],
    "pushed_at": "2026-05-14T18:44:00Z"
  },

  "discovery_signals": {
    "star_delta_7d": 500,
    "growth_percent_7d": 62.5,
    "commit_count_7d": 24
  },

  "evaluation": {
    "evaluation_id": "eval_123",
    "summary": "AI-generated summary.",
    "why_interesting": "Why developers and students may care.",
    "scores": {
      "novelty": 8,
      "usefulness": 8,
      "explainability": 9,
      "developer_relevance": 9,
      "student_learning_value": 8,
      "overall": 8.6
    },
    "skip": false,
    "skip_reason": null,
    "model": "gpt-5.5-pro",
    "prompt_version": "repo_eval_v4"
  },

  "ranking": {
    "ranking_score": 8.72,
    "rank_in_run": 1,
    "total_candidates_in_run": 42
  },

  "selection": {
    "eligible": true,
    "selected": true,
    "selected_for_platforms": ["linkedin", "instagram"]
  },

  "posted": {
    "already_posted": false,
    "posted_project_id": null
  },

  "created_at": "2026-05-15T13:00:00Z",
  "updated_at": "2026-05-15T13:28:00Z"
}
```

---

## 12. How this supports the new microservice architecture

The two-container design can still support a modular microservice architecture if the schema is organized by service-owned sections.

```text
candidate_repository_evaluations
├── source              owned by Discovery
├── discovery           owned by Discovery
├── github              owned by Enrichment
├── enrichment          owned by Enrichment
├── deduplication       owned by Project Registry / Deduplication
├── evaluation          owned by Evaluation
├── ranking             owned by Selection / Ranking
├── selection           owned by Selection
└── post_link           owned by Publishing / Packaging

posted_repositories
├── github              snapshot from Enrichment
├── project_description snapshot from Evaluation / Content
├── source              links to source pipeline data
├── evaluation_snapshot snapshot from Evaluation
├── ranking_snapshot    snapshot from Selection
├── post_instances      owned by Packaging / Publishing
├── posting_state       owned by Publishing
└── audit               shared operational metadata
```

This gives you a practical starting point without over-engineering the database into many service-specific databases too early.

Later, if RepoRadar grows, these sections can be split into separate service-owned stores.

---

## 13. Future improvement: separate project identity

The main weakness of a strict two-container design is that project identity and deduplication are embedded inside both containers.

A future improvement would be to add a third container:

```text
projects
```

That container would own canonical project identity:

```json
{
  "project_id": "proj_9f2a81c7",
  "canonical_repo_key": "github:example/example-project",
  "canonical_repo_url": "https://github.com/example/example-project",
  "known_urls": [
    "https://github.com/example/example-project",
    "https://devpost.com/software/example-project"
  ],
  "first_seen_at": "2026-05-15T13:00:00Z",
  "last_seen_at": "2026-05-15T14:05:00Z",
  "already_posted": true,
  "posted_project_id": "posted_proj_9f2a81c7"
}
```

But I would not start there unless deduplication becomes painful.

For the MVP, two containers are enough.

---

## 14. Final recommendation

Use these two containers:

```text
posted_repositories
candidate_repository_evaluations
```

Make `candidate_repository_evaluations` the working pipeline store:

```text
discovery
enrichment
evaluation
ranking
selection
skip reasons
post links
```

Make `posted_repositories` the permanent historical archive:

```text
repo snapshot
final caption/commentary
platforms posted to
image metadata
alt text
publication status
external post URL
evaluation snapshot
ranking snapshot
```

This design is simple enough for the current project but structured enough to support the modular microservice architecture later.

The most important principle is:

```text
Candidate documents help RepoRadar decide what to post.
Posted documents preserve what RepoRadar actually posted.
```
