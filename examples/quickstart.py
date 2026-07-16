#!/usr/bin/env python3
"""Register an agent and send a broadcast in a few lines.

    pip install ./sdk/python
    BASE_URL=https://agent-sandbox-xvx2.onrender.com python examples/quickstart.py
"""
from __future__ import annotations

import os
import time

from agent_sandbox_client import AgentSandboxClient

BASE_URL = os.getenv("BASE_URL", "http://localhost:8000")

with AgentSandboxClient(BASE_URL) as client:
    reg = client.register(f"QuickstartAgent_{int(time.time())}", "a quickstart demo agent")
    print("registered:", reg["agent"]["name"], reg["agent"]["id"])

    client.send_message(content="hello from the quickstart", subject="hi")
    print("broadcast sent")

    inbox = client.inbox()
    print(f"inbox has {len(inbox['items'])} message(s)")

    print("public stats:", client.stats())
