"""Bootstrap: convert the PDF in cv/ to sibling markdown for LLM scoring.

Usage:
    python -m jobhunt.scripts.cv_from_pdf          # convert if PDF is new/missing md
    python -m jobhunt.scripts.cv_from_pdf --force  # always regenerate

Drop any single .pdf in the cv/ folder (see config.yaml cv.dir).
"""
from __future__ import annotations

import argparse
import sys
from pathlib import Path

import yaml

from jobhunt.cv_convert import ensure_cv_markdown


def _cv_dir(config_path: Path) -> str:
    raw = yaml.safe_load(config_path.read_text()) if config_path.exists() else {}
    cv = raw.get("cv", {}) or {}
    return cv.get("dir", "cv")


def main() -> None:
    parser = argparse.ArgumentParser(description="Convert CV PDF to markdown.")
    parser.add_argument(
        "--force", action="store_true", help="Regenerate markdown even if up to date."
    )
    parser.add_argument(
        "--config", default="config.yaml", help="Config file (default: config.yaml)."
    )
    args = parser.parse_args()

    try:
        md_path = ensure_cv_markdown(_cv_dir(Path(args.config)), force=args.force)
    except (FileNotFoundError, ValueError) as e:
        print(f"error: {e}", file=sys.stderr)
        sys.exit(1)

    print(f"wrote {md_path} ({md_path.stat().st_size} bytes)")


if __name__ == "__main__":
    main()
