"""One structured inference call through Codex CLI or Claude Code CLI.

Uses the CLI's normal login. No HTTP proxy, API key handling, or retry loop.
"""

from __future__ import annotations

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
             model: str | None = None, effort: str | None = None, timeout: int = 600) -> dict:
    """Save prompt/schema/raw logs and return the same result shape as the API backend."""
    if backend not in ("codex", "claude-cli"):
        raise ValueError(f"Unknown CLI backend: {backend}")
    run_dir = Path(run_dir).resolve()
    run_dir.mkdir(parents=True, exist_ok=True)
    (run_dir / "prompt.txt").write_text(prompt, encoding="utf-8")
    schema_path, response_path = run_dir / "schema.json", run_dir / "response.json"
    schema_path.write_text(json.dumps(schema), encoding="utf-8")
    started = time.monotonic()
    with tempfile.TemporaryDirectory(prefix="qual2cast_inference_") as workdir:
        if backend == "codex":
            command = [executable(backend), "exec", "--skip-git-repo-check", "--ephemeral",
                       "--sandbox", "read-only", "--cd", workdir,
                       "--output-schema", str(schema_path), "--output-last-message", str(response_path), "--json"]
            if model:
                command += ["--model", model]
            if effort:
                command += ["-c", f'model_reasoning_effort="{effort}"']
            command.append("-")
        else:
            command = [executable(backend), "-p", "--output-format", "json",
                       "--json-schema", json.dumps(schema), "--tools", "", "--no-session-persistence"]
            if model:
                command += ["--model", model]
            if effort:
                command += ["--effort", effort]
        try:
            proc = subprocess.run(command, input=prompt, capture_output=True, text=True,
                                  encoding="utf-8", cwd=workdir, timeout=timeout)
        except subprocess.TimeoutExpired as exc:
            # TimeoutExpired may contain bytes even with text=True.
            for name, value in (("stdout.txt", exc.stdout), ("stderr.txt", exc.stderr)):
                (run_dir / name).write_text(value.decode("utf-8", errors="replace")
                                            if isinstance(value, bytes) else value or "", encoding="utf-8")
            return {"llm_status": "timeout", "stop_run": True, "command": command,
                    "seconds": round(time.monotonic() - started, 2)}
    (run_dir / "stdout.txt").write_text(proc.stdout or "", encoding="utf-8")
    (run_dir / "stderr.txt").write_text(proc.stderr or "", encoding="utf-8")
    if backend == "codex":
        (run_dir / "events.jsonl").write_text(proc.stdout or "", encoding="utf-8")
    meta = {"backend": backend, "command": command, "returncode": proc.returncode,
            "seconds": round(time.monotonic() - started, 2), "usage": {}}
    try:
        if proc.returncode:
            raise ValueError((proc.stderr or proc.stdout or f"Exit code {proc.returncode}")[-2000:])
        if backend == "claude-cli":
            envelope = json.loads(proc.stdout)
            if envelope.get("is_error") or envelope.get("subtype", "success") != "success":
                raise ValueError(str(envelope.get("errors") or envelope.get("result") or envelope))
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
        return {"llm_status": "cli_error", "error": str(exc), "stop_run": True, **meta}
    return {"llm_status": "ok", "text": text, **meta}
