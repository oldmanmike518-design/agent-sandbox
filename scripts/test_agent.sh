#!/usr/bin/env bash
set -euo pipefail

BASE_URL=${BASE_URL:-http://localhost:8000}
NAME=${NAME:-TestAgent$(date +%s)}
DESC=${DESC:-"I test the sandbox."}

echo "Registering $NAME at $BASE_URL" >&2
REG=$(curl -sS -X POST "$BASE_URL/register" \
  -H "Content-Type: application/json" \
  -d "{\"name\":\"$NAME\",\"description\":\"$DESC\"}")

TOKEN=$(python3 - <<'PY'
import json,sys
obj=json.loads(sys.stdin.read())
print(obj['token'])
PY <<<"$REG")

echo "Token: ${TOKEN:0:16}..." >&2

echo "Calling /agents/me" >&2
curl -sS "$BASE_URL/agents/me" -H "Authorization: Bearer $TOKEN" | python3 -m json.tool

echo "Sending broadcast" >&2
curl -sS -X POST "$BASE_URL/message/send" \
  -H "Authorization: Bearer $TOKEN" \
  -H "Content-Type: application/json" \
  -d '{"content":"hello from test_agent.sh","subject":"hello"}' | python3 -m json.tool

echo "Inbox" >&2
curl -sS "$BASE_URL/message/inbox" -H "Authorization: Bearer $TOKEN" | python3 -m json.tool
