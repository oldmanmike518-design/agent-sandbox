#!/usr/bin/env python3
from __future__ import annotations

import os
import random
import time
from dataclasses import dataclass

import httpx

BASE_URL = os.getenv("BASE_URL", "http://localhost:8000").rstrip("/")
N = int(os.getenv("N", "5"))
ROUNDS = int(os.getenv("ROUNDS", "10"))
SLEEP = float(os.getenv("SLEEP", "0.2"))


@dataclass
class SimAgent:
    name: str
    token: str
    id: str


def register(client: httpx.Client, i: int) -> SimAgent:
    name = f"SimAgent{i}_{int(time.time())}"
    r = client.post(
        f"{BASE_URL}/register",
        json={"name": name, "description": "I am a simulated agent."},
        timeout=20,
    )
    r.raise_for_status()
    obj = r.json()
    return SimAgent(name=name, token=obj["token"], id=obj["agent"]["id"])


def auth_headers(agent: SimAgent) -> dict[str, str]:
    return {"Authorization": f"Bearer {agent.token}"}


def main() -> None:
    print(f"Simulating {N} agents against {BASE_URL}")
    with httpx.Client() as client:
        agents = [register(client, i) for i in range(N)]

        for round_i in range(ROUNDS):
            sender = random.choice(agents)
            # 70% direct, 30% broadcast
            if random.random() < 0.7:
                recipient = random.choice([a for a in agents if a.id != sender.id])
                payload = {
                    "to_agent_id": recipient.id,
                    "subject": f"round {round_i}",
                    "content": f"hi {recipient.name} from {sender.name}",
                }
            else:
                payload = {"subject": f"round {round_i}", "content": f"broadcast from {sender.name}"}

            r = client.post(
                f"{BASE_URL}/message/send",
                headers=auth_headers(sender),
                json=payload,
                timeout=20,
            )
            if r.status_code == 429:
                print(f"rate-limited {sender.name}: {r.json().get('detail')}")
            else:
                r.raise_for_status()

            # occasional credit transfer
            if random.random() < 0.2:
                recipient = random.choice([a for a in agents if a.id != sender.id])
                amt = random.randint(1, 25)
                r2 = client.post(
                    f"{BASE_URL}/transaction/send",
                    headers=auth_headers(sender),
                    json={"to_agent_id": recipient.id, "amount": amt, "note": "simulation"},
                    timeout=20,
                )
                if r2.status_code not in (200, 201):
                    # ignore insufficient funds
                    print(f"tx status {r2.status_code}: {r2.text}")

            time.sleep(SLEEP)

        # Final stats
        s = client.get(f"{BASE_URL}/stats", timeout=20)
        s.raise_for_status()
        print("Public stats:")
        print(s.json())


if __name__ == "__main__":
    main()
