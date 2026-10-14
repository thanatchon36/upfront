"""Find the MCP servers, skills and instruction files each coding agent loads up front.

Config formats follow each harness's documentation:

- Claude Code: https://code.claude.com/docs/en/mcp (``.mcp.json``, ``~/.claude.json``)
- Codex: https://learn.chatgpt.com/docs/extend/mcp (``[mcp_servers.<name>]`` in
  ``.codex/config.toml`` and ``~/.codex/config.toml``); skills in ``.agents/skills``
- Gemini CLI: https://github.com/google-gemini/gemini-cli/blob/main/docs/tools/mcp-server.md
  (``mcpServers`` in ``.gemini/settings.json``; ``url`` is SSE, ``httpUrl`` is Streamable HTTP)
- OpenCode: https://opencode.ai/docs/mcp-servers (``mcp`` in ``opencode.json[c]``)
- Cursor: https://cursor.com/docs/mcp (``mcpServers`` in ``.cursor/mcp.json``)
"""

from __future__ import annotations

import json
import os
import re
import tomllib
from collections.abc import Iterable, Mapping
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Literal

Harness = Literal["claude-code", "codex", "gemini-cli", "opencode", "cursor"]
HARNESSES: tuple[Harness, ...] = ("claude-code", "codex", "gemini-cli", "opencode", "cursor")
Transport = Literal["stdio", "http", "sse"]
Scope = Literal["project", "local", "user"]


@dataclass
class ServerSpec:
    """One configured MCP server, as a given harness would start it."""

    harness: Harness
    name: str
    scope: Scope
    source: Path
    transport: Transport
    command: str | None = None
    args: list[str] = field(default_factory=list)
    env: dict[str, str] = field(default_factory=dict)
    cwd: str | None = None
    url: str | None = None
    headers: dict[str, str] = field(default_factory=dict)

    @property
    def target(self) -> str:
        """The command line or URL, as shown to the user before launching."""
        if self.transport == "stdio":
            return " ".join([self.command or "", *self.args]).strip()
        return self.url or ""


@dataclass
class Skill:
    name: str
    description: str
    body: str
    path: Path


@dataclass
class InstructionFile:
    path: Path
    text: str


@dataclass
class HarnessContext:
    harness: Harness
    servers: list[ServerSpec] = field(default_factory=list)
    skills: list[Skill] = field(default_factory=list)
    instructions: list[InstructionFile] = field(default_factory=list)
    errors: list[str] = field(default_factory=list)


@dataclass
class Discovery:
    root: Path
    harnesses: dict[Harness, HarnessContext]


# --------------------------------------------------------------------------- #
# Small parsers
# --------------------------------------------------------------------------- #

_VAR = re.compile(r"\$\{([A-Za-z_][A-Za-z0-9_]*)(?::-([^}]*))?\}")


def expand(value: str, env: Mapping[str, str]) -> str:
    """Claude Code's ``${VAR}`` / ``${VAR:-default}`` expansion; unknown vars stay literal."""

    def sub(m: re.Match[str]) -> str:
        name, default = m.group(1), m.group(2)
        if name in env:
            return env[name]
        return default if default is not None else m.group(0)

    return _VAR.sub(sub, value)


def strip_jsonc(text: str) -> str:
    """Remove // and /* */ comments and trailing commas outside of strings."""
    out: list[str] = []
    i, n, in_str = 0, len(text), False
    while i < n:
        c = text[i]
        if in_str:
            out.append(c)
            if c == "\\" and i + 1 < n:
                out.append(text[i + 1])
                i += 1
            elif c == '"':
                in_str = False
        elif c == '"':
            in_str = True
            out.append(c)
        elif text.startswith("//", i):
            while i < n and text[i] != "\n":
                i += 1
            continue
        elif text.startswith("/*", i):
            end = text.find("*/", i + 2)
            i = n if end == -1 else end + 2
            continue
        else:
            out.append(c)
        i += 1
    return re.sub(r",(\s*[}\]])", r"\1", "".join(out))


def _load(path: Path, ctx: HarnessContext, kind: Literal["json", "jsonc", "toml"]) -> Any:
    if not path.is_file():
        return None
    try:
        text = path.read_text(encoding="utf-8")
        if kind == "toml":
            return tomllib.loads(text)
        return json.loads(strip_jsonc(text) if kind == "jsonc" else text)
    except (OSError, ValueError) as e:
        ctx.errors.append(f"{path}: could not parse ({e})")
        return None


def _str_map(value: Any) -> dict[str, str]:
    return {str(k): str(v) for k, v in value.items()} if isinstance(value, dict) else {}


def _str_list(value: Any) -> list[str]:
    return [str(v) for v in value] if isinstance(value, list) else []


# --------------------------------------------------------------------------- #
# Per-harness readers
# --------------------------------------------------------------------------- #


def _claude_servers(
    ctx: HarnessContext, entries: Any, scope: Scope, source: Path, env: Mapping[str, str]
) -> None:
    if not isinstance(entries, dict):
        return
    for name, e in entries.items():
        if not isinstance(e, dict):
            continue
        kind = str(e.get("type", "stdio" if "command" in e else ""))

        def x(v: Any) -> str:
            return expand(str(v), env)

        if kind == "stdio" and "command" in e:
            ctx.servers.append(
                ServerSpec(
                    "claude-code",
                    name,
                    scope,
                    source,
                    "stdio",
                    command=x(e["command"]),
                    args=[x(a) for a in _str_list(e.get("args"))],
                    env={k: x(v) for k, v in _str_map(e.get("env")).items()},
                )
            )
        elif kind in ("http", "streamable-http", "sse") and "url" in e:
            ctx.servers.append(
                ServerSpec(
                    "claude-code",
                    name,
                    scope,
                    source,
                    "sse" if kind == "sse" else "http",
                    url=x(e["url"]),
                    headers={k: x(v) for k, v in _str_map(e.get("headers")).items()},
                )
            )
        else:
            ctx.errors.append(
                f'{source}: server \'{name}\' skipped: needs "command", or "type": '
                '"http"/"sse" with "url" (Claude Code skips it too)'
            )


def _claude(root: Path, home: Path, env: Mapping[str, str]) -> HarnessContext:
    ctx = HarnessContext("claude-code")
    project = _load(root / ".mcp.json", ctx, "json")
    if isinstance(project, dict):
        _claude_servers(ctx, project.get("mcpServers"), "project", root / ".mcp.json", env)
    user = _load(home / ".claude.json", ctx, "json")
    if isinstance(user, dict):
        src = home / ".claude.json"
        _claude_servers(ctx, user.get("mcpServers"), "user", src, env)
        projects = user.get("projects") or {}
        local = projects.get(str(root)) or projects.get(str(root.resolve()))
        if isinstance(local, dict):
            _claude_servers(ctx, local.get("mcpServers"), "local", src, env)
    # Claude Code reads AGENTS.md when the project has no CLAUDE.md.
    _instructions(
        ctx, [root / "CLAUDE.md"] if (root / "CLAUDE.md").is_file() else [root / "AGENTS.md"]
    )
    _instructions(ctx, [home / ".claude" / "CLAUDE.md"])
    _skills(ctx, [root / ".claude" / "skills", home / ".claude" / "skills"])
    return ctx


def _codex(root: Path, home: Path) -> HarnessContext:
    ctx = HarnessContext("codex")
    sources: list[tuple[Path, Scope]] = [
        (root / ".codex" / "config.toml", "project"),
        (home / ".codex" / "config.toml", "user"),
    ]
    for path, scope in sources:
        data = _load(path, ctx, "toml")
        servers = data.get("mcp_servers") if isinstance(data, dict) else None
        for name, e in (servers or {}).items():
            if not isinstance(e, dict) or e.get("enabled") is False:
                continue
            if "command" in e:
                ctx.servers.append(
                    ServerSpec(
                        "codex",
                        name,
                        scope,
                        path,
                        "stdio",
                        command=str(e["command"]),
                        args=_str_list(e.get("args")),
                        env=_str_map(e.get("env")),
                        cwd=str(e["cwd"]) if "cwd" in e else None,
                    )
                )
            elif "url" in e:
                ctx.servers.append(
                    ServerSpec("codex", name, scope, path, "http", url=str(e["url"]))
                )
    _instructions(ctx, [root / "AGENTS.md", home / ".codex" / "AGENTS.md"])
    _skills(ctx, [root / ".agents" / "skills", home / ".agents" / "skills"])
    return ctx


def _gemini(root: Path, home: Path) -> HarnessContext:
    ctx = HarnessContext("gemini-cli")
    sources: list[tuple[Path, Scope]] = [
        (root / ".gemini" / "settings.json", "project"),
        (home / ".gemini" / "settings.json", "user"),
    ]
    for path, scope in sources:
        data = _load(path, ctx, "json")
        servers = data.get("mcpServers") if isinstance(data, dict) else None
        for name, e in (servers or {}).items():
            if not isinstance(e, dict):
                continue
            headers = _str_map(e.get("headers"))
            if "command" in e:
                ctx.servers.append(
                    ServerSpec(
                        "gemini-cli",
                        name,
                        scope,
                        path,
                        "stdio",
                        command=str(e["command"]),
                        args=_str_list(e.get("args")),
                        env=_str_map(e.get("env")),
                        cwd=str(e["cwd"]) if "cwd" in e else None,
                    )
                )
            elif "httpUrl" in e:
                ctx.servers.append(
                    ServerSpec(
                        "gemini-cli",
                        name,
                        scope,
                        path,
                        "http",
                        url=str(e["httpUrl"]),
                        headers=headers,
                    )
                )
            elif "url" in e:
                ctx.servers.append(
                    ServerSpec(
                        "gemini-cli", name, scope, path, "sse", url=str(e["url"]), headers=headers
                    )
                )
    _instructions(ctx, [root / "GEMINI.md", home / ".gemini" / "GEMINI.md"])
    return ctx


def _opencode(root: Path, home: Path) -> HarnessContext:
    ctx = HarnessContext("opencode")
    user_dir = home / ".config" / "opencode"
    candidates: list[tuple[Path, Scope]] = [
        (root / "opencode.jsonc", "project"),
        (root / "opencode.json", "project"),
        (user_dir / "opencode.jsonc", "user"),
        (user_dir / "opencode.json", "user"),
    ]
    for path, scope in candidates:
        data = _load(path, ctx, "jsonc")
        servers = data.get("mcp") if isinstance(data, dict) else None
        for name, e in (servers or {}).items():
            if not isinstance(e, dict) or e.get("enabled") is False:
                continue
            if e.get("type") == "local":
                cmd = _str_list(e.get("command"))
                if cmd:
                    ctx.servers.append(
                        ServerSpec(
                            "opencode",
                            name,
                            scope,
                            path,
                            "stdio",
                            command=cmd[0],
                            args=cmd[1:],
                            env=_str_map(e.get("environment")),
                        )
                    )
            elif e.get("type") == "remote" and "url" in e:
                ctx.servers.append(
                    ServerSpec(
                        "opencode",
                        name,
                        scope,
                        path,
                        "http",
                        url=str(e["url"]),
                        headers=_str_map(e.get("headers")),
                    )
                )
    _instructions(ctx, [root / "AGENTS.md", user_dir / "AGENTS.md"])
    _skills(
        ctx,
        [
            root / ".opencode" / "skills",
            root / ".claude" / "skills",
            root / ".agents" / "skills",
            user_dir / "skills",
            home / ".claude" / "skills",
            home / ".agents" / "skills",
        ],
    )
    return ctx


def _cursor(root: Path, home: Path) -> HarnessContext:
    """Read Cursor's project and user ``mcp.json`` files (https://cursor.com/docs/mcp)."""
    ctx = HarnessContext("cursor")
    sources: list[tuple[Path, Scope]] = [
        (root / ".cursor" / "mcp.json", "project"),
        (home / ".cursor" / "mcp.json", "user"),
    ]
    for path, scope in sources:
        data = _load(path, ctx, "json")
        servers = data.get("mcpServers") if isinstance(data, dict) else None
        for name, entry in (servers or {}).items():
            if not isinstance(entry, dict):
                continue
            kind = str(
                entry.get(
                    "type",
                    "stdio" if "command" in entry else "http" if "url" in entry else "",
                )
            )
            if kind == "stdio" and "command" in entry:
                ctx.servers.append(
                    ServerSpec(
                        "cursor",
                        name,
                        scope,
                        path,
                        "stdio",
                        command=str(entry["command"]),
                        args=_str_list(entry.get("args")),
                        env=_str_map(entry.get("env")),
                    )
                )
            elif kind in ("http", "streamable-http", "sse") and "url" in entry:
                ctx.servers.append(
                    ServerSpec(
                        "cursor",
                        name,
                        scope,
                        path,
                        "sse" if kind == "sse" else "http",
                        url=str(entry["url"]),
                        headers=_str_map(entry.get("headers")),
                    )
                )
            else:
                ctx.errors.append(
                    f"{path}: server '{name}' skipped: needs \"command\" for stdio, "
                    'or "url" for an HTTP/SSE server'
                )
    return ctx


# --------------------------------------------------------------------------- #
# Skills and instruction files
# --------------------------------------------------------------------------- #

_FRONTMATTER = re.compile(r"\A---\s*\n(.*?)\n---\s*\n?", re.S)


def parse_skill(path: Path) -> Skill:
    text = path.read_text(encoding="utf-8")
    meta: dict[str, str] = {}
    body = text
    m = _FRONTMATTER.match(text)
    if m:
        body = text[m.end() :]
        for line in m.group(1).splitlines():
            key, sep, value = line.partition(":")
            if sep and not line.startswith((" ", "\t")):
                meta[key.strip()] = value.strip().strip("\"'")
    return Skill(meta.get("name", path.parent.name), meta.get("description", ""), body, path)


def _skills(ctx: HarnessContext, dirs: Iterable[Path]) -> None:
    seen = {s.name for s in ctx.skills}
    for d in dirs:
        for path in sorted(d.glob("*/SKILL.md")) if d.is_dir() else []:
            try:
                s = parse_skill(path)
            except (OSError, UnicodeDecodeError) as e:
                ctx.errors.append(f"{path}: could not read ({e})")
                continue
            if s.name not in seen:  # the first location wins, like the harnesses' precedence
                seen.add(s.name)
                ctx.skills.append(s)


def _instructions(ctx: HarnessContext, paths: Iterable[Path]) -> None:
    for p in paths:
        if p.is_file():
            try:
                ctx.instructions.append(InstructionFile(p, p.read_text(encoding="utf-8")))
            except (OSError, UnicodeDecodeError) as e:
                ctx.errors.append(f"{p}: could not read ({e})")


# --------------------------------------------------------------------------- #
# Entry point
# --------------------------------------------------------------------------- #


def discover(
    root: Path,
    *,
    home: Path | None = None,
    env: Mapping[str, str] | None = None,
    only: Iterable[str] | None = None,
) -> Discovery:
    """Read every supported config under ``root`` (project) and ``home`` (user scope)."""
    home = home or Path.home()
    env = dict(os.environ) if env is None else env
    wanted = [h for h in HARNESSES if only is None or h in set(only)]
    readers: dict[Harness, Any] = {
        "claude-code": lambda: _claude(root, home, env),
        "codex": lambda: _codex(root, home),
        "gemini-cli": lambda: _gemini(root, home),
        "opencode": lambda: _opencode(root, home),
        "cursor": lambda: _cursor(root, home),
    }
    found: dict[Harness, HarnessContext] = {h: readers[h]() for h in wanted}
    for ctx in found.values():
        for spec in ctx.servers:
            # Agents start stdio servers from the project directory; relative cwds are
            # resolved against it (Gemini CLI documents "cwd": "./server-directory").
            if spec.transport == "stdio":
                spec.cwd = str(root / spec.cwd) if spec.cwd else str(root)
    return Discovery(root, found)
