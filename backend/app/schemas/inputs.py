"""Request bodies (Pydantic v2). All input is validated and length-limited here."""
import re
from typing import Literal

from pydantic import BaseModel, ConfigDict, EmailStr, Field, field_validator

PPEItem = Literal["uniform", "hair_cap", "face_mask", "beard_net", "safety_shoes"]
_NAME = re.compile(r"^[\w .,'&()/\-–—]+$", re.UNICODE)


class Strict(BaseModel):
    model_config = ConfigDict(extra="forbid", str_strip_whitespace=True)


def _name(v: str) -> str:
    if not _NAME.match(v):
        raise ValueError("contains characters that are not allowed")
    return v


class LoginIn(Strict):
    email: EmailStr
    password: str = Field(min_length=1, max_length=128)
    remember: bool = False


class ForgotIn(Strict):
    email: EmailStr


class ResetIn(Strict):
    token: str = Field(min_length=20, max_length=200)
    new_password: str = Field(min_length=1, max_length=128)


class ChangePasswordIn(Strict):
    current_password: str = Field(min_length=1, max_length=128)
    new_password: str = Field(min_length=1, max_length=128)


class ProfileIn(Strict):
    full_name: str = Field(min_length=2, max_length=120)
    _v = field_validator("full_name")(_name)


class UserCreate(Strict):
    email: EmailStr
    full_name: str = Field(min_length=2, max_length=120)
    password: str = Field(min_length=1, max_length=128)
    role_ids: list[int] = Field(min_length=1, max_length=5)
    factory_id: int | None = None
    _v = field_validator("full_name")(_name)


class UserUpdate(Strict):
    full_name: str | None = Field(default=None, min_length=2, max_length=120)
    role_ids: list[int] | None = Field(default=None, min_length=1, max_length=5)
    factory_id: int | None = None
    is_active: bool | None = None
    set_factory: bool = False  # distinguishes "leave unchanged" from "set to all factories (null)"


class RoleIn(Strict):
    name: str = Field(min_length=3, max_length=60)
    description: str = Field(default="", max_length=250)
    permissions: list[str] = Field(default_factory=list, max_length=100)
    _v = field_validator("name")(_name)


class RolePermissionsIn(Strict):
    permissions: list[str] = Field(max_length=100)


class ShiftIn(Strict):
    code: str = Field(min_length=1, max_length=4)
    start: str = Field(pattern=r"^\d{2}:\d{2}$")
    end: str = Field(pattern=r"^\d{2}:\d{2}$")


class FactoryIn(Strict):
    name: str = Field(min_length=3, max_length=120)
    code: str = Field(min_length=2, max_length=20, pattern=r"^[A-Za-z0-9\-]+$")
    address: str = Field(default="", max_length=250)
    timezone: str = Field(default="UTC", max_length=64)
    shifts: list[ShiftIn] | None = Field(default=None, max_length=6)


class ModuleIn(Strict):
    name: str = Field(min_length=3, max_length=80)
    code: str = Field(min_length=2, max_length=10, pattern=r"^[A-Za-z0-9]+$")
    description: str = Field(default="", max_length=200)
    color: str = Field(default="#2B68A8", pattern=r"^#[0-9A-Fa-f]{6}$")
    is_active: bool = True
    required_ppe: list[PPEItem] | None = None
    first_entry_point: str | None = Field(default=None, min_length=3, max_length=80)
    _v = field_validator("name")(_name)


class ModuleUpdate(Strict):
    name: str | None = Field(default=None, min_length=3, max_length=80)
    description: str | None = Field(default=None, max_length=200)
    color: str | None = Field(default=None, pattern=r"^#[0-9A-Fa-f]{6}$")
    is_active: bool | None = None


class PPERuleIn(Strict):
    item: PPEItem
    required: bool
    min_confidence: float | None = Field(default=None, ge=0.3, le=0.99)


class PPEUpdate(Strict):
    rules: list[PPERuleIn] = Field(min_length=1, max_length=5)


class EntryPointIn(Strict):
    name: str = Field(min_length=3, max_length=80)
    create_door: bool = True
    _v = field_validator("name")(_name)


class DepartmentIn(Strict):
    name: str = Field(min_length=2, max_length=80)
    _v = field_validator("name")(_name)


class EmployeeIn(Strict):
    employee_code: str = Field(min_length=3, max_length=20, pattern=r"^[A-Za-z0-9\-]+$")
    full_name: str = Field(min_length=3, max_length=120)
    designation: str = Field(default="", max_length=80)
    department_id: int | None = None
    module_id: int | None = None
    shift: str = Field(default="A", max_length=4)
    beard_net_applicable: bool = False
    status: Literal["active", "inactive"] = "active"
    _v = field_validator("full_name")(_name)

    @field_validator("employee_code")
    @classmethod
    def _upper(cls, v: str) -> str:
        return v.upper()


class EmployeeUpdate(Strict):
    full_name: str | None = Field(default=None, min_length=3, max_length=120)
    designation: str | None = Field(default=None, max_length=80)
    department_id: int | None = None
    module_id: int | None = None
    shift: str | None = Field(default=None, max_length=4)
    beard_net_applicable: bool | None = None
    status: Literal["active", "inactive"] | None = None


class CameraIn(Strict):
    name: str = Field(min_length=3, max_length=80)
    type: Literal["browser", "usb", "rtsp", "onvif"]
    source: str = Field(default="", max_length=300)
    entry_point_id: int | None = None
    is_active: bool = True
    username: str | None = Field(default=None, max_length=80)
    password: str | None = Field(default=None, max_length=120)
    clear_credentials: bool = False
    _v = field_validator("name")(_name)


class DoorUpdate(Strict):
    unlock_seconds: int | None = Field(default=None, ge=1, le=30)
    fail_mode: Literal["fail_secure", "fail_safe"] | None = None
    auto_open: bool | None = None
    adapter: Literal["simulation", "http_relay"] | None = None
    config: dict | None = None


class DoorCommand(Strict):
    command: Literal["unlock", "lock", "hold", "release"]
    reason: str = Field(min_length=5, max_length=300)


class HardwareApproval(Strict):
    approve: bool
    confirmation: str = Field(max_length=80)


class ViolationUpdate(Strict):
    status: Literal["open", "under_review", "escalated", "resolved"]
    note: str | None = Field(default=None, max_length=500)


class NoteIn(Strict):
    text: str = Field(min_length=3, max_length=500)


class SettingsIn(Strict):
    confidence_threshold: float | None = Field(default=None, ge=0.3, le=0.99)
    evidence_policy: Literal["violations", "all"] | None = None
    retention_days: int | None = Field(default=None, ge=30, le=3650)
    repeat_threshold: int | None = Field(default=None, ge=2, le=20)
    repeat_window_days: int | None = Field(default=None, ge=1, le=90)
    notifications: dict[str, dict[str, bool]] | None = None
