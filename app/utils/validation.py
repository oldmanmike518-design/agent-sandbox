from __future__ import annotations

import re


_AGENT_NAME_RE = re.compile(r"^[a-zA-Z0-9][a-zA-Z0-9_\-]{2,31}$")


def validate_agent_name(name: str) -> str:
    name = name.strip()
    if not _AGENT_NAME_RE.match(name):
        raise ValueError(
            "Invalid agent name. Use 3-32 chars: letters, numbers, underscore, hyphen. Must start with letter/number."
        )
    return name
