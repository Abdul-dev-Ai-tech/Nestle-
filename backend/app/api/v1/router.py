from fastapi import APIRouter

from app.api.v1 import (access, auth, cameras, dashboard, employees, monitoring, org, reports, users, violations)

api_router = APIRouter()
for module in (auth, users, org, employees, cameras, monitoring, access, violations, dashboard, reports):
    api_router.include_router(module.router)
