"""
FastAPI application entry point.
"""
from __future__ import annotations
import logging
from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from api.routes import router
from api.streaming import stream_router
from storage.database import init_db
from config.settings import settings

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
)
logger = logging.getLogger(__name__)


@asynccontextmanager
async def lifespan(app: FastAPI):
    # Startup
    logger.info("Initializing database...")
    init_db()
    logger.info("Bug Localizer API ready.")
    logger.info("LLM: %s / %s", settings.llm_provider, settings.llm_model)
    logger.info("Embedding model: %s", settings.embedding_model)
    yield
    # Shutdown
    logger.info("Shutting down.")


app = FastAPI(
    title="Repository-Aware AI Bug Localizer",
    description="Research platform for evaluating LLM-based bug localization vs conventional techniques.",
    version="1.0.0",
    lifespan=lifespan,
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=[
        "http://localhost:5173",
        "http://localhost:5174",
        "http://localhost:3000",
        "http://127.0.0.1:5173",
        "http://127.0.0.1:5174",
    ],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(router, prefix="/api")
app.include_router(stream_router, prefix="/api")


if __name__ == "__main__":
    import uvicorn
    uvicorn.run(
        "main:app",
        host="0.0.0.0",
        port=8000,
        reload=True,
        # Only watch source directories — never watch workspaces/ (cloned repos)
        reload_dirs=[
            "api", "core", "localization", "config",
            "storage", "evaluation", "explanation", "fix", "verification",
        ],
    )
