# upfront

[![ci](https://github.com/thanatchon36/upfront/actions/workflows/ci.yml/badge.svg)](https://github.com/thanatchon36/upfront/actions/workflows/ci.yml)
[![coverage](https://codecov.io/gh/thanatchon36/upfront/graph/badge.svg)](https://codecov.io/gh/thanatchon36/upfront)
[![PyPI](https://img.shields.io/pypi/v/upfront?v=1)](https://pypi.org/project/upfront/)
[![Python](https://img.shields.io/pypi/pyversions/upfront?v=1)](https://pypi.org/project/upfront/)
[![license: MIT](https://img.shields.io/badge/license-MIT-blue)](https://github.com/thanatchon36/upfront/blob/main/LICENSE)

See how many tokens your MCP servers, skills and instruction files cost a coding agent before
you type a word, and which tools will break in Claude Code, Codex, Gemini CLI, OpenCode or Cursor.

## The problem

> "Claude Code sends 33k tokens before reading the prompt; OpenCode sends 7k"
> — [Hacker News, 706 points](https://news.ycombinator.com/item?id=48883275); finding out took a logging proxy.

Every connected MCP server puts all of its tool schemas into the context, every skill adds its
description, and AGENTS.md / CLAUDE.md ride along on every request. Usage limits arrive early,
and Codex starts dropping skills ([codex#19679](https://github.com/openai/codex/issues/19679))
and MCP tools ([codex#44308](https://github.com/openai/codex/issues/44308)) once budgets run
out. Claude Code's `/context` shows this for Claude Code only; OpenCode closed the request as
[not planned](https://github.com/anomalyco/opencode/issues/11995).

## Demo

![upfront measuring a demo project with three official MCP servers](https://raw.githubusercontent.com/thanatchon36/upfront/main/docs/demo.gif)

```console
$ uv run upfront examples/demo --yes --top 2      # in a clone of this repository
upfront 0.1.0 · examples/demo · tokens o200k_base

claude-code                                      ≈ 6,786  before your first prompt
  mcp filesystem (14 tools, project)             ≈ 2,751  41% of total
      read_media_file                              ≈ 285
      read_text_file                               ≈ 251
  mcp memory (9 tools, project)                  ≈ 2,365  35% of total
      create_entities                              ≈ 349
      search_nodes                                 ≈ 320
  mcp everything (13 tools, project)             ≈ 1,602  24% of total
      gzip-file-as-resource                        ≈ 239
      get-structured-content                       ≈ 186
  skills (2, name + description)                    ≈ 33  bodies ≈ 48 load on demand
  CLAUDE.md                                         ≈ 35
...
compatibility
  error   codex       issue-scenarios.files.read: 'files.read' (10 chars) is not a valid OpenAI function name
          [openai-tool-name] https://github.com/openai/openai-python/blob/main/src/openai/types/shared_params/function_definition.py
```

The demo's servers replay `tools/list` snapshots of the official
[filesystem, memory and everything](https://github.com/modelcontextprotocol/servers) reference
servers (1.0.0), so the numbers above are what those servers really cost.

## Install

```bash
uvx upfront            # run from your project, no install
pip install upfront
```

Python 3.11+. Then, in a project:

```bash
upfront          # skills, instruction files and the list of servers; starts nothing
upfront --yes    # also start/connect to each MCP server and count its tools
```

## Features

- **Five harnesses, both scopes.** Reads Claude Code, Codex, Gemini CLI, OpenCode and Cursor configs from the project and your home directory, including `${VAR:-default}` expansion and JSONC.
- **Real tool lists.** Talks to every stdio, Streamable HTTP and SSE server with the official MCP SDK, follows pagination, and reports failures (missing command, timeout, "auth required") per server instead of crashing.
- **Where the tokens go.** Per server and per tool, skill metadata separately from skill bodies, and every instruction file.
- **Compatibility checks with sources.** Tool names against OpenAI, Anthropic and Gemini rules, `$ref` parameters in Claude Code, non-standard formats in OpenCode, and Codex's skills budget. Every finding links the documentation or open issue it comes from.
- **CI-friendly.** `--json`, `--budget N` and `--strict` exit codes, and `--tools-file` to check a saved `tools/list` without starting anything.
- **Safe by default.** Nothing is launched without consent: it asks in a terminal and needs `--yes` elsewhere. It only ever calls `tools/list`.

## How it compares

| | upfront | Claude Code [`/context`](https://code.claude.com/docs/en/commands) | [mcp-assert](https://github.com/blackwell-systems/mcp-assert) | [ccusage](https://github.com/ccusage/ccusage) |
|---|---|---|---|---|
| Up-front cost of MCP tools, skills, instruction files | yes, per harness | yes, Claude Code only | no | no |
| Works for Codex, Gemini CLI, OpenCode | yes | no | n/a | n/a |
| Per-client schema compatibility | yes, 6 sourced rules | no | no; 24 usability lint rules (descriptions, nesting) | no |
| Tests tool *behaviour* | no | no | yes (assertions, fuzzing) | no |
| Actual spend from past sessions | no | `/usage` | no | yes |

Use `/context` inside Claude Code, mcp-assert to test what your tools do, and
ccusage to see what you've already spent. upfront answers "what will each agent load, and what
breaks where" before you start.

## How it works

1. **Discover**: parse each harness's documented config files ([concepts](https://github.com/thanatchon36/upfront/blob/main/docs/concepts.md#where-upfront-looks)).
2. **Fetch**: with consent, start each distinct server once (from the project directory, like the agent) and page through `tools/list`.
3. **Count**: tokenize each tool's wire JSON with `o200k_base`; skill metadata and bodies separately; instruction files whole.
4. **Check**: run the per-client rules ([table](https://github.com/thanatchon36/upfront/blob/main/docs/api.md#compatibility-rules)).

More: [quickstart](https://github.com/thanatchon36/upfront/blob/main/docs/quickstart.md) · [concepts](https://github.com/thanatchon36/upfront/blob/main/docs/concepts.md) · [FAQ](https://github.com/thanatchon36/upfront/blob/main/docs/faq.md) · [API](https://github.com/thanatchon36/upfront/blob/main/docs/api.md) · [decisions](https://github.com/thanatchon36/upfront/blob/main/docs/decisions/)

## Limitations

- **Estimates.** One tokenizer for every model; vendors' counts differ, and clients add their own framing around tools ([ADR-0003](https://github.com/thanatchon36/upfront/blob/main/docs/decisions/ADR-0003-tokenizer.md)).
- **Not the vendor's system prompt.** Only what you add is measured.
- **Lazy loading isn't modelled.** Claude Code's tool search and OpenCode's lazy MCP loading defer some definitions; upfront reports their full cost.
- **No OAuth.** Remote servers that need a login show "auth required; not measured". Headers from your config are sent; OAuth flows are not run.
- **Root-level instruction files only**; Cursor currently contributes MCP server configurations only.
- **Codex's 2% skills budget** depends on the model's window; upfront checks the documented 8,000-character fallback.

## Roadmap

- **v0.2**: exact counts via vendor token-count APIs (opt-in), a `--fix` proxy that rewrites schemas per client, and Windsurf configs.
- **v0.3**: `upfront diff` between git refs for MCP server pull requests, and a GitHub Action.

## Contributing

Bug reports with a config that reproduces the problem help most. See
[CONTRIBUTING.md](https://github.com/thanatchon36/upfront/blob/main/CONTRIBUTING.md); compatibility rules need a public source.

## License

[MIT](https://github.com/thanatchon36/upfront/blob/main/LICENSE)
