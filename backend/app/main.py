from backend.app.api.auth import router as auth_router
from backend.app.api.admin import router as admin_router
from backend.app.api.cases import router as cases_router
from backend.app.api.evidence import router as evidence_router
from fastapi import FastAPI
from backend.app.api.decisions import router as decisions_router
from sqlalchemy import text
from sqlalchemy.exc import SQLAlchemyError
from backend.app.api.appeals import router as appeals_router

from backend.app.database import engine
from backend.app.config import get_settings


settings = get_settings()

app = FastAPI(
    title="Academic Integrity Case Management System",
    version="0.1.0",
    description="Academic integrity case review and management API.",
)


@app.get("/")
def root():
    return {
        "message": "Academic Integrity Case Management System API",
        "environment": settings.app_env,
    }


@app.get("/health")
def health():
    return {"status": "ok"}


@app.get("/health/database")
def database_health():
    try:
        with engine.connect() as connection:
            connection.execute(text("SELECT 1"))
        return {"status": "ok", "database": "connected"}
    except SQLAlchemyError:
        return {
            "status": "error",
            "database": "unavailable",
        }


app.include_router(auth_router)
app.include_router(admin_router)
app.include_router(cases_router)
app.include_router(evidence_router)
app.include_router(decisions_router)
app.include_router(appeals_router)
