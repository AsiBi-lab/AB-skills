#!/usr/bin/env python3
"""Stop hook for Claude Code — requires a plain, complete closing recap.

Fail-open by design: any error, and the session closes normally. Only judges
turns that changed files, blocks at most once per turn, and never while the
anti-loop flag is set.
"""

from __future__ import annotations

import json
import sys
from pathlib import Path
from typing import Any

sys.path.insert(0, str(Path(__file__).resolve().parent))

from hook_runtime import run  # noqa: E402
from transcript_common import EDIT_TOOLS, Turn, shell_changed_files  # noqa: E402


def _is_user_prompt(record: dict[str, Any]) -> bool:
    """A message the user actually typed — the start of a new turn.

    Tool results and injected notes (hook feedback, skill text) are recorded as
    "user" too, but they continue the current turn rather than start one.
    """
    if record.get("type") != "user" or record.get("isMeta") or record.get("isSidechain"):
        return False
    content = (record.get("message") or {}).get("content")
    if isinstance(content, str):
        return bool(content.strip())
    if isinstance(content, list):
        return any(isinstance(b, dict) and b.get("type") == "text" for b in content)
    return False


def read_transcript(path: Path) -> Turn:
    turn = Turn()
    with path.open("r", encoding="utf-8", errors="replace") as handle:
        for line in handle:
            try:
                record = json.loads(line)
            except Exception:
                continue
            if not isinstance(record, dict):
                continue
            if _is_user_prompt(record):
                turn = Turn(id=str(record.get("uuid") or ""))
                continue
            # Subagent output never reaches the user as the closing message.
            if record.get("type") != "assistant" or record.get("isSidechain"):
                continue

            content = (record.get("message") or {}).get("content")
            if not isinstance(content, list):
                continue

            texts: list[str] = []
            for block in content:
                if not isinstance(block, dict):
                    continue
                kind = block.get("type")
                payload = block.get("input") if isinstance(block.get("input"), dict) else {}
                if kind == "tool_use":
                    name = block.get("name")
                    if name in EDIT_TOOLS:
                        turn.changed_files.add(
                            str(payload.get("file_path") or payload.get("notebook_path") or name))
                    elif name == "Bash" and shell_changed_files(str(payload.get("command") or "")):
                        turn.shell_changes += 1
                elif kind == "text" and str(block.get("text", "")).strip():
                    texts.append(block["text"])
            if texts:
                turn.add_text("\n".join(texts))
    return turn


if __name__ == "__main__":
    raise SystemExit(run(read_transcript, "claude"))
