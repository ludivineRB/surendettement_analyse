"""Public contracts for the conversational assistant service."""

from typing import Literal
from uuid import UUID

from pydantic import BaseModel, Field


class AnswerRequest(BaseModel):
    question: str = Field(min_length=3, max_length=2_000)
    conversation_id: UUID | None = None


class SourceReference(BaseModel):
    title: str
    url: str
    publisher: str
    reference_period: str | None = None


class DataReference(BaseModel):
    indicator_code: str
    territory: str
    reference_period: str


class AnswerResponse(BaseModel):
    answer: str
    sources: list[SourceReference] = Field(default_factory=list)
    data_references: list[DataReference] = Field(default_factory=list)
    method: Literal["documents", "analytics", "hybrid"]
    request_id: UUID


class ServiceUnavailableResponse(BaseModel):
    status: Literal["not_ready"]
    detail: str
    request_id: UUID


class RetrievalRequest(BaseModel):
    query: str = Field(min_length=2, max_length=500)
    limit: int = Field(default=5, ge=1, le=20)


class RetrievalHit(BaseModel):
    chunk_id: str
    source_id: str
    source_url: str
    source_title: str
    publisher: str
    reference_period: str
    geographic_scope: str
    section: str
    content: str
    rank: float


class RetrievalResponse(BaseModel):
    query: str
    results: list[RetrievalHit]
