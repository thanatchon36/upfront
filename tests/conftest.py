"""Shared fixtures: a fake project + home directory with every supported config format."""

from __future__ import annotations

import json
import sys
from pathlib import Path

import pytest

REPO = Path(__file__).resolve().parent.parent
REPLAY = REPO / "examples" / "servers" / "replay_server.py"


def write(path: Path, text: str) -> Path:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text)
    return path


def skill(root: Path, name: str, description: str, body: str = "Do the thing.\n") -> Path:
    return write(
        root / name / "SKILL.md",
        f"---\nname: {name}\ndescription: {description}\n---\n\n{body}",
    )


@pytest.fixture
def tools_file(tmp_path: Path) -> Path:
    tools = [
        {
            "name": f"tool_{i}",
            "description": f"Tool number {i}. " * 5,
            "inputSchema": {"type": "object", "properties": {"q": {"type": "string"}}},
        }
        for i in range(5)
    ]
    return write(tmp_path / "tools.json", json.dumps({"tools": tools}))


@pytest.fixture
def workspace(tmp_path: Path, tools_file: Path) -> tuple[Path, Path]:
    """A project dir and a home dir configured for all five harnesses."""
    root, home = tmp_path / "project", tmp_path / "home"
    py = sys.executable
    stdio = {"command": py, "args": [str(REPLAY), str(tools_file)]}
    posix_py = py.replace("\\", "/")
    posix_replay = str(REPLAY).replace("\\", "/")
    posix_tools_file = str(tools_file).replace("\\", "/")

    # Claude Code: project .mcp.json, user + local scope in ~/.claude.json
    write(
        root / ".mcp.json",
        json.dumps(
            {
                "mcpServers": {
                    "replay": stdio,
                    "remote": {"type": "http", "url": "${API_BASE:-http://127.0.0.1:9}/mcp"},
                    "broken": {"url": "http://example.invalid/mcp"},
                }
            }
        ),
    )
    write(
        home / ".claude.json",
        json.dumps(
            {
                "mcpServers": {"user-wide": stdio},
                "projects": {str(root): {"mcpServers": {"local-only": stdio}}},
            }
        ),
    )
    write(root / "CLAUDE.md", "# Project rules\nUse uv.\n")
    skill(root / ".claude" / "skills", "deploy", "Deploy the app to staging.")
    skill(home / ".claude" / "skills", "review", "Review a pull request.")

    # Codex: TOML in project and user config, AGENTS.md, .agents/skills
    write(
        root / ".codex" / "config.toml",
        f'[mcp_servers.replay]\ncommand = "{posix_py}"\n'
        f'args = ["{posix_replay}", "{posix_tools_file}"]\n'
        '[mcp_servers.figma]\nurl = "https://mcp.figma.com/mcp"\n',
    )
    write(
        home / ".codex" / "config.toml", "[mcp_servers.disabled]\ncommand = 'x'\nenabled = false\n"
    )
    write(root / "AGENTS.md", "# Agents\nRun tests with pytest.\n")
    skill(root / ".agents" / "skills", "release", "Cut a release.")

    # Gemini CLI: settings.json with stdio, SSE (url) and HTTP (httpUrl)
    write(
        root / ".gemini" / "settings.json",
        json.dumps(
            {
                "mcpServers": {
                    "replay": {**stdio, "cwd": str(root)},
                    "legacy-sse": {"url": "http://127.0.0.1:9/sse"},
                    "streaming": {"httpUrl": "http://127.0.0.1:9/mcp", "headers": {"X-Key": "k"}},
                }
            }
        ),
    )
    write(home / ".gemini" / "GEMINI.md", "Prefer short answers.\n")

    # OpenCode: JSONC with comments and trailing commas
    write(
        root / "opencode.jsonc",
        "{\n  // local server\n"
        f'  "mcp": {{\n    "replay": {{"type": "local", "command": ["{posix_py}", '
        f'"{posix_replay}", "{posix_tools_file}"], "environment": {{"A": "1"}}}},\n'
        '    "jira": {"type": "remote", "url": "https://jira.example.com/mcp",'
        ' "enabled": false,},\n'
        "  },\n}\n",
    )
    skill(root / ".opencode" / "skills", "triage", "Triage new issues.")

    # Cursor: project and user mcp.json files with stdio and remote servers.
    write(
        root / ".cursor" / "mcp.json",
        json.dumps(
            {
                "mcpServers": {
                    "cursor-local": {"type": "stdio", **stdio},
                    "cursor-remote": {
                        "url": "https://cursor.example.com/mcp",
                        "headers": {"X-Key": "cursor"},
                    },
                }
            }
        ),
    )
    write(
        home / ".cursor" / "mcp.json",
        json.dumps({"mcpServers": {"cursor-user": {"command": py, "args": ["--user"]}}}),
    )
    return root, home
