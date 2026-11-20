"""Source-document HTTP adapters."""

from fastapi import APIRouter

from backend.dependencies import Database
from backend.documents import (
    Documents,
    SearchHit,
    SearchInput,
    SectionInfo,
    SectionText,
)

router = APIRouter()


@router.get("/documents", operation_id="list_document_sections")
def document_catalog(db: Database) -> list[SectionInfo]:
    """List section titles and versions of the two approved source documents."""
    return Documents(db).catalog()


@router.post("/documents/search", operation_id="search_document_sections")
def search_documents(search: SearchInput, db: Database) -> list[SearchHit]:
    """Find source sections by keyword without sending complete documents."""
    return Documents(db).search(search)


@router.get(
    "/documents/{document_id}/sections/{section}", operation_id="get_document_section"
)
def get_document_section(document_id: str, section: int, db: Database) -> SectionText:
    """Read a complete source section for a handler without claiming agent access."""
    return Documents(db).section(document_id, section)
