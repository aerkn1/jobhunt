"""Score a job 0-100 against the candidate's CV, with a one-line rationale."""
from __future__ import annotations

import json
import re

from .config import cfg
from .llm import complete
from .models import JobPost

_PROMPT = """You are screening a job for a candidate against their CV.

=== CV ===
{cv}

=== JOB ===
{job}

Score genuine fit 0-100. Weigh: tech-stack overlap, seniority match,
and whether the location / visa situation is realistic for the candidate.
Be strict: 80+ means a strong, worth-applying match.

Return ONLY a JSON object, no prose, no markdown fences:
{{"score": <int 0-100>, "reason": "<one sentence, <=25 words>"}}"""


def _parse(raw: str) -> tuple[int, str]:
    raw = raw.strip()
    raw = re.sub(r"^```(?:json)?|```$", "", raw, flags=re.MULTILINE).strip()
    m = re.search(r"\{.*\}", raw, re.DOTALL)
    data = json.loads(m.group(0) if m else raw)
    score = max(0, min(100, int(data["score"])))
    reason = str(data.get("reason", "")).strip()[:200]
    return score, reason


def score(job: JobPost, cv: str) -> tuple[int, str]:
    try:
        return _parse(complete(
            _PROMPT.format(cv=cv, job=job.summary()),
            max_tokens=cfg.llm_score_max_tokens,
            temperature=cfg.llm_score_temperature,
            json_mode=True,
        ))
    except Exception as e:  # never let one bad score kill the run
        return 0, f"scoring error: {e}"
