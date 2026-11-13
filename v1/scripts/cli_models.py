"""One structured inference call through Codex CLI or Claude Code CLI.

Uses the CLI's normal login. No HTTP proxy, API key handling, or retry loop.
"""

from __future__ import annotations

import hashlib
import json
import os
from pathlib import Path
import shutil
import subprocess
import tempfile
import time


def executable(backend: str) -> str:
    """Find the CLI even when a notebook kernel has a different PATH."""
    if backend not in ("codex", "claude-cli"):
        raise ValueError(f"Unknown CLI backend: {backend}")
    name = "claude" if backend == "claude-cli" else "codex"
    override = os.environ.get(f"{name.upper()}_BIN")
    if override:
        path = shutil.which(str(Path(override).expanduser()))
        if not path:
            raise RuntimeError(f"{name.upper()}_BIN is not an executable: {override}")
        return path
    path = shutil.which(name)
    if path:
        return path
    if backend == "codex":
        # The macOS desktop app can include Codex without adding it to PATH.
        for applications in (Path("/Applications"), Path.home() / "Applications"):
            bundled = applications / "ChatGPT.app/Contents/Resources/codex-cli/CodexCLI.app/Contents/MacOS/codex"
            if bundled.is_file() and os.access(bundled, os.X_OK):
                return str(bundled)
    raise RuntimeError(f"{name} CLI not found. Install it and sign in, or set "
                       f"{name.upper()}_BIN in the notebook setup cell to its executable path.")


def usage_from_events(stdout: str) -> dict:
    usage = {}
    for line in stdout.splitlines():
        try:
            event = json.loads(line)
        except json.JSONDecodeError:
            continue
        if isinstance(event, dict) and isinstance(event.get("usage"), dict):
            usage = event["usage"]
    return usage


def call_cli(prompt: str, run_dir: Path, schema: dict, backend: str,
             model: str | None = None, effort: str | None = None, timeout: int = 600,
             instructions_len: int = 0) -> dict:
    """Save prompt/schema/raw logs and return the same result shape as the API backend.

    claude-cli runs `claude -p` under the student's own Claude subscription, with no
    MCP servers, no settings files and no CLAUDE.md, so each call carries only the
    prompt (about 1k tokens of overhead instead of 300k). With instructions_len, the
    prompt's first instructions_len characters (the same for every company) go in the
    system prompt, so the CLI's prompt cache covers them across calls, as the API
    backend does."""
    if backend not in ("codex", "claude-cli"):
        raise ValueError(f"Unknown CLI backend: {backend}")
    run_dir = Path(run_dir).resolve()
    run_dir.mkdir(parents=True, exist_ok=True)
    system_file = None
    if backend == "claude-cli" and instructions_len:
        # The instructions (system prompt) are the same for every call of a run, so they are kept once, beside
        # the per-call folders (<out>/runs/system_<hash>.txt); each call keeps only its own part (prompt_user.txt).
        # direct_llm's system prompt is the whole pool (about 400 KB), so this matters there.
        system = prompt[:instructions_len]
        digest = hashlib.sha256(system.encode("utf-8")).hexdigest()[:8]   # a run can use several (fill_facets: with/without pages)
        system_file = run_dir.parent.parent / f"system_{digest}.txt"
        if not system_file.exists():
            tmp = system_file.with_name(f".system.{os.getpid()}.{run_dir.name}.tmp")
            tmp.write_text(system, encoding="utf-8")
            os.replace(tmp, system_file)
        (run_dir / "prompt_user.txt").write_text(prompt[instructions_len:].lstrip(), encoding="utf-8")
    else:
        (run_dir / "prompt.txt").write_text(prompt, encoding="utf-8")
    schema_path, response_path = run_dir / "schema.json", run_dir / "response.json"
    schema_path.write_text(json.dumps(schema), encoding="utf-8")
    started = time.monotonic()
    with tempfile.TemporaryDirectory(prefix="qual2cast_inference_") as workdir:
        if backend == "codex":
            command = [executable(backend), "exec", "--skip-git-repo-check", "--ephemeral",
                       "--sandbox", "read-only", "--cd", workdir, "-c", 'web_search="disabled"',
                       "--output-schema", str(schema_path), "--output-last-message", str(response_path), "--json"]
            if model:
                command += ["--model", model]
            if effort:
                command += ["-c", f'model_reasoning_effort="{effort}"']
            command.append("-")
        else:
            command = [executable(backend), "-p", "--output-format", "json",
                       "--json-schema", json.dumps(schema), "--tools", "", "--no-session-persistence",
                       "--strict-mcp-config", "--mcp-config", '{"mcpServers":{}}',
                       "--setting-sources", "", "--max-turns", "3"]
            if system_file:
                command += ["--system-prompt-file", str(system_file)]
            if model:
                command += ["--model", model]
            if effort:
                command += ["--effort", effort]
        stdin = prompt[instructions_len:].lstrip() if (backend == "claude-cli" and instructions_len) else prompt
        # a `claude -p` started from inside a Claude Code session must not look nested
        env = {k: v for k, v in os.environ.items() if k not in ("CLAUDECODE", "CLAUDE_CODE_ENTRYPOINT")}
        try:
            proc = subprocess.run(command, input=stdin, capture_output=True, text=True,
                                  encoding="utf-8", cwd=workdir, timeout=timeout, env=env)
        except subprocess.TimeoutExpired as exc:
            # TimeoutExpired may contain bytes even with text=True.
            for name, value in (("stdout.txt", exc.stdout), ("stderr.txt", exc.stderr)):
                (run_dir / name).write_text(value.decode("utf-8", errors="replace")
                                            if isinstance(value, bytes) else value or "", encoding="utf-8")
            return {"llm_status": "timeout", "stop_run": False, "command": command,
                    "seconds": round(time.monotonic() - started, 2)}
    (run_dir / "stdout.txt").write_text(proc.stdout or "", encoding="utf-8")
    (run_dir / "stderr.txt").write_text(proc.stderr or "", encoding="utf-8")
    if backend == "codex":
        (run_dir / "events.jsonl").write_text(proc.stdout or "", encoding="utf-8")
    meta = {"backend": backend, "command": command, "returncode": proc.returncode,
            "seconds": round(time.monotonic() - started, 2), "usage": {}}
    try:
        if backend == "claude-cli":
            try:
                envelope = json.loads(proc.stdout)
            except json.JSONDecodeError:
                envelope = None
            if not isinstance(envelope, dict):
                raise ValueError((proc.stderr or proc.stdout or f"Exit code {proc.returncode}")[-2000:])
            if envelope.get("is_error") or envelope.get("subtype", "success") != "success":
                raise ValueError(str(envelope.get("errors") or envelope.get("result") or envelope.get("subtype")))
        elif proc.returncode:
            raise ValueError((proc.stderr or proc.stdout or f"Exit code {proc.returncode}")[-2000:])
        if backend == "claude-cli":
            answer = envelope.get("structured_output")
            if answer is None:
                answer = json.loads(envelope.get("result", ""))
            text = json.dumps(answer, ensure_ascii=False)
            meta["usage"] = envelope.get("usage", {})
        else:
            meta["usage"] = usage_from_events(proc.stdout)
            text = response_path.read_text(encoding="utf-8")
            json.loads(text)
        response_path.write_text(text, encoding="utf-8")
    except (ValueError, OSError) as exc:
        error = str(exc)
        # stop the whole run only when the next call would fail the same way
        fatal = any(s in error.lower() for s in ("usage limit", "rate limit", "not logged in", "/login",
                                                  "credit balance", "quota", "cli not found"))
        return {"llm_status": "cli_error", "error": error, "stop_run": fatal, **meta}
    return {"llm_status": "ok", "text": text, **meta}
