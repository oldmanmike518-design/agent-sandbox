# Agent Instructions

This is the canonical Agent Sandbox workspace.

Before working:

1. Read `agent-sandbox-handoff.md` for current state and ordered work. **The handoff is the authoritative execution order.**
2. Read `agent-sandbox-log.md` for durable history and audit findings. **The running log now contains two independent audits: the Codex audit (2026-07-16, Session 2) and the Claude independent security/product/commercial review (2026-07-16, Session 3).** Both are preserved; do not rewrite or delete either.
3. Consult `agent-sandbox-brief.md`, `MARKETING-PLAN.md`, and `SECURITY.md` only as supporting context.

Working rules:

- Work only in `/Users/michaellanger/Projects/agent-sandbox`.
- Do not edit duplicate copies under Documents, Codex, or bug-bounties.
- Append meaningful completed work and decisions to `agent-sandbox-log.md`.
- Update `agent-sandbox-handoff.md` at the end of every session.
- Never commit `.env`, credentials, JWT secrets, database URLs, API tokens, private keys, seed phrases, or provider secrets.
- Public cryptocurrency **receiving addresses and required destination memos are intentional and are NOT secrets** — they exist so people and agents can send tips. Do not flag them as leaked. Only private keys, seed phrases, exchange/API credentials, JWT secrets, and database credentials are sensitive authentication material.
- Use placeholders for sensitive authentication material in examples and documentation.
- Do not push, deploy, rotate credentials, or change external services without explicit user authorization.
- **Public promotion remains blocked until the handoff launch gate is satisfied.**
