"""
Central configuration using pydantic-settings.
All values come from environment variables or .env file.
"""
from pathlib import Path
from typing import List
from pydantic_settings import BaseSettings
from pydantic import Field


class Settings(BaseSettings):
    # LLM
    llm_provider: str = Field(default="openai", env="LLM_PROVIDER")
    llm_model: str = Field(default="gpt-4o", env="LLM_MODEL")
    llm_api_key: str = Field(default="", env="LLM_API_KEY")

    # Embedding
    embedding_model: str = Field(default="all-MiniLM-L6-v2", env="EMBEDDING_MODEL")

    # RAG
    rag_top_k: int = Field(default=5, env="RAG_TOP_K")

    # Storage
    database_url: str = Field(default="sqlite:///./buglocalizer.db", env="DATABASE_URL")
    workspace_dir: str = Field(default="./workspaces", env="WORKSPACE_DIR")

    # Ground-truth protection: these paths are NEVER read during localization
    ground_truth_exclusions: str = Field(
        default="BUG_DATASET.md,bug_dataset.json,bug_dataset.csv,dataset,ground_truth,evaluation,corrected_patches",
        env="GROUND_TRUTH_EXCLUSIONS",
    )

    # Security
    max_repo_size_mb: int = Field(default=500, env="MAX_REPO_SIZE_MB")
    clone_timeout_seconds: int = Field(default=120, env="CLONE_TIMEOUT_SECONDS")

    # Docker verification
    enable_docker_verification: bool = Field(default=True, env="ENABLE_DOCKER_VERIFICATION")
    docker_timeout_seconds: int = Field(default=120, env="DOCKER_TIMEOUT_SECONDS")

    # Prompt version (for reproducibility tracking)
    prompt_version: str = "v1.0.0"

    class Config:
        env_file = ".env"
        env_file_encoding = "utf-8"

    @property
    def ground_truth_exclusion_list(self) -> List[str]:
        return [p.strip() for p in self.ground_truth_exclusions.split(",") if p.strip()]

    @property
    def workspace_path(self) -> Path:
        p = Path(self.workspace_dir)
        p.mkdir(parents=True, exist_ok=True)
        return p


settings = Settings()
