# CV folder

Place **one** resume PDF here (any filename). The pipeline generates **`<name>.md`**
alongside it for LLM scoring (deterministic conversion, no extra API calls).

```bash
# one-time or after you update the PDF:
python -m jobhunt.scripts.cv_from_pdf

# force regenerate:
python -m jobhunt.scripts.cv_from_pdf --force
```

`discover` / `approve` also refresh the markdown automatically when the PDF is newer.

**CI tip:** PDFs are gitignored by default. For GitHub Actions, commit the generated
`.md`, include the PDF in a private repo, or set the `CV_TEXT` secret.
