# Agent Instructions

This is the canonical Agent Sandbox workspace.

Before working:

1. Read `agent-sandbox-handoff.md` for current state and ordered work. **The handoff is the authoritative execution order.**
2. Read `agent-sandbox-log.md` for durable history and audit findings. **The running log preserves the Codex audit (Session 2), Claude's independent review (Session 3), the merged engineering sprint (Session 15), the production/deployment closeout (Session 16), and the production smoke/capacity closeout (Session 17).** Do not rewrite or delete prior sessions.
3. Use `DEPLOYMENT_HANDOFF.md` for production facts and `PROMOTION-COMMAND-CENTER.md` for the controlled seed/broad-launch sequence. Consult `agent-sandbox-brief.md`, `MARKETING-PLAN.md`, and `SECURITY.md` as supporting context.

Working rules:

- Work only in `/Users/michaellanger/Projects/agent-sandbox`.
- The former duplicate copies under Documents/Codex and bug-bounties were removed on 2026-07-19. Do not recreate or work from duplicate checkouts.
- Append meaningful completed work and decisions to `agent-sandbox-log.md`.
- Update `agent-sandbox-handoff.md` at the end of every session.
- Never commit `.env`, credentials, JWT secrets, database URLs, API tokens, private keys, seed phrases, or provider secrets.
- Public cryptocurrency **receiving addresses and required destination memos are intentional and are NOT secrets** — they exist so people and agents can send tips. Do not flag them as leaked. Only private keys, seed phrases, exchange/API credentials, JWT secrets, and database credentials are sensitive authentication material.
- Use placeholders for sensitive authentication material in examples and documentation.
- Do not push, deploy, rotate credentials, or change external services without explicit user authorization.
- **Controlled seed outreach is open. Broad Show HN/Reddit promotion remains gated by the five explicit boxes in the handoff.**
