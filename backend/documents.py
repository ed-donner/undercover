"""The policy wording and the claims manual, section by section."""

import re
from typing import Any, Literal

from backend.db import DATA

Document = Literal["policy_wording", "claims_manual"]
DOCUMENTS: tuple[Document, ...] = ("policy_wording", "claims_manual")
HEADING = re.compile(r"^## (\d+)\. (.+)$", re.MULTILINE)
MOST_RESULTS = 5
LINES_PER_RESULT = 2
SHORTEST_PLURAL = 5


def split(document: Document) -> list[dict[str, Any]]:
    """Split a document into its numbered sections."""
    text = (DATA / f"{document}.md").read_text(encoding="utf-8")
    headings = list(HEADING.finditer(text))
    ends = [heading.start() for heading in headings[1:]] + [len(text)]
    return [
        {
            "document": document,
            "section": int(heading[1]),
            "title": heading[2],
            "text": text[heading.end() : end].strip(),
        }
        for heading, end in zip(headings, ends, strict=True)
    ]


SECTIONS = [section for document in DOCUMENTS for section in split(document)]


def contents() -> list[dict[str, Any]]:
    """List every section's document, number and title."""
    return [
        {key: section[key] for key in ("document", "section", "title")}
        for section in SECTIONS
    ]


def find(document: Document, number: int) -> dict[str, Any] | None:
    """Return one section, or None if the document has no such section."""
    return next(
        (
            section
            for section in SECTIONS
            if section["document"] == document and section["section"] == number
        ),
        None,
    )


def stems(query: str) -> list[str]:
    """Reduce a query to the starts of its words, so 'animals' finds 'animal'."""
    words = re.findall(r"[a-z0-9$]+", query.lower())
    return [
        word.removesuffix("s") if len(word) >= SHORTEST_PLURAL else word
        for word in words
    ]


def hits(stem: str, text: str) -> int:
    """Count the words in the text that start with the stem."""
    return len(re.findall(rf"\b{re.escape(stem)}", text.lower()))


def search(query: str) -> list[dict[str, Any]]:
    """Rank the sections by the query's words, with rare words counting most."""
    sections = [
        (section, f"{section['title']}\n{section['text']}") for section in SECTIONS
    ]
    weights = {}
    for stem in stems(query):
        found = sum(1 for _, text in sections if hits(stem, text))
        if found:
            weights[stem] = 1 / found

    def score(text: str) -> float:
        return sum(weight * hits(stem, text) for stem, weight in weights.items())

    ranked = sorted(
        ((score(text), section) for section, text in sections),
        key=lambda pair: pair[0],
        reverse=True,
    )
    return [
        {
            **{key: section[key] for key in ("document", "section", "title")},
            "lines": [
                line
                for line in sorted(
                    section["text"].splitlines(), key=score, reverse=True
                )
                if score(line)
            ][:LINES_PER_RESULT],
        }
        for points, section in ranked[:MOST_RESULTS]
        if points
    ]
