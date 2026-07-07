"""Deterministic CV PDF → markdown conversion for LLM scoring."""
from __future__ import annotations

import re
from pathlib import Path

DEFAULT_CV_DIR = Path("cv")


def find_cv_pdf(cv_dir: str | Path = DEFAULT_CV_DIR) -> Path | None:
    """Return the sole PDF in cv_dir, or None. Raises if multiple PDFs."""
    root = Path(cv_dir)
    if not root.is_dir():
        return None
    pdfs = sorted(root.glob("*.pdf"))
    if not pdfs:
        return None
    if len(pdfs) > 1:
        names = ", ".join(p.name for p in pdfs)
        raise ValueError(f"Expected one PDF in '{root}', found: {names}")
    return pdfs[0]


def find_cv_markdown(cv_dir: str | Path = DEFAULT_CV_DIR) -> Path | None:
    """Return markdown paired with the PDF, or a lone .md in cv_dir (not README)."""
    root = Path(cv_dir)
    pdf = find_cv_pdf(root)
    if pdf is not None:
        return pdf.with_suffix(".md")
    mds = sorted(
        p for p in root.glob("*.md")
        if p.name.lower() != "readme.md"
    )
    if not mds:
        return None
    if len(mds) > 1:
        names = ", ".join(p.name for p in mds)
        raise ValueError(f"Expected one CV markdown in '{root}', found: {names}")
    return mds[0]


def pdf_to_markdown(pdf_path: Path) -> str:
    import pymupdf4llm

    raw = pymupdf4llm.to_markdown(str(pdf_path))
    return normalize_markdown(raw)


def normalize_markdown(text: str) -> str:
    """Light cleanup after PDF extraction."""
    text = text.replace("\r\n", "\n").strip()
    text = re.sub(r"\n{3,}", "\n\n", text)
    return f"{text}\n"


def needs_regeneration(pdf_path: Path, md_path: Path) -> bool:
    if not md_path.exists():
        return True
    return pdf_path.stat().st_mtime > md_path.stat().st_mtime


def ensure_cv_markdown(
    cv_dir: str | Path = DEFAULT_CV_DIR,
    *,
    force: bool = False,
) -> Path:
    """Write <pdf-stem>.md from the PDF in cv_dir. Returns markdown path."""
    pdf_path = find_cv_pdf(cv_dir)
    if pdf_path is None:
        md_path = find_cv_markdown(cv_dir)
        if md_path and md_path.exists():
            return md_path
        raise FileNotFoundError(f"No PDF in '{cv_dir}' and no CV markdown found.")

    md_path = pdf_path.with_suffix(".md")
    if force or needs_regeneration(pdf_path, md_path):
        md_path.parent.mkdir(parents=True, exist_ok=True)
        md_path.write_text(pdf_to_markdown(pdf_path), encoding="utf-8")
    return md_path
