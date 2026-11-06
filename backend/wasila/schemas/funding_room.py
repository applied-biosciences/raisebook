"""Funding Room request and response shapes (``/v1/funding-room``)."""

from __future__ import annotations

from typing import Any, Literal
from uuid import UUID

from pydantic import Field

from wasila.schemas.common import APIModel, StrictInput, Timestamp

Category = Literal[
    "pitch",
    "corporate",
    "financial",
    "technical",
    "clinical",
    "regulatory",
    "ip",
    "cybersecurity",
    "data_protection",
    "commercial",
    "legal",
    "tax_relief",
    "other",
]
Confidentiality = Literal["public", "investors", "nda", "restricted"]
ReviewStatus = Literal["draft", "in_review", "approved", "archived"]
DocJurisdiction = Literal["all", "us", "uk", "ksa"]


class DocumentCreate(StrictInput):
    title: str = Field(..., min_length=1, max_length=200)
    category: Category
    folder: str | None = Field(None, max_length=120)
    description: str | None = Field(None, max_length=4000)
    confidentiality: Confidentiality = "investors"
    review_status: ReviewStatus = "draft"
    jurisdiction: DocJurisdiction = "all"


class DocumentUpdate(StrictInput):
    title: str | None = Field(None, min_length=1, max_length=200)
    category: Category | None = None
    folder: str | None = Field(None, max_length=120)
    description: str | None = Field(None, max_length=4000)
    confidentiality: Confidentiality | None = None
    review_status: ReviewStatus | None = None
    jurisdiction: DocJurisdiction | None = None


class VersionOut(APIModel):
    version: int
    filename: str
    content_type: str
    size_bytes: int
    sha256: str
    note: str | None
    created_at: Timestamp
    actor_label: str | None = None


class DocumentOut(APIModel):
    id: UUID
    title: str
    category: str
    category_label: str
    folder: str | None
    description: str | None
    confidentiality: str
    review_status: str
    jurisdiction: str
    is_deck: bool
    current_version: int
    latest: VersionOut | None = None
    reviewed_at: Timestamp | None
    created_at: Timestamp
    updated_at: Timestamp


class DocumentList(APIModel):
    data: list[DocumentOut]
    counts: dict[str, int]
    categories: dict[str, str]


class VersionList(APIModel):
    data: list[VersionOut]


class LinkCreate(StrictInput):
    label: str = Field(..., min_length=1, max_length=120)
    document_ids: list[UUID] = Field(..., min_length=1, max_length=50)
    investor_id: UUID | None = None
    days: int = Field(14, ge=1, le=90)


class LinkOut(APIModel):
    id: UUID
    label: str
    investor_id: UUID | None
    document_ids: list[UUID]
    expires_at: Timestamp
    revoked_at: Timestamp | None
    view_count: int
    last_viewed_at: Timestamp | None
    state: str
    created_at: Timestamp


class LinkCreated(LinkOut):
    token: str = Field(..., description="Shown once. The share URL is <web>/room/<token>.")


class LinkList(APIModel):
    data: list[LinkOut]


class EventOut(APIModel):
    id: UUID
    document_id: UUID | None
    kind: str
    data: dict[str, Any]
    actor_type: str
    actor_label: str | None
    created_at: Timestamp


class EventList(APIModel):
    data: list[EventOut]


class ChecklistItem(APIModel):
    key: str
    label: str
    category: str
    status: Literal["missing", "present", "approved"]
    document_ids: list[str]


class Checklist(APIModel):
    jurisdiction: str
    items: list[ChecklistItem]


class PublicDocument(APIModel):
    id: UUID
    title: str
    category_label: str
    description: str | None
    filename: str
    size_bytes: int


class PublicRoom(APIModel):
    company: str
    label: str
    expires_at: Timestamp
    documents: list[PublicDocument]
