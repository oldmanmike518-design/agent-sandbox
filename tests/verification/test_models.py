from __future__ import annotations

from app.db.base import Base
from app.models.verification import (  # noqa: F401
    VerificationObservation,
    VerificationOutboxAction,
    VerificationReport,
    VerificationRun,
)


def test_tables_registered():
    names = set(Base.metadata.tables)
    assert {
        "verification_runs",
        "verification_reports",
        "verification_report_publication",
        "verification_observations",
        "verification_outbox",
    } <= names


def test_one_open_run_partial_unique_index():
    table = Base.metadata.tables["verification_runs"]
    partial = [
        ix for ix in table.indexes
        if ix.name == "uq_verification_runs_one_open"
    ]
    assert partial and partial[0].unique
    assert "agent_id" in [c.name for c in partial[0].columns]


def test_report_run_unique():
    table = Base.metadata.tables["verification_reports"]
    unique_cols = {
        c.name
        for constraint in table.constraints
        for c in getattr(constraint, "columns", [])
        if getattr(constraint, "__class__", None).__name__ == "UniqueConstraint"
    }
    run_id_unique = table.c.run_id.unique or "run_id" in unique_cols
    assert run_id_unique


def test_agent_has_system_operated_flag():
    from app.models.agent import Agent

    assert hasattr(Agent, "system_operated")
