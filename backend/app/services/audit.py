from sqlalchemy.orm import Session

from app.models import AuditLog, User


def audit(db: Session, user: User | None, action: str, detail: str = "", *, ip: str = "",
          factory_id: int | None = None, email: str | None = None) -> None:
    """Append an audit entry. The caller commits. Never pass secrets in `detail`."""
    db.add(AuditLog(factory_id=factory_id if factory_id is not None else (user.factory_id if user else None),
                    user_id=user.id if user else None, user_email=email or (user.email if user else "system"),
                    action=action[:80], detail=detail[:2000], ip=ip[:64]))
