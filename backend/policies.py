"""Shoppie's policies, split into sections the agent can look up."""

import re
from pathlib import Path

POLICY_DIRECTORY = Path(__file__).resolve().parent.parent / "docs"
POLICY_FILES = {
    "shopping": "shopping-policy.md",
    "cancellation": "cancellation-policy.md",
    "returns": "returns-policy.md",
}
HEADING = re.compile(r"^(#{2,3}) (.+)$", re.MULTILINE)


def slug(title: str) -> str:
    """Turn a section heading into a stable id."""
    return re.sub(r"[^a-z0-9]+", "-", title.casefold()).strip("-")


def policy_name(policy: str) -> str:
    """Return a policy's title from its first heading."""
    text = (POLICY_DIRECTORY / POLICY_FILES[policy]).read_text(encoding="utf-8")
    return text.splitlines()[0].removeprefix("# ")


def sections(policy: str) -> list[dict[str, str]]:
    """Split a policy into sections that run to the next heading of their level."""
    text = (POLICY_DIRECTORY / POLICY_FILES[policy]).read_text(encoding="utf-8")
    headings = list(HEADING.finditer(text))
    result = []
    for index, heading in enumerate(headings):
        level = len(heading.group(1))
        end = next(
            (
                later.start()
                for later in headings[index + 1 :]
                if len(later.group(1)) <= level
            ),
            len(text),
        )
        title = heading.group(2).strip()
        result.append(
            {"id": slug(title), "title": title, "content": text[heading.start() : end]}
        )
    return result


def list_policies() -> list[dict[str, object]]:
    """Return every policy with the ids and titles of its sections."""
    return [
        {
            "policy": policy,
            "name": policy_name(policy),
            "sections": [
                {"id": section["id"], "title": section["title"]}
                for section in sections(policy)
            ],
        }
        for policy in POLICY_FILES
    ]


def read_section(policy: str, section_id: str) -> dict[str, str] | None:
    """Return one section of a policy, or None if there is no such section."""
    if policy not in POLICY_FILES:
        return None
    for section in sections(policy):
        if section["id"] == section_id:
            return {
                "policy": policy,
                "name": policy_name(policy),
                "title": section["title"],
                "content": section["content"],
            }
    return None
