from datetime import datetime, date, timezone
import enum
import uuid
from typing import Optional, Dict, Any

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
    layout: Mapped[Dict[str, Any]] = mapped_column(
        JSON, nullable=False
    )  # e.g. {"name_y": 45.0, "course_y": 60.0, "date_y": 75.0}
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
    title: Mapped[str] = mapped_column(String(255), nullable=False)
    organization_name: Mapped[Optional[str]] = mapped_column(
        String(255), nullable=True
    )
    issued_date: Mapped[date] = mapped_column(Date, nullable=False)
    template_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("templates.id"), nullable=False
    )
    layout_snapshot: Mapped[Dict[str, Any]] = mapped_column(
        JSON, nullable=False
    )  # Frozen copy of template layout at job creation time
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
    recipient_email: Mapped[str] = mapped_column(String(255), nullable=False)
    status: Mapped[CertificateStatus] = mapped_column(
        Enum(CertificateStatus, name="cert_status_enum", values_callable=lambda obj: [e.value for e in obj]),
        default=CertificateStatus.PENDING,
        index=True,
        nullable=False,
    )
    error_message: Mapped[Optional[str]] = mapped_column(
        Text, nullable=True
    )
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
