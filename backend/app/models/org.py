from sqlalchemy import JSON, Boolean, Float, ForeignKey, Integer, String, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base, TimestampMixin

PPE_ITEMS = ("uniform", "hair_cap", "face_mask", "beard_net", "safety_shoes")
PPE_LABELS = {"uniform": "Uniform", "hair_cap": "Hair Cap", "face_mask": "Face Mask",
              "beard_net": "Beard Net", "safety_shoes": "Safety Shoes"}
DEFAULT_SHIFTS = [{"code": "A", "start": "06:00", "end": "14:00"}, {"code": "B", "start": "14:00", "end": "22:00"},
                  {"code": "C", "start": "22:00", "end": "06:00"}]


class Factory(Base, TimestampMixin):
    __tablename__ = "factories"
    id: Mapped[int] = mapped_column(primary_key=True)
    name: Mapped[str] = mapped_column(String(120), nullable=False)
    code: Mapped[str] = mapped_column(String(20), unique=True, nullable=False)
    address: Mapped[str] = mapped_column(String(250), default="", nullable=False)
    timezone: Mapped[str] = mapped_column(String(64), default="UTC", nullable=False)
    shifts: Mapped[list] = mapped_column(JSON, default=lambda: list(DEFAULT_SHIFTS), nullable=False)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)
    modules: Mapped[list["Module"]] = relationship(back_populates="factory", order_by="Module.id")
    settings: Mapped["FactorySetting | None"] = relationship(back_populates="factory", uselist=False)


class FactorySetting(Base, TimestampMixin):
    __tablename__ = "factory_settings"
    id: Mapped[int] = mapped_column(primary_key=True)
    factory_id: Mapped[int] = mapped_column(ForeignKey("factories.id", ondelete="CASCADE"), unique=True, nullable=False)
    confidence_threshold: Mapped[float] = mapped_column(Float, default=0.6, nullable=False)
    evidence_policy: Mapped[str] = mapped_column(String(20), default="violations", nullable=False)  # violations | all
    retention_days: Mapped[int] = mapped_column(Integer, default=365, nullable=False)
    repeat_threshold: Mapped[int] = mapped_column(Integer, default=3, nullable=False)
    repeat_window_days: Mapped[int] = mapped_column(Integer, default=7, nullable=False)
    notifications: Mapped[dict] = mapped_column(JSON, default=dict, nullable=False)
    factory: Mapped[Factory] = relationship(back_populates="settings")


class Module(Base, TimestampMixin):
    __tablename__ = "modules"
    __table_args__ = (UniqueConstraint("factory_id", "code"),)
    id: Mapped[int] = mapped_column(primary_key=True)
    factory_id: Mapped[int] = mapped_column(ForeignKey("factories.id", ondelete="CASCADE"), index=True, nullable=False)
    name: Mapped[str] = mapped_column(String(80), nullable=False)
    code: Mapped[str] = mapped_column(String(10), nullable=False)
    description: Mapped[str] = mapped_column(String(200), default="", nullable=False)
    color: Mapped[str] = mapped_column(String(9), default="#2B68A8", nullable=False)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)
    factory: Mapped[Factory] = relationship(back_populates="modules")
    entry_points: Mapped[list["EntryPoint"]] = relationship(back_populates="module", order_by="EntryPoint.id",
                                                           cascade="all, delete-orphan")
    ppe_requirements: Mapped[list["PPERequirement"]] = relationship(back_populates="module",
                                                                   cascade="all, delete-orphan", lazy="selectin")


class Department(Base):
    __tablename__ = "departments"
    __table_args__ = (UniqueConstraint("factory_id", "name"),)
    id: Mapped[int] = mapped_column(primary_key=True)
    factory_id: Mapped[int] = mapped_column(ForeignKey("factories.id", ondelete="CASCADE"), index=True, nullable=False)
    name: Mapped[str] = mapped_column(String(80), nullable=False)


class EntryPoint(Base, TimestampMixin):
    __tablename__ = "entry_points"
    __table_args__ = (UniqueConstraint("module_id", "name"),)
    id: Mapped[int] = mapped_column(primary_key=True)
    module_id: Mapped[int] = mapped_column(ForeignKey("modules.id", ondelete="CASCADE"), index=True, nullable=False)
    name: Mapped[str] = mapped_column(String(80), nullable=False)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)
    module: Mapped[Module] = relationship(back_populates="entry_points")


class PPERequirement(Base):
    __tablename__ = "ppe_requirements"
    __table_args__ = (UniqueConstraint("module_id", "item"),)
    id: Mapped[int] = mapped_column(primary_key=True)
    module_id: Mapped[int] = mapped_column(ForeignKey("modules.id", ondelete="CASCADE"), index=True, nullable=False)
    item: Mapped[str] = mapped_column(String(20), nullable=False)
    required: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)
    min_confidence: Mapped[float | None] = mapped_column(Float)  # NULL = factory default
    module: Mapped[Module] = relationship(back_populates="ppe_requirements")
