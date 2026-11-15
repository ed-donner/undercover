"""The claims manual and the policy wording, split into numbered sections."""

import re
from typing import Literal

from backend.db import DATA

Document = Literal["claims_manual", "policy_wording"]

HEADING = re.compile(r"^## (\d+)\. (.+)$", re.MULTILINE)


def sections(document: Document) -> list[dict[str, str | int]]:
    """Split a document on its numbered headings."""
    text = (DATA / f"{document}.md").read_text()
    found = list(HEADING.finditer(text))
    ends = [m.start() for m in found[1:]] + [len(text)]
    return [
        {
            "number": int(m.group(1)),
            "title": m.group(2),
            "text": text[m.start() : end].strip(),
        }
        for m, end in zip(found, ends, strict=True)
    ]
