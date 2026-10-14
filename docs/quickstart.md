# Quickstart

## Run it

```bash
cd your-project
uvx upfront          # what's configured, no servers started
uvx upfront --yes    # also start servers and count their tools
```

Or install it: `pip install upfront`.

Without `--yes`, upfront lists the servers it would start and asks (in a terminal) or skips
them (in CI). Skills and instruction files are always measured; they're just files.

## Try it on the demo project

```bash
git clone https://github.com/thanatchon36/upfront && cd upfront
uv run upfront examples/demo --yes
```

The demo's servers replay `tools/list` snapshots of three official MCP reference servers, so
it works offline and gives the same numbers every time.

## Common options

| Option | What it does |
|---|---|
| `-H codex` | Only this harness (repeatable): `claude-code`, `codex`, `gemini-cli`, `opencode`, `cursor` |
| `--top 10` | List the 10 heaviest tools per server (default 3) |
| `--json` | Machine-readable report |
| `--budget 20000` | Exit 1 if any harness loads more than 20,000 tokens up front |
| `--strict` | Exit 1 on error-level compatibility findings |
| `--tools-file tools.json` | Measure a saved `tools/list` instead of reading configs |
| `--timeout 60` | Seconds to wait per server (default 20) |

## In CI, for an MCP server you maintain

Save your server's tool list and check it on every pull request:

```yaml
- run: uvx upfront --tools-file tools.json --strict --budget 8000
```

Or launch the server from a config in the repository and use `--yes`.
