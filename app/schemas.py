"""
Pydantic Schemas for Request & Response Validation.

================================================================================
TWO-LEVEL VALIDATION DESIGN RATIONALE:
================================================================================
1. Level 1 Validation (HTTP Layer / Pydantic):
   - Scope: Evaluates structural integrity of incoming API payloads (e.g. valid JSON,
     required top-level parameters, recipient list bounds [1..10000], layout coordinate bounds [0..100]).
   - Outcome: Any structural deviation immediately raises a Pydantic ValidationError,
     returning HTTP 422 Unprocessable Entity to the client.

2. Level 2 Validation (Service / Worker Layer):
   - Scope: Evaluates per-recipient data quality (e.g. empty names, invalid email formats, string encoding errors).
   - Design Decision: RecipientIn uses basic string types (str) for name and email rather than strict Pydantic
     types like EmailStr.
   - Outcome: A job request containing one or more bad recipient emails or malformed records IS NOT REJECTED
     at the HTTP interface. Instead, the job is accepted (HTTP 202), and individual recipients are evaluated
     asynchronously inside their own isolated try/except blocks.
   - Fault Tolerance: If an individual recipient fails validation or rendering, it is recorded in the database
     with status='failed' and a detailed error_message. Valid certificates in the same job continue to generate
     and succeed without interrupting the overall batch process.
================================================================================
"""

from datetime import datetime, date
from enum import Enum
from typing import List, Optional
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field


class TemplateLayout(BaseModel):
    """Layout coordinates for text positioning on certificate canvas as percentages (0 to 100)."""

    name_y: float = Field(
        ...,
        ge=0.0,
        le=100.0,
        description="Vertical Y position for recipient name as a percentage (0-100)",
    )
    course_y: float = Field(
        ...,
        ge=0.0,
        le=100.0,
        description="Vertical Y position for course title as a percentage (0-100)",
    )
    date_y: float = Field(
        ...,
        ge=0.0,
        le=100.0,
        description="Vertical Y position for issue date as a percentage (0-100)",
    )

    model_config = ConfigDict(from_attributes=True)


class RecipientIn(BaseModel):
    """
    Recipient input payload.

    Note: Fields 'name' and 'email' use lenient 'str' validation to allow Level 2 per-recipient error handling
    in the background worker without rejecting the entire HTTP batch request.
    """

    name: str = Field(..., description="Recipient full name")
    email: str = Field(..., description="Recipient email address")


class JobCreate(BaseModel):
    """Payload for creating a new bulk certificate generation job."""

    title: str = Field(..., min_length=1, max_length=255, description="Job / Event title")
    organization_name: Optional[str] = Field(
        None, max_length=255, description="Optional organization or issuer name"
    )
    issued_date: date = Field(..., description="Certificate issue date (YYYY-MM-DD)")
    template_id: UUID = Field(..., description="ID of template to render certificates with")
    recipients: List[RecipientIn] = Field(
        ...,
        min_length=1,
        max_length=10000,
        description="List of recipient entries (1 to 10000 recipients)",
    )
    idempotency_key: Optional[str] = Field(
        None, max_length=255, description="Optional client idempotency key to prevent duplicate jobs"
    )


class DerivedJobStatus(str, Enum):
    QUEUED = "queued"
    PROCESSING = "processing"
    COMPLETED = "completed"
    COMPLETED_WITH_ERRORS = "completed_with_errors"
    FAILED = "failed"


class JobProgress(BaseModel):
    """Dynamically computed job progress metrics based on grouped certificate status counts."""

    total: int = Field(..., ge=0)
    succeeded: int = Field(..., ge=0)
    failed: int = Field(..., ge=0)
    pending: int = Field(..., ge=0)
    percent: float = Field(..., ge=0.0, le=100.0)
    status: DerivedJobStatus


class CertificateOut(BaseModel):
    """Output schema for an individual generated certificate."""

    id: UUID
    job_id: UUID
    recipient_name: str
    recipient_email: str
    status: str
    error_message: Optional[str] = None
    file_path: Optional[str] = None
    created_at: datetime
    updated_at: datetime

    model_config = ConfigDict(from_attributes=True)


class TemplateOut(BaseModel):
    """Output schema for a certificate template."""

    id: UUID
    name: str
    kind: str
    key: Optional[str] = None
    background_path: Optional[str] = None
    layout: TemplateLayout
    is_deleted: bool
    created_at: datetime

    model_config = ConfigDict(from_attributes=True)
