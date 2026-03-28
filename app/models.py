"""SQLAlchemy models for Scanner Frontend."""

import uuid
from datetime import datetime

from sqlalchemy import String, Integer, Float, Text, DateTime, ForeignKey, Index
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship
from sqlalchemy.sql import func

from app.database import Base


class Scan(Base):
    """A security scan run."""

    __tablename__ = "scans"
    __table_args__ = (
        Index("idx_scans_status", "status"),
        Index("idx_scans_created", "created_at"),
    )

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, default=uuid.uuid4
    )
    status: Mapped[str] = mapped_column(String(20), nullable=False, default="pending")
    scan_type: Mapped[str] = mapped_column(String(20), nullable=False, default="gitleaks")
    github_users: Mapped[str | None] = mapped_column(Text, nullable=True)
    gitlab_users: Mapped[str | None] = mapped_column(Text, nullable=True)
    repo_urls: Mapped[str | None] = mapped_column(Text, nullable=True)
    repos_scanned: Mapped[int | None] = mapped_column(Integer, nullable=True)
    total_findings: Mapped[int | None] = mapped_column(Integer, nullable=True)
    critical_count: Mapped[int] = mapped_column(Integer, default=0)
    high_count: Mapped[int] = mapped_column(Integer, default=0)
    medium_count: Mapped[int] = mapped_column(Integer, default=0)
    low_count: Mapped[int] = mapped_column(Integer, default=0)
    duration_seconds: Mapped[float | None] = mapped_column(Float, nullable=True)
    error_message: Mapped[str | None] = mapped_column(Text, nullable=True)
    started_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )
    completed_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )

    findings: Mapped[list["Finding"]] = relationship(
        back_populates="scan", cascade="all, delete-orphan"
    )


class Finding(Base):
    """A single finding from a scan."""

    __tablename__ = "findings"
    __table_args__ = (
        Index("idx_findings_scan_id", "scan_id"),
        Index("idx_findings_severity", "severity"),
    )

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, default=uuid.uuid4
    )
    scan_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("scans.id", ondelete="CASCADE"), nullable=False
    )
    repo: Mapped[str] = mapped_column(Text, nullable=False)
    tool: Mapped[str] = mapped_column(String(20), nullable=False)
    rule_id: Mapped[str | None] = mapped_column(String(100), nullable=True)
    severity: Mapped[str] = mapped_column(String(20), nullable=False)
    category: Mapped[str | None] = mapped_column(String(50), nullable=True)
    file: Mapped[str | None] = mapped_column(Text, nullable=True)
    line: Mapped[int | None] = mapped_column(Integer, nullable=True)
    commit_hash: Mapped[str | None] = mapped_column(String(40), nullable=True)
    snippet: Mapped[str | None] = mapped_column(Text, nullable=True)
    description: Mapped[str | None] = mapped_column(Text, nullable=True)
    recommendation: Mapped[str | None] = mapped_column(Text, nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )

    scan: Mapped["Scan"] = relationship(back_populates="findings")
