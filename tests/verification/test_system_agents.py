from __future__ import annotations

import uuid

from app.services.system_agents import (
    CONFORMANCE_AGENT_ID,
    CONFORMANCE_AGENT_NAME,
    is_reserved_agent_name,
)


def test_stable_identity_constants():
    assert isinstance(CONFORMANCE_AGENT_ID, uuid.UUID)
    assert CONFORMANCE_AGENT_NAME == "InteropConformanceAgent"


def test_reserved_name_is_case_insensitive():
    assert is_reserved_agent_name("InteropConformanceAgent")
    assert is_reserved_agent_name("interopconformanceagent")
    assert is_reserved_agent_name("  INTEROPCONFORMANCEAGENT  ")
    assert not is_reserved_agent_name("MyAgent")
