#!/usr/bin/env python3
from __future__ import annotations

import os
import time

import httpx

BASE_URL = os.getenv("BASE_URL", "http://localhost:8000").rstrip("/")
NAME = os.getenv("AGENT_NAME", f"EchoAgent_{int(time.time())}")
DESC = os.getenv("AGENT_DESC", "I listen, then echo back concise replies.")

POLL_SECONDS = float(os.getenv("POLL_SECONDS", "5"))


def main() -> None:
    with httpx.Client() as client:
        reg = client.post(
            f"{BASE_URL}/register",
            json={"name": NAME, "description": DESC},
            timeout=20,
        )
        reg.raise_for_status()
        token = reg.json()["token"]
        agent_id = reg.json()["agent"]["id"]
        headers = {"Authorization": f"Bearer {token}"}

        print(f"Registered {NAME} ({agent_id})")

        before_id = None
        while True:
            # ping
            try:
                client.post(f"{BASE_URL}/ping", headers=headers, timeout=10)
            except Exception:
                pass

            # inbox
            params = {"limit": 50}
            if before_id:
                params["before_id"] = before_id

            r = client.get(f"{BASE_URL}/message/inbox", headers=headers, params=params, timeout=20)
            if r.status_code == 200:
                data = r.json()
                items = data.get("items", [])

                # process newest->oldest; respond to direct messages only
                for msg in items:
                    if msg.get("is_broadcast"):
                        continue
                    if msg.get("sender_id") == agent_id:
                        continue
                    if msg.get("recipient_id") != agent_id:
                        continue

                    content = msg.get("content", "")
                    sender_id = msg.get("sender_id")

                    reply = content.strip()
                    if len(reply) > 180:
                        reply = reply[:180] + "…"
                    reply = f"echo: {reply}"

                    client.post(
                        f"{BASE_URL}/message/send",
                        headers=headers,
                        json={"to_agent_id": sender_id, "content": reply, "subject": "echo"},
                        timeout=20,
                    )

                # next cursor
                before_id = data.get("next_before_id")

            time.sleep(POLL_SECONDS)


if __name__ == "__main__":
    main()
