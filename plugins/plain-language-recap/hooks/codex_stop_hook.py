#!/usr/bin/env python3
"""Stop hook for Codex — same rules as the Claude hook, different transcript format."""

from __future__ import annotations

import json
import re
import sys
from pathlib import Path
from typing import Any

sys.path.insert(0, str(Path(__file__).resolve().parent))

from hook_runtime import run  # noqa: E402
from transcript_common import EDIT_TOOLS, Turn, shell_changed_files  # noqa: E402

_APPLY_PATCH_RE = re.compile(r"tools\.apply_patch\s*\(")
_SHELL_TOOLS = {"exec", "functions.exec", "shell", "local_shell", "exec_command"}
_CMD_RE = re.compile(r"""["']?\b(?:cmd|command)["']?\s*:\s*("(?:[^"\\]|\\.)*")""")


def _text_from_content(content: Any) -> str:
    if not isinstance(content, list):
        return ""
    return "\n".join(
        block["text"] for block in content
        if isinstance(block, dict) and block.get("type") in {"output_text", "text"}
        and isinstance(block.get("text"), str) and block["text"].strip()
    )


def _shell_commands(raw_input: str) -> list[str]:
    """The shell commands inside one Codex tool call.

    Codex Desktop records nested calls as JavaScript, e.g.
    `await tools.exec_command({"cmd": "cat > x <<'EOF' ..."})`; plain shell
    calls carry JSON arguments. Either way the command sits in a quoted string,
    so it is decoded before being judged — otherwise the whole command would
    look like quoted text and a real write would slip past.
    """
    try:
        parsed = json.loads(raw_input)
    except Exception:
        parsed = None
    if isinstance(parsed, dict):
        command = parsed.get("cmd", parsed.get("command"))
        if isinstance(command, list):
            return [" ".join(str(part) for part in command)]
        if isinstance(command, str):
            return [command]
    commands = []
    for literal in _CMD_RE.findall(raw_input):
        try:
            commands.append(json.loads(literal))
        except Exception:
            continue
    # Older logs store the bare command as the whole input.
    return commands or ([raw_input] if not _CMD_RE.search(raw_input) else [])


def _call_changed_files(payload: dict[str, Any]) -> bool:
    if payload.get("type") not in {"custom_tool_call", "function_call"}:
        return False
    name = str(payload.get("name") or "")
    if name in EDIT_TOOLS:
        return True
    if name not in _SHELL_TOOLS:
        return False
    raw_input = payload.get("input", payload.get("arguments", ""))
    if not isinstance(raw_input, str):
        try:
            raw_input = json.dumps(raw_input, ensure_ascii=False)
        except Exception:
            raw_input = ""
    if _APPLY_PATCH_RE.search(raw_input):
        return True
    return any(shell_changed_files(command) for command in _shell_commands(raw_input))


def read_transcript(path: Path) -> Turn:
    """A Codex turn starts with a `task_started` event.

    Assistant text is taken from the response items (the event stream repeats
    it); the final-phase message is the closing one when Codex marks it.
    """
    turn, events, final_text = Turn(), [], ""
    with path.open("r", encoding="utf-8", errors="replace") as handle:
        for line in handle:
            try:
                record = json.loads(line)
            except Exception:
                continue
            if not isinstance(record, dict):
                continue
            payload = record.get("payload")
            if not isinstance(payload, dict):
                continue
            record_type = record.get("type")

            if record_type == "event_msg" and payload.get("type") == "task_started":
                turn, events, final_text = Turn(id=str(payload.get("turn_id") or "")), [], ""
            elif record_type == "response_item":
                if _call_changed_files(payload):
                    turn.shell_changes += 1
                if payload.get("type") == "message" and payload.get("role") == "assistant":
                    text = _text_from_content(payload.get("content"))
                    if text:
                        turn.add_text(text)
                        if payload.get("phase") == "final":
                            final_text = text
            elif record_type == "event_msg" and payload.get("type") == "agent_message":
                text = payload.get("message")
                if isinstance(text, str) and text.strip():
                    events.append(text)
                    if payload.get("phase") == "final":
                        final_text = text

    if not turn.texts:
        turn.texts = events
        turn.last_text = events[-1] if events else ""
    turn.last_text = final_text or turn.last_text
    return turn


if __name__ == "__main__":
    raise SystemExit(run(read_transcript, "codex"))
