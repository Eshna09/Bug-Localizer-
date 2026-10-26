"""
SQLite-backed experiment storage.
Stores every analysis and experiment for reproducibility and later evaluation.
"""
from __future__ import annotations
import json
import logging
from datetime import datetime, timezone
from typing import List, Optional, Generator

from sqlalchemy import (
    create_engine, Column, String, Text, DateTime, Float, Boolean,
    Integer, JSON
)
from sqlalchemy.orm import declarative_base, Session, sessionmaker

from config.settings import settings

logger = logging.getLogger(__name__)

Base = declarative_base()
engine = create_engine(settings.database_url, connect_args={"check_same_thread": False})
SessionLocal = sessionmaker(bind=engine, autocommit=False, autoflush=False)


class AnalysisRow(Base):
    __tablename__ = "analyses"

    id = Column(String, primary_key=True)
    repo_url = Column(String, nullable=False)
    commit_hash = Column(String)
    detected_language = Column(String)
    issue_description = Column(Text)
    status = Column(String)
    timestamp = Column(DateTime, default=lambda: datetime.now(timezone.utc))

    # Full result stored as JSON
    result_json = Column(Text)


class ExperimentRow(Base):
    __tablename__ = "experiments"

    id = Column(String, primary_key=True)
    bug_id = Column(String, nullable=False)
    repository_url = Column(String)
    commit_hash = Column(String)
    approach = Column(String)
    model = Column(String)
    embedding_model = Column(String)
    prompt_version = Column(String)
    rag_top_k = Column(Integer)
    latency_ms = Column(Float)
    token_usage = Column(JSON)
    predictions_json = Column(Text)
    retrieved_chunks_json = Column(Text)
    timestamp = Column(DateTime, default=lambda: datetime.now(timezone.utc))
    error = Column(Text, nullable=True)


class FixRow(Base):
    __tablename__ = "fixes"

    id = Column(String, primary_key=True)
    analysis_id = Column(String)
    bug_id = Column(String)
    predicted_file = Column(String)
    predicted_function = Column(String)
    generated_patch = Column(Text)
    verification_status = Column(String)
    tests_before_json = Column(Text)
    tests_after_json = Column(Text)
    timestamp = Column(DateTime, default=lambda: datetime.now(timezone.utc))


class EvaluationPreviewRow(Base):
    __tablename__ = "evaluation_previews"

    id = Column(String, primary_key=True)
    data_json = Column(Text, nullable=False)


def init_db() -> None:
    """Create all tables if they don't exist."""
    Base.metadata.create_all(bind=engine)
    from evaluation.demo_metrics import DEMO_EVALUATION

    with SessionLocal() as db:
        preview = db.get(EvaluationPreviewRow, "shopbug-demo-v1")
        if preview is None:
            db.add(EvaluationPreviewRow(
                id="shopbug-demo-v1",
                data_json=json.dumps(DEMO_EVALUATION),
            ))
            db.commit()
    logger.info("Database initialized: %s", settings.database_url)


def get_db() -> Generator[Session, None, None]:
    """FastAPI dependency: yields a database session."""
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()


class Database:
    """High-level database operations."""

    def __init__(self, db: Session):
        self.db = db

    def get_evaluation_preview(self) -> Optional[dict]:
        """Retrieve the persisted illustrative evaluation dashboard data."""
        row = self.db.get(EvaluationPreviewRow, "shopbug-demo-v1")
        if not row:
            return None
        return json.loads(row.data_json)

    def save_analysis(self, analysis_id: str, result_dict: dict) -> None:
        """Save or update a complete analysis result."""
        existing = self.db.query(AnalysisRow).filter_by(id=analysis_id).first()
        if existing:
            existing.result_json = json.dumps(result_dict)
            existing.status = result_dict.get("status", "completed")
        else:
            row = AnalysisRow(
                id=analysis_id,
                repo_url=result_dict.get("repo_url", ""),
                commit_hash=result_dict.get("commit_hash", ""),
                detected_language=result_dict.get("detected_language", ""),
                issue_description=result_dict.get("issue_description", ""),
                status=result_dict.get("status", "completed"),
                result_json=json.dumps(result_dict),
            )
            self.db.add(row)
        self.db.commit()

    def get_analysis(self, analysis_id: str) -> Optional[dict]:
        """Retrieve a complete analysis result."""
        row = self.db.query(AnalysisRow).filter_by(id=analysis_id).first()
        if not row or not row.result_json:
            return None
        return json.loads(row.result_json)

    def list_analyses(self, limit: int = 50) -> List[dict]:
        """List recent analyses (summary only)."""
        rows = (
            self.db.query(AnalysisRow)
            .order_by(AnalysisRow.timestamp.desc())
            .limit(limit)
            .all()
        )
        results = []
        for row in rows:
            entry = {
                "id": row.id,
                "repo_url": row.repo_url,
                "commit_hash": row.commit_hash,
                "status": row.status,
                "timestamp": row.timestamp.isoformat() if row.timestamp else None,
                "issue_description": (row.issue_description or "")[:200],
            }
            # Extract top prediction from result_json if available
            if row.result_json:
                try:
                    result = json.loads(row.result_json)
                    preds = result.get("primary_predictions", [])
                    if preds:
                        top = preds[0]
                        entry["top_prediction"] = f"{top.get('file', '')} :: {top.get('function', '')}"
                    entry["verification_status"] = (
                        result.get("verification", {}) or {}
                    ).get("status", "N/A")
                except Exception:
                    pass
            results.append(entry)
        return results

    def save_experiment(self, exp_id: str, data: dict) -> None:
        """Save a localization experiment record."""
        row = ExperimentRow(
            id=exp_id,
            bug_id=data.get("bug_id", ""),
            repository_url=data.get("repository_url", ""),
            commit_hash=data.get("commit_hash", ""),
            approach=data.get("approach", ""),
            model=data.get("model"),
            embedding_model=data.get("embedding_model"),
            prompt_version=data.get("prompt_version"),
            rag_top_k=data.get("rag_top_k"),
            latency_ms=data.get("latency_ms"),
            token_usage=data.get("token_usage"),
            predictions_json=json.dumps(data.get("predictions", [])),
            retrieved_chunks_json=json.dumps(data.get("retrieved_chunks", [])),
            error=data.get("error"),
        )
        self.db.add(row)
        self.db.commit()

    def save_fix(self, fix_id: str, data: dict) -> None:
        """Save a fix and verification record."""
        row = FixRow(
            id=fix_id,
            analysis_id=data.get("analysis_id", ""),
            bug_id=data.get("bug_id", ""),
            predicted_file=data.get("predicted_file", ""),
            predicted_function=data.get("predicted_function", ""),
            generated_patch=data.get("generated_patch", ""),
            verification_status=data.get("verification_status", ""),
            tests_before_json=json.dumps(data.get("tests_before", [])),
            tests_after_json=json.dumps(data.get("tests_after", [])),
        )
        self.db.add(row)
        self.db.commit()
