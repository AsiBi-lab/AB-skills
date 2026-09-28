"""Shared Stop-hook plumbing: safety gates, once-per-turn marker, output."""

from __future__ import annotations

import json
import os
import re
import sys
from pathlib import Path
from typing import Any, Callable

from recap_quality import RecapRules, load_rules
from transcript_common import Turn

SESSION_ID_RE = re.compile(r"^[A-Za-z0-9._-]{1,128}$")
TURN_ID_RE = re.compile(r"[^A-Za-z0-9-]")


def _marker_dir(tool: str) -> Path:
    override = os.environ.get("RECAP_MARKER_DIR")
    if override:
        return Path(override).expanduser()
    return Path.home() / f".{tool}" / "status" / "plain-language"


def evaluate(
    event: dict[str, Any],
    rules: RecapRules,
    read_transcript: Callable[[Path], Turn],
    tool: str,
) -> str | None:
    """Return a block reason, or None to stay silent."""
    if bool(event.get("stop_hook_active", False)):
        return None

    transcript_value = event.get("transcript_path")
    session_id = event.get("session_id")
    if not isinstance(transcript_value, str) or not transcript_value:
        return None
    if not isinstance(session_id, str) or not SESSION_ID_RE.fullmatch(session_id):
        return None

    transcript = Path(transcript_value).expanduser()
    if not transcript.is_file() or transcript.suffix != ".jsonl":
        return None

    turn = read_transcript(transcript)
    if not turn.changed_count:
        return None

    marker_root = _marker_dir(tool)
    turn_id = TURN_ID_RE.sub("", turn.id)[:64]
    marker = marker_root / (f"{session_id}.{turn_id}" if turn_id else session_id)
    if marker.is_file():
        return None

    section = rules.section(turn.last_text)
    if not section:
        # A one-line acknowledgement is not a summary worth gating.
        if len(turn.last_text) < rules.trivial_closing_chars:
            return None
        problems = [rules.missing_recap]
    else:
        everything = "\n".join(turn.texts)
        body = everything[:everything.rfind(section)] if section in everything else everything
        problems = rules.diagnose(section, body, turn.changed_count)
        if not problems:
            return None

    marker_root.mkdir(parents=True, exist_ok=True, mode=0o700)
    marker.touch(exist_ok=True, mode=0o600)
    return rules.reason(problems)


def run(read_transcript: Callable[[Path], Turn], tool: str) -> int:
    try:
        rules = load_rules(Path(__file__).resolve().parents[1])
        event = json.load(sys.stdin)
        if not isinstance(event, dict):
            return 0
        reason = evaluate(event, rules, read_transcript, tool)
        if reason is None:
            return 0
        print(json.dumps({"decision": "block", "reason": reason}, ensure_ascii=False))
        return 0
    except Exception:
        # A closing-quality helper must never become a session blocker.
        return 0
