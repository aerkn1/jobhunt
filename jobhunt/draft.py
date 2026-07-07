"""Generate a tailored CV summary + cover letter for an approved job.

Never fabricates: the prompt is constrained to reuse only what's in the CV.
"""
from __future__ import annotations

from .config import cfg
from .llm import complete
from .models import JobPost

_SYSTEM = (
    "You tailor job applications. Use ONLY facts present in the candidate's CV. "
    "Never invent experience, employers, dates, metrics, or skills. If the job "
    "wants something the CV lacks, omit it rather than fabricate."
)

_PROMPT = """CANDIDATE CV:
{cv}

TARGET JOB:
{job}

Produce two sections separated by the exact line '---COVER---':
1) A tailored CV summary + reordered highlight bullets emphasising the overlap
   with this job (plain text, no fabrication).
2) A concise cover letter (<=200 words) in the candidate's voice.
Output the two sections only."""


def generate(job: JobPost, cv: str) -> tuple[str, str]:
    out = complete(
        _PROMPT.format(cv=cv, job=job.summary()),
        system=_SYSTEM,
        max_tokens=cfg.llm_draft_max_tokens,
        temperature=cfg.llm_draft_temperature,
    )
    if "---COVER---" in out:
        tailored, cover = out.split("---COVER---", 1)
    else:
        tailored, cover = out, ""
    return tailored.strip(), cover.strip()
