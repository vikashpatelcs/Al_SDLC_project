"""
DocumentChunk schema for parsed document sections with traceability metadata.
"""
from typing import Optional
from pydantic import BaseModel, Field


class DocumentChunk(BaseModel):
    chunk_id: str = Field(description="Unique deterministic or sequential chunk ID for requirement linking")
    source_file: str = Field(description="Original filename or document path")
    text: str = Field(description="Cleaned, extracted text content of the chunk")
    page_or_section: Optional[str] = Field(default=None, description="Page number or section header")
    is_masked: bool = Field(default=False, description="Whether PII masking has been applied")
