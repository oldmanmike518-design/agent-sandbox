#!/usr/bin/env python3
"""Regenerate the checked-in discovery artifacts.

Writes ``llms.txt``, ``.well-known/agent-manifest.json``, and ``openapi.json`` at
the repository root so framework integrations and crawlers can discover the API
without hitting a live server.

Usage:
    PUBLIC_BASE_URL=https://your-host ENV=dev DATABASE_URL=... \
        python scripts/dump_discovery.py
"""
from __future__ import annotations

import json
from pathlib import Path

from app.core.discovery import build_agent_manifest, build_llms_txt
from app.main import app

ROOT = Path(__file__).resolve().parents[1]


def main() -> None:
    (ROOT / "llms.txt").write_text(build_llms_txt(), encoding="utf-8")

    well_known = ROOT / ".well-known"
    well_known.mkdir(exist_ok=True)
    (well_known / "agent-manifest.json").write_text(
        json.dumps(build_agent_manifest(), indent=2) + "\n", encoding="utf-8"
    )

    (ROOT / "openapi.json").write_text(
        json.dumps(app.openapi(), indent=2) + "\n", encoding="utf-8"
    )
    print("Wrote llms.txt, .well-known/agent-manifest.json, openapi.json")


if __name__ == "__main__":
    main()
