from pydantic import BaseModel, ConfigDict, Field


class IngestRequest(BaseModel):
    model_config = ConfigDict(extra="ignore")

    filename: str = Field(min_length=1, description="Original filename of the document")
    content: str = Field(min_length=1, description="Raw markdown text to ingest")


class IngestResponse(BaseModel):
    document_id: int
    chunk_count: int
    status: str


class SearchRequest(BaseModel):
    model_config = ConfigDict(extra="ignore")

    query: str = Field(min_length=1)
    limit: int = Field(default=5, ge=1, le=20)


class SearchResult(BaseModel):
    chunk_id: int
    document_filename: str
    heading_path: str | None
    content: str
    score: float


class SearchResponse(BaseModel):
    results: list[SearchResult]
