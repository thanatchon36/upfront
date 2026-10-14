# Concepts

## What "up front" means

Before you type anything, a coding agent puts three kinds of things you control into the
model's context:

1. **MCP tool definitions**: every tool's name, description and JSON schemas, from every
   connected server. Some clients load them lazily (Claude Code's tool search, OpenCode's lazy
   loading); upfront reports the full cost, which is what you pay when they are loaded.
2. **Skill metadata**: each skill's `name` and `description`. The body of `SKILL.md` only loads
   when the skill is used, so upfront reports it separately as "on demand".
3. **Instruction files**: `CLAUDE.md` (or `AGENTS.md` when there is no `CLAUDE.md`) for Claude
   Code, `AGENTS.md` for Codex and OpenCode, `GEMINI.md` for Gemini CLI, at the project root and
   in the user's config directory.

The agent's own system prompt is not included. It belongs to the vendor and changes between
releases.

## Where upfront looks

| Harness | MCP servers | Skills | Instructions |
|---|---|---|---|
| Claude Code | `.mcp.json`; `~/.claude.json` (user and per-project "local" scope) | `.claude/skills`, `~/.claude/skills` | `CLAUDE.md` (else `AGENTS.md`), `~/.claude/CLAUDE.md` |
| Codex | `.codex/config.toml`, `~/.codex/config.toml` (`[mcp_servers.*]`) | `.agents/skills`, `~/.agents/skills` | `AGENTS.md`, `~/.codex/AGENTS.md` |
| Gemini CLI | `.gemini/settings.json`, `~/.gemini/settings.json` (`mcpServers`) | none | `GEMINI.md`, `~/.gemini/GEMINI.md` |
| OpenCode | `opencode.json[c]`, `~/.config/opencode/opencode.json[c]` (`mcp`) | `.opencode/skills`, `.claude/skills`, `.agents/skills` and the matching user folders | `AGENTS.md`, `~/.config/opencode/AGENTS.md` |
| Cursor | `.cursor/mcp.json`, `~/.cursor/mcp.json` (`mcpServers`) | none | none |

Only root-level instruction files are read; nested `AGENTS.md` files load when the agent
works in that folder, not up front.

## How tokens are counted

One tokenizer, `o200k_base`, for every harness, applied to the compact JSON of each tool's
wire fields (`name`, `title`, `description`, `inputSchema`, `outputSchema`, `annotations`).
Numbers are estimates and are printed with "≈"; they rank servers reliably, but a vendor's own
count will differ. Clients also wrap tools in their own framing, which upfront doesn't add.
If the tokenizer can't load (offline), upfront falls back to characters ÷ 4 and says so in
the header. See [ADR-0003](decisions/ADR-0003-tokenizer.md).

## Compatibility findings

Each finding names a rule and links its source. Rules come only from official API
documentation or from issues that are still open; bugs that clients have already fixed are
not rules. The full table is at the end of the [API reference](api.md#compatibility-rules).

## Starting servers safely

To count a stdio server's tools, upfront runs the server's command, from the project directory,
exactly as the agent would. A cloned repository's config can name any command, so upfront asks
first (or needs `--yes`). It only calls `tools/list`; it never calls a tool. See
[ADR-0004](decisions/ADR-0004-consent-before-launching.md).
