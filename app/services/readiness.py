from __future__ import annotations

from dataclasses import dataclass
from functools import lru_cache
from pathlib import Path

from alembic.config import Config
from alembic.script import ScriptDirectory
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession


@dataclass(frozen=True)
class ReadinessResult:
    ready: bool
    database: str
    schema: str


@lru_cache(maxsize=1)
def expected_schema_revision() -> str:
    project_root = Path(__file__).resolve().parents[2]
    config = Config()
    config.set_main_option("script_location", str(project_root / "alembic"))
    revision = ScriptDirectory.from_config(config).get_current_head()
    if revision is None:
        raise RuntimeError("Alembic has no head revision")
    return revision


async def check_readiness(session: AsyncSession) -> ReadinessResult:
    result = await session.execute(text("SELECT version_num FROM alembic_version"))
    current_revision = result.scalar_one_or_none()
    schema = "current" if current_revision == expected_schema_revision() else "mismatch"
    return ReadinessResult(
        ready=schema == "current",
        database="available",
        schema=schema,
    )
