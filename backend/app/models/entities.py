from sqlalchemy import (
    Boolean, CheckConstraint, DateTime, ForeignKey, Index,
    Integer, JSON, Numeric, String, Text, UniqueConstraint
)
from sqlalchemy.orm import Mapped, mapped_column
from backend.app.database import Base


class User(Base):
    __tablename__ = "users"

    user_id: Mapped[str] = mapped_column(String(32), primary_key=True)
    username: Mapped[str] = mapped_column(String(100), unique=True, nullable=False)
    email: Mapped[str] = mapped_column(String(255), unique=True, nullable=False)
    password_hash: Mapped[str | None] = mapped_column(String(255), nullable=True)
    role: Mapped[str] = mapped_column(String(60), nullable=False, index=True)
    is_active: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)
    created_at: Mapped[object] = mapped_column(DateTime(timezone=True), nullable=False)


class Learner(Base):
    __tablename__ = "learners"

    learner_id: Mapped[str] = mapped_column(String(32), primary_key=True)
    user_id: Mapped[str] = mapped_column(
        ForeignKey("users.user_id"), unique=True, nullable=False
    )
    full_name: Mapped[str] = mapped_column(String(150), nullable=False)
    department: Mapped[str] = mapped_column(String(100), nullable=False)
    enrollment_year: Mapped[int] = mapped_column(Integer, nullable=False)


class Instructor(Base):
    __tablename__ = "instructors"

    instructor_id: Mapped[str] = mapped_column(String(32), primary_key=True)
    user_id: Mapped[str] = mapped_column(
        ForeignKey("users.user_id"), unique=True, nullable=False
    )
    full_name: Mapped[str] = mapped_column(String(150), nullable=False)
    department: Mapped[str] = mapped_column(String(100), nullable=False)


class Reviewer(Base):
    __tablename__ = "reviewers"

    reviewer_id: Mapped[str] = mapped_column(String(32), primary_key=True)
    user_id: Mapped[str] = mapped_column(
        ForeignKey("users.user_id"), unique=True, nullable=False
    )
    full_name: Mapped[str] = mapped_column(String(150), nullable=False)
    department: Mapped[str] = mapped_column(String(100), nullable=False)
    specialization: Mapped[str] = mapped_column(String(150), nullable=False)


class Assessment(Base):
    __tablename__ = "assessments"

    assessment_id: Mapped[str] = mapped_column(String(32), primary_key=True)
    title: Mapped[str] = mapped_column(String(255), nullable=False)
    course_code: Mapped[str] = mapped_column(String(40), nullable=False)
    created_by_instructor_id: Mapped[str] = mapped_column(
        ForeignKey("instructors.instructor_id"), nullable=False
    )
    max_score: Mapped[object] = mapped_column(Numeric(8, 2), nullable=False)
    due_date: Mapped[object] = mapped_column(DateTime(timezone=True), nullable=False)


class Submission(Base):
    __tablename__ = "submissions"

    submission_id: Mapped[str] = mapped_column(String(32), primary_key=True)
    learner_id: Mapped[str] = mapped_column(
        ForeignKey("learners.learner_id"), nullable=False, index=True
    )
    assessment_id: Mapped[str] = mapped_column(
        ForeignKey("assessments.assessment_id"), nullable=False, index=True
    )
    submitted_at: Mapped[object] = mapped_column(DateTime(timezone=True), nullable=False)
    content_fingerprint: Mapped[str] = mapped_column(String(64), nullable=False)
    status: Mapped[str] = mapped_column(String(40), nullable=False)


class SimilarityReport(Base):
    __tablename__ = "similarity_reports"
    __table_args__ = (
        CheckConstraint(
            "similarity_score >= 0 AND similarity_score <= 100",
            name="ck_similarity_report_score_range",
        ),
        CheckConstraint(
            "target_submission_id <> matched_submission_id",
            name="ck_similarity_report_distinct_submissions",
        ),
        Index("ix_similarity_target", "target_submission_id"),
        Index("ix_similarity_matched", "matched_submission_id"),
    )

    report_id: Mapped[str] = mapped_column(String(32), primary_key=True)
    target_submission_id: Mapped[str] = mapped_column(
        ForeignKey("submissions.submission_id"), nullable=False
    )
    matched_submission_id: Mapped[str] = mapped_column(
        ForeignKey("submissions.submission_id"), nullable=False
    )
    similarity_score: Mapped[object] = mapped_column(Numeric(5, 2), nullable=False)
    generated_at: Mapped[object] = mapped_column(DateTime(timezone=True), nullable=False)
    algorithm_version: Mapped[str] = mapped_column(String(50), nullable=False)


class SimilarityFlag(Base):
    __tablename__ = "similarity_flags"
    __table_args__ = (
        CheckConstraint(
            "similarity_score >= 15 AND similarity_score <= 100",
            name="ck_similarity_flag_score_range",
        ),
        CheckConstraint(
            "severity IN ('MEDIUM', 'HIGH')",
            name="ck_similarity_flag_severity",
        ),
        Index("ix_flag_severity_created", "severity", "created_at"),
    )

    flag_id: Mapped[str] = mapped_column(String(32), primary_key=True)
    report_id: Mapped[str] = mapped_column(
        ForeignKey("similarity_reports.report_id"), unique=True, nullable=False
    )
    submission_id: Mapped[str] = mapped_column(
        ForeignKey("submissions.submission_id"), nullable=False, index=True
    )
    similarity_score: Mapped[object] = mapped_column(Numeric(5, 2), nullable=False)
    severity: Mapped[str] = mapped_column(String(20), nullable=False)
    flag_reason: Mapped[str] = mapped_column(Text, nullable=False)
    created_at: Mapped[object] = mapped_column(DateTime(timezone=True), nullable=False)


class Case(Base):
    __tablename__ = "cases"
    __table_args__ = (
        CheckConstraint(
            "case_status IN ('UNDER_INVESTIGATION', 'DECIDED', 'APPEALED', 'CLOSED')",
            name="ck_case_status",
        ),
        Index("ix_case_status_updated", "case_status", "updated_at"),
    )

    case_id: Mapped[str] = mapped_column(String(32), primary_key=True)
    flag_id: Mapped[str] = mapped_column(
        ForeignKey("similarity_flags.flag_id"), unique=True, nullable=False
    )
    submission_id: Mapped[str] = mapped_column(
        ForeignKey("submissions.submission_id"), nullable=False, index=True
    )
    case_status: Mapped[str] = mapped_column(String(40), nullable=False)
    created_at: Mapped[object] = mapped_column(DateTime(timezone=True), nullable=False)
    updated_at: Mapped[object] = mapped_column(DateTime(timezone=True), nullable=False)


class ReviewerAssignment(Base):
    __tablename__ = "reviewer_assignments"
    __table_args__ = (
        Index("ix_assignment_case_active", "case_id", "is_active"),
    )

    assignment_id: Mapped[str] = mapped_column(String(32), primary_key=True)
    case_id: Mapped[str] = mapped_column(ForeignKey("cases.case_id"), nullable=False)
    reviewer_id: Mapped[str] = mapped_column(
        ForeignKey("reviewers.reviewer_id"), nullable=False
    )
    assigned_by_user_id: Mapped[str] = mapped_column(
        ForeignKey("users.user_id"), nullable=False
    )
    assignment_role: Mapped[str] = mapped_column(String(50), nullable=False)
    assigned_at: Mapped[object] = mapped_column(DateTime(timezone=True), nullable=False)
    is_active: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)


class Evidence(Base):
    __tablename__ = "evidence"
    __table_args__ = (
        CheckConstraint("version >= 1", name="ck_evidence_version_positive"),
        Index("ix_evidence_case_added", "case_id", "added_at"),
    )

    evidence_id: Mapped[str] = mapped_column(String(32), primary_key=True)
    case_id: Mapped[str] = mapped_column(ForeignKey("cases.case_id"), nullable=False)
    evidence_type: Mapped[str] = mapped_column(String(80), nullable=False)
    content_summary: Mapped[str] = mapped_column(Text, nullable=False)
    metadata_checksum: Mapped[str] = mapped_column(String(64), nullable=False)
    added_by_user_id: Mapped[str] = mapped_column(
        ForeignKey("users.user_id"), nullable=False
    )
    added_at: Mapped[object] = mapped_column(DateTime(timezone=True), nullable=False)
    version: Mapped[int] = mapped_column(Integer, nullable=False)


class Decision(Base):
    __tablename__ = "decisions"
    __table_args__ = (
        UniqueConstraint("case_id", name="uq_decision_case"),
        CheckConstraint(
            "finding IN ('ACADEMIC_MISCONDUCT_FOUND', "
            "'NO_MISCONDUCT_FOUND', 'INSUFFICIENT_EVIDENCE')",
            name="ck_decision_finding",
        ),
    )

    decision_id: Mapped[str] = mapped_column(String(32), primary_key=True)
    case_id: Mapped[str] = mapped_column(ForeignKey("cases.case_id"), nullable=False)
    decision_maker_id: Mapped[str] = mapped_column(
        ForeignKey("reviewers.reviewer_id"), nullable=False
    )
    finding: Mapped[str] = mapped_column(String(50), nullable=False)
    sanction_recommended: Mapped[str] = mapped_column(String(80), nullable=False)
    rationale_text: Mapped[str] = mapped_column(Text, nullable=False)
    decided_at: Mapped[object] = mapped_column(DateTime(timezone=True), nullable=False)


class Appeal(Base):
    __tablename__ = "appeals"
    __table_args__ = (
        UniqueConstraint("case_id", name="uq_appeal_case"),
        UniqueConstraint("decision_id", name="uq_appeal_decision"),
        CheckConstraint(
            "appeal_status IN ('UNDER_INDEPENDENT_REVIEW', 'CLOSED')",
            name="ck_appeal_status",
        ),
        CheckConstraint(
            "review_outcome IS NULL OR review_outcome IN "
            "('UPHELD', 'OVERTURNED', 'REMANDED')",
            name="ck_appeal_outcome",
        ),
    )

    appeal_id: Mapped[str] = mapped_column(String(32), primary_key=True)
    case_id: Mapped[str] = mapped_column(ForeignKey("cases.case_id"), nullable=False)
    decision_id: Mapped[str] = mapped_column(
        ForeignKey("decisions.decision_id"), nullable=False
    )
    independent_reviewer_id: Mapped[str] = mapped_column(
        ForeignKey("reviewers.reviewer_id"), nullable=False
    )
    appeal_reason: Mapped[str] = mapped_column(Text, nullable=False)
    appeal_status: Mapped[str] = mapped_column(String(40), nullable=False)
    submitted_at: Mapped[object] = mapped_column(DateTime(timezone=True), nullable=False)
    review_completed_at: Mapped[object | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )
    review_outcome: Mapped[str | None] = mapped_column(String(30), nullable=True)


class AuditEvent(Base):
    __tablename__ = "audit_events"
    __table_args__ = (
        Index("ix_audit_entity", "entity_type", "entity_id"),
        Index("ix_audit_timestamp", "timestamp"),
    )

    event_id: Mapped[str] = mapped_column(String(32), primary_key=True)
    actor_id: Mapped[str] = mapped_column(ForeignKey("users.user_id"), nullable=False)
    event_type: Mapped[str] = mapped_column(String(80), nullable=False)
    entity_type: Mapped[str] = mapped_column(String(50), nullable=False)
    entity_id: Mapped[str] = mapped_column(String(32), nullable=False)
    event_payload_json: Mapped[dict] = mapped_column(JSON, nullable=False)
    timestamp: Mapped[object] = mapped_column(DateTime(timezone=True), nullable=False)
