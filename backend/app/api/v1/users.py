from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, Request, status
from sqlalchemy import func, select

from app.api.deps import DB, client_ip, require
from app.models import Factory, Permission, Role, User, user_roles
from app.schemas.common import role_out, user_out
from app.schemas.inputs import RoleIn, RolePermissionsIn, UserCreate, UserUpdate
from app.security.passwords import hash_password
from app.security.permissions import PERMISSIONS
from app.services import auth as auth_svc
from app.services.audit import audit

router = APIRouter(tags=["users"])


def _roles(db, ids: list[int], actor: User) -> list[Role]:
    roles = db.scalars(select(Role).where(Role.id.in_(ids))).all()
    if len(roles) != len(set(ids)):
        raise HTTPException(status.HTTP_400_BAD_REQUEST, "Unknown role")
    if not actor.is_superuser:
        actor_rank = min(r.rank for r in actor.roles)
        if any(r.is_superuser or r.rank < actor_rank for r in roles):
            raise HTTPException(status.HTTP_403_FORBIDDEN, "You cannot assign a role higher than your own")
    return list(roles)


def _target(db, user_id: int, actor: User) -> User:
    u = db.get(User, user_id)
    if u is None or (actor.factory_id is not None and u.factory_id != actor.factory_id):
        raise HTTPException(status.HTTP_404_NOT_FOUND, "User not found")
    if u.is_superuser and not actor.is_superuser:
        raise HTTPException(status.HTTP_403_FORBIDDEN, "Only a Super Admin can change a Super Admin")
    return u


@router.get("/users")
def list_users(db: DB, actor: Annotated[User, Depends(require("users.view"))]):
    q = select(User).order_by(User.full_name)
    if actor.factory_id is not None:
        q = q.where(User.factory_id == actor.factory_id)
    return [user_out(u) for u in db.scalars(q).all()]


@router.post("/users", status_code=201)
def create_user(body: UserCreate, request: Request, db: DB, actor: Annotated[User, Depends(require("users.manage"))]):
    email = body.email.lower()
    if db.scalar(select(User.id).where(User.email == email)):
        raise HTTPException(status.HTTP_409_CONFLICT, "A user with this e-mail already exists")
    factory_id = actor.factory_id if actor.factory_id is not None else body.factory_id
    if factory_id is not None and db.get(Factory, factory_id) is None:
        raise HTTPException(status.HTTP_400_BAD_REQUEST, "Unknown factory")
    roles = _roles(db, body.role_ids, actor)
    if factory_id is None and not any(r.is_superuser for r in roles):
        raise HTTPException(status.HTTP_400_BAD_REQUEST, "Choose a factory for this user")
    auth_svc.validate_new_password(body.password, email)
    u = User(email=email, full_name=body.full_name, password_hash=hash_password(body.password), factory_id=factory_id,
             roles=roles, must_change_password=True)
    db.add(u)
    audit(db, actor, "user.create", f"Created user {email} ({', '.join(r.name for r in roles)})", ip=client_ip(request))
    db.commit()
    return user_out(u)


@router.patch("/users/{user_id}")
def update_user(user_id: int, body: UserUpdate, request: Request, db: DB,
                actor: Annotated[User, Depends(require("users.manage"))]):
    u = _target(db, user_id, actor)
    changes = []
    if body.full_name is not None:
        u.full_name = body.full_name
        changes.append("name")
    if body.role_ids is not None:
        if u.id == actor.id:
            raise HTTPException(status.HTTP_400_BAD_REQUEST, "You cannot change your own role")
        u.roles = _roles(db, body.role_ids, actor)
        changes.append("roles -> " + ", ".join(r.name for r in u.roles))
    if body.set_factory and actor.factory_id is None:
        if body.factory_id is not None and db.get(Factory, body.factory_id) is None:
            raise HTTPException(status.HTTP_400_BAD_REQUEST, "Unknown factory")
        u.factory_id = body.factory_id
        changes.append("factory")
    if body.is_active is not None and body.is_active != u.is_active:
        if u.id == actor.id:
            raise HTTPException(status.HTTP_400_BAD_REQUEST, "You cannot deactivate your own account")
        u.is_active = body.is_active
        changes.append("activated" if body.is_active else "deactivated")
        if not body.is_active:
            auth_svc.revoke_sessions(db, u.id)
    audit(db, actor, "user.update", f"{u.email}: {', '.join(changes) or 'no change'}", ip=client_ip(request))
    db.commit()
    return user_out(u)


@router.post("/users/{user_id}/revoke-sessions")
def revoke_user_sessions(user_id: int, request: Request, db: DB,
                         actor: Annotated[User, Depends(require("users.manage"))]):
    u = _target(db, user_id, actor)
    n = auth_svc.revoke_sessions(db, u.id)
    audit(db, actor, "user.sessions_revoked", f"{u.email}: {n} session(s) revoked", ip=client_ip(request))
    db.commit()
    return {"revoked": n}


# ---------- roles & permissions ----------
@router.get("/permissions")
def list_permissions(_: Annotated[User, Depends(require("users.view"))]):
    return [{"code": c, "category": cat, "description": d} for c, cat, d in PERMISSIONS]


@router.get("/roles")
def list_roles(db: DB, _: Annotated[User, Depends(require("users.view"))]):
    counts = dict(db.execute(select(user_roles.c.role_id, func.count()).group_by(user_roles.c.role_id)).all())
    return [role_out(r, counts.get(r.id, 0)) for r in db.scalars(select(Role).order_by(Role.rank, Role.id)).all()]


def _perms(db, codes: list[str]) -> list[Permission]:
    perms = db.scalars(select(Permission).where(Permission.code.in_(codes))).all()
    if len(perms) != len(set(codes)):
        raise HTTPException(status.HTTP_400_BAD_REQUEST, "Unknown permission code")
    return list(perms)


@router.post("/roles", status_code=201)
def create_role(body: RoleIn, request: Request, db: DB, actor: Annotated[User, Depends(require("roles.manage"))]):
    if db.scalar(select(Role.id).where(func.lower(Role.name) == body.name.lower())):
        raise HTTPException(status.HTTP_409_CONFLICT, "A role with this name already exists")
    r = Role(name=body.name, description=body.description, permissions=_perms(db, body.permissions), rank=50)
    db.add(r)
    audit(db, actor, "role.create", f"Created role {r.name}", ip=client_ip(request))
    db.commit()
    return role_out(r)


@router.put("/roles/{role_id}/permissions")
def set_role_permissions(role_id: int, body: RolePermissionsIn, request: Request, db: DB,
                         actor: Annotated[User, Depends(require("roles.manage"))]):
    r = db.get(Role, role_id)
    if r is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Role not found")
    if r.is_superuser:
        raise HTTPException(status.HTTP_400_BAD_REQUEST, "Super Admin always has every permission")
    before = {p.code for p in r.permissions}
    r.permissions = _perms(db, body.permissions)
    after = set(body.permissions)
    audit(db, actor, "role.permissions", f"{r.name}: +{sorted(after - before)} -{sorted(before - after)}",
          ip=client_ip(request))
    db.commit()
    return role_out(r)


@router.delete("/roles/{role_id}")
def delete_role(role_id: int, request: Request, db: DB, actor: Annotated[User, Depends(require("roles.manage"))]):
    r = db.get(Role, role_id)
    if r is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Role not found")
    if r.is_system:
        raise HTTPException(status.HTTP_400_BAD_REQUEST, "Built-in roles cannot be deleted")
    if db.scalar(select(func.count()).select_from(user_roles).where(user_roles.c.role_id == r.id)):
        raise HTTPException(status.HTTP_409_CONFLICT, "Move this role's users to another role first")
    db.delete(r)
    audit(db, actor, "role.delete", f"Deleted role {r.name}", ip=client_ip(request))
    db.commit()
    return {"ok": True}
