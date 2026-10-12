"""
Pydantic Schemas for Request & Response Validation.

================================================================================
TWO-LEVEL VALIDATION DESIGN RATIONALE:
================================================================================
1. Level 1 Validation (HTTP Layer / Pydantic):
   - Evaluates structural integrity of API requests (JSON schema, recipient bounds
     1..10000, valid UUIDs, allowed output_format: 'pdf', 'png', 'jpg').
   - Any structural deviation raises a ValidationError returning HTTP 422.

2. Level 2 Validation (Service / Worker Layer):
   - Evaluates individual recipient data quality against template requirements.
   - Recipient email is now optional. If provided, it must be syntactically valid.
   - Recipient name remains mandatory (non-empty, <= 200 chars).
   - If an individual recipient row fails validation, the overall job request is STILL ACCEPTED (HTTP 202).
   - The flawed recipient is recorded in the database with status='failed' and a specific error_message.
   - Valid certificates in the same batch continue to generate and succeed without interruption.
================================================================================
"""

from datetime import datetime, date
from enum import Enum
from typing import List, Optional, Dict, Any, Literal
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field


class RecipientIn(BaseModel):
    """
    Recipient input payload.
    - name: Mandatory, non-empty, max 200 chars.
    - email: Optional. Validated if provided, but accepted if empty/None.
    """

    name: str = Field(..., description="Recipient full name")
    email: Optional[str] = Field(None, description="Optional recipient email address")


class JobCreate(BaseModel):
    """Payload for creating a bulk certificate generation job."""

    template_id: UUID = Field(..., description="Template UUID to render certificates with")
    title: Optional[str] = Field(None, max_length=255, description="Course / Certificate title")
    organization_name: Optional[str] = Field(None, max_length=255, description="Issuing organization name")
    issued_date: Optional[date] = Field(None, description="Issue date (YYYY-MM-DD)")
    output_format: Literal["pdf", "png", "jpg"] = Field(
        "pdf", description="Output format for generated certificates"
    )
    recipients: List[RecipientIn] = Field(
        ...,
        min_length=1,
        max_length=10000,
        description="List of recipients (1 to 10000 entries)",
    )
    idempotency_key: Optional[str] = Field(
        None, max_length=255, description="Optional idempotency key to prevent duplicate jobs"
    )


class DerivedJobStatus(str, Enum):
    QUEUED = "queued"
    PROCESSING = "processing"
    COMPLETED = "completed"
    COMPLETED_WITH_ERRORS = "completed_with_errors"
    FAILED = "failed"


class FailedRecipientOut(BaseModel):
    """Details of an individual recipient that failed validation or generation."""

    name: str = Field(..., description="Recipient name")
    email: Optional[str] = Field(None, description="Recipient email (if provided)")
    error_message: Optional[str] = Field(None, description="Reason for failure")


class JobProgress(BaseModel):
    """Dynamically computed job progress metrics from certificate row status counts."""

    total: int = Field(..., ge=0)
    succeeded: int = Field(..., ge=0)
    failed: int = Field(..., ge=0)
    pending: int = Field(..., ge=0)
    percent: float = Field(..., ge=0.0, le=100.0)
    status: DerivedJobStatus
    failed_recipients: List[FailedRecipientOut] = Field(
        default_factory=list,
        description="List of failed recipients with error details",
    )


class CertificateOut(BaseModel):
    """Output schema for an individual recipient certificate."""

    id: UUID
    job_id: UUID
    recipient_name: str
    recipient_email: Optional[str] = None
    file_name: str
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
    layout: Dict[str, Any]
    required_fields: List[str]
    is_deleted: bool
    created_at: datetime

    model_config = ConfigDict(from_attributes=True)
