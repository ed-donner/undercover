"""Allowlisted section lookup with immutable per-attempt read records."""

from __future__ import annotations

import re
import sqlite3
from pathlib import Path
from typing import TYPE_CHECKING

from fastapi import HTTPException
from pydantic import BaseModel, Field

from backend.contracts import Input
from backend.run_state import active_attempt, now, require

if TYPE_CHECKING:
    from backend.store import Store

SOURCES = {"wording": "policy_wording.md", "manual": "claims_manual.md"}


class SectionInfo(BaseModel):
    document_id: str
    version: str
    section: int
    title: str


class SectionText(SectionInfo):
    text: str


class SearchInput(Input):
    document_id: str
    query: str = Field(max_length=200)


class SearchHit(SectionInfo):
    excerpt: str


class ReadInput(Input):
    run_id: str
    document_id: str
    section: int


class ReadRecord(SectionText):
    sequence: int
    run_id: str
    claim_id: str
    read_at: str


def seed_documents(connection: sqlite3.Connection, data_dir: Path) -> None:
    for document_id, filename in SOURCES.items():
        if connection.execute(
            "SELECT 1 FROM document_sections WHERE document_id = ?", (document_id,)
        ).fetchone():
            continue
        text = (data_dir / filename).read_text()
        version = re.search(r"Version (\d+\.\d+)", text)
        if version is None:
            raise ValueError("Document has no version")
        headings = list(re.finditer(r"^## (\d+)\. (.+)$", text, re.MULTILINE))
        for index, heading in enumerate(headings):
            end = (
                headings[index + 1].start() if index + 1 < len(headings) else len(text)
            )
            connection.execute(
                "INSERT INTO document_sections VALUES (?, ?, ?, ?, ?)",
                (
                    document_id,
                    version[1],
                    int(heading[1]),
                    heading[2],
                    text[heading.start() : end].strip(),
                ),
            )


class Documents:
    def __init__(self, store: Store):
        self.store = store

    def sections(self, document_id: str) -> list[SectionText]:
        if document_id not in SOURCES:
            raise HTTPException(404, "Document not found")
        with self.store.connect() as connection:
            rows = connection.execute(
                "SELECT * FROM document_sections "
                "WHERE document_id = ? ORDER BY section",
                (document_id,),
            ).fetchall()
        return [SectionText.model_validate(dict(row)) for row in rows]

    def catalog(self) -> list[SectionInfo]:
        return [
            SectionInfo.model_validate(s.model_dump())
            for key in SOURCES
            for s in self.sections(key)
        ]

    def section(self, document_id: str, number: int) -> SectionText:
        section = next(
            (s for s in self.sections(document_id) if s.section == number), None
        )
        if section is None:
            raise HTTPException(404, "Section not found")
        return section

    def search(self, request: SearchInput) -> list[SearchHit]:
        words = set(re.findall(r"\w+", request.query.lower()))
        results = []
        for section in self.sections(request.document_id):
            match = next((w for w in sorted(words) if w in section.text.lower()), None)
            if match:
                offset = max(0, section.text.lower().find(match) - 60)
                results.append(
                    SearchHit(
                        **section.model_dump(exclude={"text"}),
                        excerpt=section.text[offset : offset + 240],
                    )
                )
        return results

    def read(self, claim_id: str, request: ReadInput) -> SectionText:
        section = self.section(request.document_id, request.section)
        with self.store.transaction() as connection:
            run = active_attempt(connection, request.run_id)
            require(run["claim_id"] == claim_id, "Read must belong to this claim")
            connection.execute(
                "INSERT INTO document_reads "
                "(run_id, claim_id, document_id, version, section, "
                "title, text, read_at) "
                "VALUES (?, ?, ?, ?, ?, ?, ?, ?)",
                (
                    request.run_id,
                    claim_id,
                    section.document_id,
                    section.version,
                    section.section,
                    section.title,
                    section.text,
                    now(),
                ),
            )
            connection.execute(
                "INSERT INTO events (run_id, kind, label, created_at) "
                "VALUES (?, 'section_read', ?, ?)",
                (
                    request.run_id,
                    f"Read {section.document_id} {section.version}, "
                    f"section {section.section}: {section.title}",
                    now(),
                ),
            )
        return section

    def reads(self, claim_id: str) -> list[ReadRecord]:
        self.store.claim(claim_id)
        with self.store.connect() as connection:
            rows = connection.execute(
                "SELECT * FROM document_reads WHERE claim_id = ? ORDER BY sequence",
                (claim_id,),
            ).fetchall()
        return [ReadRecord.model_validate(dict(row)) for row in rows]


def validate_references(
    connection: sqlite3.Connection,
    run_id: str,
    policy_sections: list[int],
    manual_sections: list[int],
    manual_version: str | None,
) -> None:
    rows = connection.execute(
        "SELECT document_id, version, section FROM document_reads WHERE run_id = ?",
        (run_id,),
    ).fetchall()
    read = {(r["document_id"], r["section"]) for r in rows}
    require(
        bool(manual_sections) and manual_version is not None,
        "Read and cite the claims manual",
    )
    require(
        all(("wording", s) in read for s in policy_sections),
        "Read cited wording sections first",
    )
    require(
        all(("manual", s) in read for s in manual_sections),
        "Read cited manual sections first",
    )
    versions = {r["version"] for r in rows if r["document_id"] == "manual"}
    require(manual_version in versions, "Manual version must match the sections read")
