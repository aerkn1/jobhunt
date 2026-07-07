"""The single normalized job record every source produces."""
from __future__ import annotations

from dataclasses import dataclass, field


@dataclass
class JobPost:
    position: str
    company: str
    url: str                      # canonicalized; this is the dedupe key
    source: str                   # indeed | linkedin | google | visa_repo
    location: str = ""
    country: str = ""
    salary: str | None = None
    remote: bool = False
    visa: str = "unknown"         # yes | no | unknown
    post_date: str | None = None
    description: str = ""

    @property
    def role(self) -> str:
        return self.position

    def summary(self) -> str:
        """Compact text handed to the scoring model."""
        parts = [
            f"Role: {self.role}",
            f"Company: {self.company}",
            f"Location: {self.location} ({self.country})",
            f"Remote: {self.remote}",
            f"Salary: {self.salary or 'n/a'}",
            "",
            self.description[:6000],
        ]
        return "\n".join(parts)
