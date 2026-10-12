from datetime import datetime, date, timezone
import enum
import uuid
from typing import Optional, Dict, Any, List

from sqlalchemy import (
    String,
    Boolean,
    Date,
    DateTime,
    Enum,
    ForeignKey,
    JSON,
    Text,
)
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db import Base


class CertificateStatus(str, enum.Enum):
    PENDING = "pending"
    PROCESSING = "processing"
    SUCCEEDED = "succeeded"
    FAILED = "failed"


class Template(Base):
    __tablename__ = "templates"

    id: Mapped[uuid.UUID] = mapped_column(
        primary_key=True, default=uuid.uuid4
    )
    name: Mapped[str] = mapped_column(String(255), nullable=False)
    kind: Mapped[str] = mapped_column(
        String(50), nullable=False, default="builtin"
    )  # "builtin" or "custom"
    key: Mapped[Optional[str]] = mapped_column(
        String(50), nullable=True, unique=True
    )  # e.g. classic, modern, minimal, elegant, bold
    background_path: Mapped[Optional[str]] = mapped_column(
        String(512), nullable=True
    )
    # Layout configuration (e.g. name_x, name_y, font, font_size_pct, color, max_width_pct)
    layout: Mapped[Dict[str, Any]] = mapped_column(
        JSON, nullable=False
    )
    # List of field names required by this template: ["name", "title", "issued_date"] or ["name"]
    required_fields: Mapped[List[str]] = mapped_column(
        JSON, nullable=False, default=lambda: ["name"]
    )
    is_deleted: Mapped[bool] = mapped_column(
        Boolean, default=False, nullable=False
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=lambda: datetime.now(timezone.utc),
        nullable=False,
    )

    jobs: Mapped[list["Job"]] = relationship(
        "Job", back_populates="template"
    )


class Job(Base):
    __tablename__ = "jobs"

    id: Mapped[uuid.UUID] = mapped_column(
        primary_key=True, default=uuid.uuid4
    )
    title: Mapped[Optional[str]] = mapped_column(String(255), nullable=True)
    organization_name: Mapped[Optional[str]] = mapped_column(
        String(255), nullable=True
    )
    issued_date: Mapped[Optional[date]] = mapped_column(Date, nullable=True)
    template_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("templates.id"), nullable=False
    )
    # Output file format: "pdf", "png", "jpg"
    output_format: Mapped[str] = mapped_column(
        String(10), default="pdf", nullable=False
    )
    # Frozen snapshot of template layout, background path, and required fields at job creation
    layout_snapshot: Mapped[Dict[str, Any]] = mapped_column(
        JSON, nullable=False
    )
    idempotency_key: Mapped[Optional[str]] = mapped_column(
        String(255), nullable=True, unique=True, index=True
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=lambda: datetime.now(timezone.utc),
        nullable=False,
    )
    finished_at: Mapped[Optional[datetime]] = mapped_column(
        DateTime(timezone=True), nullable=True
    )

    template: Mapped["Template"] = relationship(
        "Template", back_populates="jobs"
    )
    certificates: Mapped[list["Certificate"]] = relationship(
        "Certificate", back_populates="job", cascade="all, delete-orphan"
    )


class Certificate(Base):
    __tablename__ = "certificates"

    id: Mapped[uuid.UUID] = mapped_column(
        primary_key=True, default=uuid.uuid4
    )
    job_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("jobs.id"), index=True, nullable=False
    )
    recipient_name: Mapped[str] = mapped_column(String(255), nullable=False)
    recipient_email: Mapped[Optional[str]] = mapped_column(String(255), nullable=True)
    # Sanitized friendly file name for ZIP entry and download header (e.g. "Jane_Doe.pdf")
    file_name: Mapped[str] = mapped_column(String(255), nullable=False)
    status: Mapped[CertificateStatus] = mapped_column(
        Enum(CertificateStatus, name="cert_status_enum", values_callable=lambda obj: [e.value for e in obj]),
        default=CertificateStatus.PENDING,
        index=True,
        nullable=False,
    )
    error_message: Mapped[Optional[str]] = mapped_column(
        Text, nullable=True
    )
    # Storage relative path on disk: "storage/{job_id}/{certificate_id}.{ext}"
    file_path: Mapped[Optional[str]] = mapped_column(
        String(512), nullable=True
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=lambda: datetime.now(timezone.utc),
        nullable=False,
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=lambda: datetime.now(timezone.utc),
        onupdate=lambda: datetime.now(timezone.utc),
        nullable=False,
    )

    job: Mapped["Job"] = relationship("Job", back_populates="certificates")
