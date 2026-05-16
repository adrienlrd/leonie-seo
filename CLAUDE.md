@AGENTS.md

## Claude Code specific instructions

Use `permissionMode: plan` or switch to plan mode before:
- Large refactors or architecture changes
- Database schema or migration changes
- Shopify OAuth, billing, webhook, or API scope changes
- Deployment or production config changes

Prefer read-only exploration before editing.

Use project subagents from `.claude/agents/` when relevant:
- `code-reviewer`
- `test-triage`
- `shopify-architecture-reviewer`

Do not duplicate rules from `AGENTS.md` here.
If a rule conflicts with `AGENTS.md`, `AGENTS.md` wins unless the user explicitly says otherwise.

Update `docs/AI_HANDOFF.md` after every meaningful change.
