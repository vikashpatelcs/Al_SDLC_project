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

# Ensure tables are created on startup
Base.metadata.create_all(bind=engine)

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
