"""Configuration loader.

Non-secret knobs come from config.yaml (committed, versioned, readable).
Secrets come from environment variables (GitHub Secrets at runtime).
The two never mix: nothing sensitive is ever read from the YAML file.
"""
from __future__ import annotations

import os
from pathlib import Path

import yaml

from .cv_convert import ensure_cv_markdown, find_cv_markdown, find_cv_pdf


def _clean_list(items) -> list[str]:
    return [str(x).strip() for x in (items or []) if str(x).strip()]


class Config:
    def __init__(self, path: str | Path = "config.yaml"):
        raw = yaml.safe_load(Path(path).read_text())

        targets = raw.get("targets", {})
        self.countries: list[str] = _clean_list(targets.get("countries"))
        self.titles: list[str] = _clean_list(targets.get("titles"))
        if not self.countries or not self.titles:
            raise ValueError("config.yaml: 'countries' and 'titles' must be non-empty")

        scoring = raw.get("scoring", {})
        self.threshold: int = max(0, min(100, int(scoring.get("fit_threshold", 80))))
        self.hours_old: int = int(scoring.get("hours_old", 12))
        self.max_jobs_per_query: int = int(scoring.get("max_jobs_per_query", 25))
        self.seen_log: str = scoring.get("seen_log", ".jobhunt/seen.jsonl")

        llm = raw.get("llm", {}) or {}
        self.llm_model: str = llm.get("model", "gpt-4o-mini")
        score_llm = llm.get("score", {}) or {}
        self.llm_score_max_tokens: int = int(score_llm.get("max_tokens", 200))
        self.llm_score_temperature: float = float(score_llm.get("temperature", 0))
        draft_llm = llm.get("draft", {}) or {}
        self.llm_draft_max_tokens: int = int(draft_llm.get("max_tokens", 1600))
        self.llm_draft_temperature: float = float(draft_llm.get("temperature", 0.7))

        sources = raw.get("sources", {})
        self.boards: list[str] = _clean_list(sources.get("boards")) or ["indeed"]
        visa = sources.get("visa_repo", {}) or {}
        self.visa_enabled: bool = bool(visa.get("enabled", True))
        self.visa_url: str = visa.get(
            "url",
            "https://github.com/Lamiiine/Awesome-daily-list-of-visa-sponsored-jobs",
        )
        self.visa_fetch_job_page: bool = bool(visa.get("fetch_job_page", True))
        self.visa_fetch_timeout: int = int(visa.get("fetch_timeout_sec", 10))
        self.visa_fetch_max_concurrent: int = max(
            1, int(visa.get("max_concurrent", 3)),
        )

        notion = raw.get("notion", {})
        self.new_lane: str = notion.get("new_lane", "New")

        cv = raw.get("cv", {}) or {}
        self.cv_dir: str = cv.get("dir", "cv")
        # legacy single-file path; used only when cv/ has no PDF or markdown
        self.cv_path: str = raw.get("cv_path", "cv.md")

        # ---- secrets: environment only, never the YAML ----
        self.notion_token = os.environ["NOTION_TOKEN"]
        self.notion_db_id = os.environ["NOTION_DB_ID"]
        self.llm_key = os.environ["LLM_API_KEY"]
        self.telegram_token = os.environ.get("TELEGRAM_TOKEN")
        self.telegram_chat_id = os.environ.get("TELEGRAM_CHAT_ID")

    def load_cv(self) -> str:
        """CV text: prefer CV_TEXT secret, else markdown from cv/ (PDF if present)."""
        env_cv = os.environ.get("CV_TEXT")
        if env_cv and env_cv.strip():
            return env_cv

        cv_dir = Path(self.cv_dir)
        try:
            if find_cv_pdf(cv_dir) is not None:
                md_path = ensure_cv_markdown(cv_dir)
                return md_path.read_text(encoding="utf-8")
            md_path = find_cv_markdown(cv_dir)
            if md_path and md_path.exists():
                return md_path.read_text(encoding="utf-8")
        except ValueError as e:
            raise FileNotFoundError(str(e)) from e

        legacy = Path(self.cv_path)
        if legacy.exists():
            return legacy.read_text(encoding="utf-8")

        raise FileNotFoundError(
            f"No CV found: put one PDF in '{cv_dir}/', commit markdown there, "
            f"or set CV_TEXT."
        )


cfg = Config()
