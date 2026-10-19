"""The policy wording and the claims manual, split into numbered sections."""

import re
from functools import cache

from backend.db import DATA
from backend.models import Section

FILES = {"wording": "policy_wording.md", "manual": "claims_manual.md"}
HEADING = re.compile(r"^## (\d+)\. (.+)$", re.MULTILINE)


@cache
def sections(document: str) -> dict[int, tuple[str, str]]:
    """Map each section number to its title and its text, heading first."""
    text = (DATA / FILES[document]).read_text(encoding="utf-8")
    headings = list(HEADING.finditer(text))
    found = {0: ("Introduction", text[: headings[0].start()].strip())}
    for heading, following in zip(headings, [*headings[1:], None], strict=False):
        end = following.start() if following else len(text)
        found[int(heading[1])] = (heading[2], text[heading.start() : end].strip())
    return found


def listing(document: str) -> list[Section]:
    return [
        Section(number=number, title=title)
        for number, (title, _) in sections(document).items()
    ]


def section_text(document: str, number: int) -> str | None:
    found = sections(document).get(number)
    return found[1] if found else None
