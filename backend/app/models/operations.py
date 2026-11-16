from datetime import datetime

from sqlalchemy import JSON, Boolean, Float, ForeignKey, Index, Integer, String, Text, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.core.time import utcnow
from app.db.base import Base, TimestampMixin
from app.db.types import UTCDateTime
from app.models.org import EntryPoint, Module


class Employee(Base, TimestampMixin):
    __tablename__ = "employees"
    __table_args__ = (UniqueConstraint("factory_id", "employee_code"),)
    id: Mapped[int] = mapped_column(primary_key=True)
    factory_id: Mapped[int] = mapped_column(ForeignKey("factories.id", ondelete="CASCADE"), index=True, nullable=False)
    module_id: Mapped[int | None] = mapped_column(ForeignKey("modules.id", ondelete="SET NULL"), index=True)
    department_id: Mapped[int | None] = mapped_column(ForeignKey("departments.id", ondelete="SET NULL"))
    employee_code: Mapped[str] = mapped_column(String(20), nullable=False)
    full_name: Mapped[str] = mapped_column(String(120), index=True, nullable=False)
    designation: Mapped[str] = mapped_column(String(80), default="", nullable=False)
    shift: Mapped[str] = mapped_column(String(4), default="A", nullable=False)
    beard_net_applicable: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    status: Mapped[str] = mapped_column(String(12), default="active", nullable=False)  # active | inactive
    photo_path: Mapped[str | None] = mapped_column(String(255))
    module: Mapped[Module | None] = relationship(lazy="joined")
    department = relationship("Department", lazy="joined")


class Camera(Base, TimestampMixin):
    __tablename__ = "cameras"
    id: Mapped[int] = mapped_column(primary_key=True)
    factory_id: Mapped[int] = mapped_column(ForeignKey("factories.id", ondelete="CASCADE"), index=True, nullable=False)
    entry_point_id: Mapped[int | None] = mapped_column(ForeignKey("entry_points.id", ondelete="SET NULL"), index=True)
    name: Mapped[str] = mapped_column(String(80), nullable=False)
    type: Mapped[str] = mapped_column(String(12), nullable=False)  # browser | usb | rtsp | onvif
    # usb: device index ("0"); rtsp/onvif: URL WITHOUT credentials; browser: empty
    source: Mapped[str] = mapped_column(String(300), default="", nullable=False)
    credentials_enc: Mapped[str | None] = mapped_column(Text)  # Fernet-encrypted JSON, never returned by the API
    is_active: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)
    status: Mapped[str] = mapped_column(String(12), default="unknown", nullable=False)  # unknown | online | offline
    last_seen_at: Mapped[datetime | None] = mapped_column(UTCDateTime)
    last_error: Mapped[str] = mapped_column(String(250), default="", nullable=False)
    resolution: Mapped[str] = mapped_column(String(20), default="", nullable=False)
    entry_point: Mapped[EntryPoint | None] = relationship(lazy="joined")


class DoorController(Base, TimestampMixin):
    __tablename__ = "door_controllers"
    id: Mapped[int] = mapped_column(primary_key=True)
    factory_id: Mapped[int] = mapped_column(ForeignKey("factories.id", ondelete="CASCADE"), index=True, nullable=False)
    entry_point_id: Mapped[int] = mapped_column(ForeignKey("entry_points.id", ondelete="CASCADE"), unique=True,
                                                nullable=False)
    name: Mapped[str] = mapped_column(String(80), nullable=False)
    adapter: Mapped[str] = mapped_column(String(20), default="simulation", nullable=False)  # simulation | http_relay
    config: Mapped[dict] = mapped_column(JSON, default=dict, nullable=False)  # non-secret adapter settings
    unlock_seconds: Mapped[int] = mapped_column(Integer, default=5, nullable=False)
    fail_mode: Mapped[str] = mapped_column(String(12), default="fail_secure", nullable=False)
    auto_open: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)
    state: Mapped[str] = mapped_column(String(10), default="locked", nullable=False)  # locked|unlocked|held|fault
    unlock_until: Mapped[datetime | None] = mapped_column(UTCDateTime)
    online: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)
    last_seen_at: Mapped[datetime | None] = mapped_column(UTCDateTime)
    # Real hardware is only driven after an explicit, recorded approval by an authorised user.
    hardware_approved_by: Mapped[int | None] = mapped_column(ForeignKey("users.id", ondelete="SET NULL"))
    hardware_approved_at: Mapped[datetime | None] = mapped_column(UTCDateTime)
    entry_point: Mapped[EntryPoint] = relationship(lazy="joined")


class EntryLog(Base):
    __tablename__ = "entry_logs"
    __table_args__ = (
        Index("ix_entry_logs_factory_time", "factory_id", "occurred_at"),
        Index("ix_entry_logs_module_time", "module_id", "occurred_at"),
        Index("ix_entry_logs_employee_time", "employee_id", "occurred_at"),
    )
    id: Mapped[int] = mapped_column(primary_key=True)
    factory_id: Mapped[int] = mapped_column(ForeignKey("factories.id", ondelete="CASCADE"), nullable=False)
    module_id: Mapped[int] = mapped_column(ForeignKey("modules.id", ondelete="CASCADE"), nullable=False)
    entry_point_id: Mapped[int | None] = mapped_column(ForeignKey("entry_points.id", ondelete="SET NULL"))
    camera_id: Mapped[int | None] = mapped_column(ForeignKey("cameras.id", ondelete="SET NULL"))
    employee_id: Mapped[int | None] = mapped_column(ForeignKey("employees.id", ondelete="SET NULL"))
    operator_id: Mapped[int | None] = mapped_column(ForeignKey("users.id", ondelete="SET NULL"))
    occurred_at: Mapped[datetime] = mapped_column(UTCDateTime, default=utcnow, nullable=False)
    passed: Mapped[bool] = mapped_column(Boolean, nullable=False)
    decision: Mapped[str] = mapped_column(String(10), nullable=False)  # granted | denied
    missing_items: Mapped[list] = mapped_column(JSON, default=list, nullable=False)
    shift: Mapped[str | None] = mapped_column(String(4))
    # live = real model on a real frame; simulation = simulated detector; sample = seeded demo data
    source: Mapped[str] = mapped_column(String(12), default="live", nullable=False)
    evidence_path: Mapped[str | None] = mapped_column(String(255))
    employee: Mapped[Employee | None] = relationship(lazy="joined")
    module: Mapped[Module] = relationship(lazy="joined")
    entry_point: Mapped[EntryPoint | None] = relationship(lazy="joined")
    camera: Mapped[Camera | None] = relationship(lazy="joined")
    detections: Mapped[list["DetectionRecord"]] = relationship(back_populates="entry_log",
                                                               cascade="all, delete-orphan")
    compliance: Mapped["ComplianceRecord | None"] = relationship(back_populates="entry_log", uselist=False,
                                                                 cascade="all, delete-orphan")
    violation: Mapped["Violation | None"] = relationship(back_populates="entry_log", uselist=False)


class DetectionRecord(Base):
    __tablename__ = "detection_records"
    id: Mapped[int] = mapped_column(primary_key=True)
    entry_log_id: Mapped[int] = mapped_column(ForeignKey("entry_logs.id", ondelete="CASCADE"), index=True,
                                              nullable=False)
    item: Mapped[str] = mapped_column(String(20), nullable=False)
    detected: Mapped[bool] = mapped_column(Boolean, nullable=False)
    confidence: Mapped[float] = mapped_column(Float, nullable=False)
    bbox: Mapped[list | None] = mapped_column(JSON)  # [x, y, w, h] normalised 0..1
    model_name: Mapped[str] = mapped_column(String(80), default="", nullable=False)
    model_version: Mapped[str] = mapped_column(String(40), default="", nullable=False)
    simulated: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    entry_log: Mapped[EntryLog] = relationship(back_populates="detections")


class ComplianceRecord(Base):
    __tablename__ = "compliance_records"
    id: Mapped[int] = mapped_column(primary_key=True)
    entry_log_id: Mapped[int] = mapped_column(ForeignKey("entry_logs.id", ondelete="CASCADE"), unique=True,
                                              nullable=False)
    required_items: Mapped[list] = mapped_column(JSON, default=list, nullable=False)
    missing_items: Mapped[list] = mapped_column(JSON, default=list, nullable=False)
    item_results: Mapped[list] = mapped_column(JSON, default=list, nullable=False)
    passed: Mapped[bool] = mapped_column(Boolean, nullable=False)
    threshold: Mapped[float] = mapped_column(Float, nullable=False)
    engine_version: Mapped[str] = mapped_column(String(20), default="1.0", nullable=False)
    entry_log: Mapped[EntryLog] = relationship(back_populates="compliance")


class AccessEvent(Base):
    __tablename__ = "access_events"
    __table_args__ = (Index("ix_access_events_door_time", "door_id", "occurred_at"),)
    id: Mapped[int] = mapped_column(primary_key=True)
    factory_id: Mapped[int] = mapped_column(ForeignKey("factories.id", ondelete="CASCADE"), index=True, nullable=False)
    door_id: Mapped[int] = mapped_column(ForeignKey("door_controllers.id", ondelete="CASCADE"), nullable=False)
    entry_log_id: Mapped[int | None] = mapped_column(ForeignKey("entry_logs.id", ondelete="SET NULL"))
    actor_user_id: Mapped[int | None] = mapped_column(ForeignKey("users.id", ondelete="SET NULL"))
    type: Mapped[str] = mapped_column(String(24), nullable=False)
    reason: Mapped[str] = mapped_column(String(300), default="", nullable=False)
    simulated: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)
    occurred_at: Mapped[datetime] = mapped_column(UTCDateTime, default=utcnow, nullable=False)
    door: Mapped[DoorController] = relationship(lazy="joined")
    actor = relationship("User", lazy="joined")


class Violation(Base):
    __tablename__ = "violations"
    __table_args__ = (Index("ix_violations_factory_created", "factory_id", "created_at"),
                      Index("ix_violations_employee_created", "employee_id", "created_at"))
    id: Mapped[int] = mapped_column(primary_key=True)
    factory_id: Mapped[int] = mapped_column(ForeignKey("factories.id", ondelete="CASCADE"), nullable=False)
    module_id: Mapped[int] = mapped_column(ForeignKey("modules.id", ondelete="CASCADE"), index=True, nullable=False)
    entry_log_id: Mapped[int] = mapped_column(ForeignKey("entry_logs.id", ondelete="CASCADE"), unique=True,
                                              nullable=False)
    employee_id: Mapped[int | None] = mapped_column(ForeignKey("employees.id", ondelete="SET NULL"))
    missing_items: Mapped[list] = mapped_column(JSON, default=list, nullable=False)
    severity: Mapped[str] = mapped_column(String(10), default="medium", nullable=False)  # medium|high|critical
    status: Mapped[str] = mapped_column(String(14), default="open", index=True, nullable=False)
    is_repeat: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    created_at: Mapped[datetime] = mapped_column(UTCDateTime, default=utcnow, nullable=False)
    resolved_at: Mapped[datetime | None] = mapped_column(UTCDateTime)
    resolved_by: Mapped[int | None] = mapped_column(ForeignKey("users.id", ondelete="SET NULL"))
    entry_log: Mapped[EntryLog] = relationship(back_populates="violation", lazy="joined")
    employee: Mapped[Employee | None] = relationship(lazy="joined")
    notes: Mapped[list["ViolationNote"]] = relationship(cascade="all, delete-orphan", order_by="ViolationNote.id")


class ViolationNote(Base):
    __tablename__ = "violation_notes"
    id: Mapped[int] = mapped_column(primary_key=True)
    violation_id: Mapped[int] = mapped_column(ForeignKey("violations.id", ondelete="CASCADE"), index=True,
                                              nullable=False)
    user_id: Mapped[int | None] = mapped_column(ForeignKey("users.id", ondelete="SET NULL"))
    author: Mapped[str] = mapped_column(String(120), default="", nullable=False)
    text: Mapped[str] = mapped_column(String(500), nullable=False)
    created_at: Mapped[datetime] = mapped_column(UTCDateTime, default=utcnow, nullable=False)


class Alert(Base):
    __tablename__ = "alerts"
    __table_args__ = (Index("ix_alerts_factory_created", "factory_id", "created_at"),)
    id: Mapped[int] = mapped_column(primary_key=True)
    factory_id: Mapped[int] = mapped_column(ForeignKey("factories.id", ondelete="CASCADE"), nullable=False)
    type: Mapped[str] = mapped_column(String(24), nullable=False)
    severity: Mapped[str] = mapped_column(String(10), default="medium", nullable=False)
    title: Mapped[str] = mapped_column(String(200), nullable=False)
    detail: Mapped[str] = mapped_column(String(400), default="", nullable=False)
    ref_type: Mapped[str | None] = mapped_column(String(20))
    ref_id: Mapped[int | None] = mapped_column(Integer)
    created_at: Mapped[datetime] = mapped_column(UTCDateTime, default=utcnow, nullable=False)
    read_at: Mapped[datetime | None] = mapped_column(UTCDateTime)
    acknowledged_at: Mapped[datetime | None] = mapped_column(UTCDateTime)
    acknowledged_by: Mapped[int | None] = mapped_column(ForeignKey("users.id", ondelete="SET NULL"))
