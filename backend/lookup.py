"""Look up sections of the claims manual and the policy wording."""

import re
from functools import cache
from typing import Literal, TypedDict

from backend.db import DATA

Document = Literal["manual", "wording"]
FILES = {"manual": "claims_manual.md", "wording": "policy_wording.md"}
MAX_RESULTS = 5
SNIPPET_LENGTH = 160
MIN_TERM_LENGTH = 3


class Section(TypedDict):
    """One numbered section of a document."""

    number: int
    title: str
    text: str


@cache
def sections(document: Document) -> list[Section]:
    """Split a document on its numbered `## ` headings."""
    text = (DATA / FILES[document]).read_text(encoding="utf-8")
    found: list[Section] = []
    for part in re.split(r"^## ", text, flags=re.MULTILINE)[1:]:
        heading, _, body = part.partition("\n")
        number, _, title = heading.partition(". ")
        found.append(
            {"number": int(number), "title": title.strip(), "text": body.strip()}
        )
    return found


def terms(query: str) -> list[str]:
    """Reduce a query to lower-case words with a trailing s removed."""
    words = re.findall(r"[a-z0-9]+", query.lower())
    return [w.rstrip("s") for w in words if len(w) >= MIN_TERM_LENGTH]


def snippet(text: str, words: list[str]) -> str:
    """Return the first line of the text that holds one of the words."""
    for line in text.splitlines():
        if any(w in line.lower() for w in words):
            return line.strip()[:SNIPPET_LENGTH]
    return ""


def search(document: Document, query: str) -> list[dict[str, str | int]]:
    """Return the best matching sections as number, title and a short snippet."""
    words = terms(query)
    scored: list[tuple[int, Section]] = []
    for section in sections(document):
        haystack = f"{section['title']} {section['text']}".lower()
        score = sum(haystack.count(w) for w in words)
        if score:
            scored.append((score, section))
    scored.sort(key=lambda pair: -pair[0])
    return [
        {
            "number": s["number"],
            "title": s["title"],
            "snippet": snippet(s["text"], words),
        }
        for _, s in scored[:MAX_RESULTS]
    ]
