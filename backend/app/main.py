"""
FastAPI application entrypoint for FinReq AI.
"""
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from backend.app.config import settings
from backend.app.core.session import SessionMiddleware
from backend.app.db.session import engine, Base
import backend.app.db.models  # Register models with Base
from backend.app.api.chats import router as chats_router
from backend.app.api.approvals import router as approvals_router

from sqlalchemy import text

# Ensure tables are created on startup
Base.metadata.create_all(bind=engine)

def ensure_schema_migrated(db_engine):
    """Ensure newly introduced Phase 13 columns exist on legacy SQLite tables."""
    with db_engine.connect() as conn:
        try:
            res = conn.execute(text("PRAGMA table_info(agent_executions)")).fetchall()
            cols = {r[1] for r in res}
            if cols:
                if "model_version" not in cols:
                    conn.execute(text("ALTER TABLE agent_executions ADD COLUMN model_version VARCHAR(64)"))
                if "kb_version" not in cols:
                    conn.execute(text("ALTER TABLE agent_executions ADD COLUMN kb_version VARCHAR(64)"))
                if "prompt_version" not in cols:
                    conn.execute(text("ALTER TABLE agent_executions ADD COLUMN prompt_version VARCHAR(64)"))

            res_chats = conn.execute(text("PRAGMA table_info(chats)")).fetchall()
            cols_chats = {r[1] for r in res_chats}
            if cols_chats and "deleted_at" not in cols_chats:
                conn.execute(text("ALTER TABLE chats ADD COLUMN deleted_at DATETIME"))
            conn.commit()
        except Exception:
            pass

ensure_schema_migrated(engine)

app = FastAPI(
    title=settings.PROJECT_NAME,
    version=settings.VERSION,
    description="Multi-agent requirements elicitation and SDLC recommendation system.",
)

# Anonymous session middleware (sets / checks anon_session_token HttpOnly cookie)
app.add_middleware(SessionMiddleware)

# CORS middleware supporting credentials (cookies)
app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.CORS_ORIGINS,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Mount API routers
app.include_router(chats_router, prefix=settings.API_V1_PREFIX)
app.include_router(approvals_router, prefix=settings.API_V1_PREFIX)


@app.get("/health")
def health_check():
    """Healthcheck endpoint."""
    return {
        "status": "healthy",
        "service": settings.PROJECT_NAME,
        "version": settings.VERSION,
        "env": settings.ENV,
    }


if __name__ == "__main__":
    import uvicorn
    uvicorn.run("backend.app.main:app", host="127.0.0.1", port=8000, reload=True)
