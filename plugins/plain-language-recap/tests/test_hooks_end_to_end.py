"""Both hooks, driven exactly as their host tool drives them: JSON on stdin."""

from __future__ import annotations

import json
import os
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from conftest_paths import CLAUDE_HOOK, CODEX_HOOK, ENGLISH_CONFIG  # noqa: E402
from test_recap_rules import GOOD_EN, GOOD_HE  # noqa: E402

LONG_TECHNICAL = "ביצעתי שינוי טכני מפורט בקוד. " * 35


class HookTestCase(unittest.TestCase):
    hook: Path = CLAUDE_HOOK

    def setUp(self) -> None:
        self.temp = tempfile.TemporaryDirectory()
        self.root = Path(self.temp.name)
        self.transcript = self.root / "session.jsonl"
        self.markers = self.root / "markers"

    def tearDown(self) -> None:
        self.temp.cleanup()

    def _run(self, session_id: str = "s1", config: Path | None = None, **extra):
        env = os.environ.copy()
        env["RECAP_MARKER_DIR"] = str(self.markers)
        if config:
            env["RECAP_CONFIG"] = str(config)
        event = {"session_id": session_id, "transcript_path": str(self.transcript), **extra}
        return subprocess.run([sys.executable, str(self.hook)], input=json.dumps(event),
                              text=True, capture_output=True, check=False, env=env)

    def _reason(self, out: str) -> str:
        self.assertTrue(out.strip(), "expected a block decision, got silence")
        payload = json.loads(out)
        self.assertEqual(payload["decision"], "block")
        return payload["reason"]


class ClaudeHookTests(HookTestCase):
    hook = CLAUDE_HOOK

    def _write(self, closing: str, work: str = "edit") -> None:
        records = []
        tool = {
            "edit": {"type": "tool_use", "name": "Edit", "input": {"file_path": "/srv/app.py"}},
            "shell-write": {"type": "tool_use", "name": "Bash",
                            "input": {"command": "cat > /srv/app.py <<'EOF'\nx\nEOF"}},
            "shell-read": {"type": "tool_use", "name": "Bash",
                           "input": {"command": "ls -la /srv 2>/dev/null | head -5"}},
        }.get(work)
        if tool:
            record = {"type": "assistant", "message": {"content": [tool]}}
            if work == "sidechain":
                record["isSidechain"] = True
            records.append(record)
        if work == "sidechain":
            records = [{"type": "assistant", "isSidechain": True, "message": {"content": [
                {"type": "tool_use", "name": "Edit", "input": {"file_path": "/srv/app.py"}}]}}]
        records.append({"type": "assistant", "message": {"content": [{"type": "text", "text": closing}]}})
        self.transcript.write_text(
            "\n".join(json.dumps(r, ensure_ascii=False) for r in records) + "\n", encoding="utf-8")

    def test_blocks_when_recap_missing(self) -> None:
        self._write(LONG_TECHNICAL)
        self.assertIn("no plain-language recap at all", self._reason(self._run().stdout))

    def test_allows_good_recap(self) -> None:
        self._write(LONG_TECHNICAL + "\n\n" + GOOD_HE)
        self.assertEqual(self._run("ok1").stdout, "")

    def test_detects_edits_made_through_the_shell(self) -> None:
        self._write(LONG_TECHNICAL, work="shell-write")
        self.assertIn("no plain-language recap", self._reason(self._run("s2").stdout))

    def test_ignores_read_only_shell_commands(self) -> None:
        self._write(LONG_TECHNICAL, work="shell-read")
        self.assertEqual(self._run("s3").stdout, "")

    def test_ignores_subagent_edits(self) -> None:
        self._write(LONG_TECHNICAL, work="sidechain")
        self.assertEqual(self._run("s4").stdout, "")

    def test_allows_trivial_acknowledgement(self) -> None:
        self._write("הושלם.")
        self.assertEqual(self._run("s5").stdout, "")

    def _records(self, records: list[dict]) -> None:
        self.transcript.write_text(
            "\n".join(json.dumps(r, ensure_ascii=False) for r in records) + "\n", encoding="utf-8")

    @staticmethod
    def _user(text: str, uuid: str, meta: bool = False) -> dict:
        record = {"type": "user", "uuid": uuid, "message": {"role": "user", "content": text}}
        if meta:
            record["isMeta"] = True
        return record

    @staticmethod
    def _tool(name: str, **payload) -> dict:
        return {"type": "assistant", "message": {"content": [
            {"type": "tool_use", "name": name, "input": payload}]}}

    @staticmethod
    def _say(text: str) -> dict:
        return {"type": "assistant", "message": {"content": [{"type": "text", "text": text}]}}

    def test_blocks_once_per_turn(self) -> None:
        edit = self._tool("Edit", file_path="/srv/app.py")
        self._records([self._user("תתקן", "u1"), edit, self._say(LONG_TECHNICAL)])
        self.assertIn("block", self._run("once").stdout)
        self.assertEqual(self._run("once").stdout, "")
        self._records([self._user("תתקן", "u1"), edit, self._say(LONG_TECHNICAL),
                       self._user("עוד תיקון", "u2"), edit, self._say(LONG_TECHNICAL)])
        self.assertIn("block", self._run("once").stdout)

    def test_edits_from_an_earlier_turn_do_not_count(self) -> None:
        self._records([self._user("תתקן", "u1"), self._tool("Edit", file_path="/srv/app.py"),
                       self._say(LONG_TECHNICAL + "\n\n" + GOOD_HE),
                       self._user("ומה דעתך?", "u2"), self._say(LONG_TECHNICAL)])
        self.assertEqual(self._run("t1").stdout, "")

    def test_hook_feedback_continues_the_turn(self) -> None:
        self._records([self._user("תתקן", "u1"), self._tool("Edit", file_path="/srv/app.py"),
                       self._say(LONG_TECHNICAL), self._user("Stop hook feedback", "fb", meta=True),
                       self._say(LONG_TECHNICAL)])
        self.assertIn("block", self._run("t2").stdout)

    def test_script_text_in_a_heredoc_is_not_a_change(self) -> None:
        script = ("python3 - <<'EOF'\nfor d in rows:\n"
                  "    if d['ts'] > \"2026\" and 'cp ' in d['cmd']:\n        print(d)\nEOF")
        self._records([self._user("תחפש", "u1"), self._tool("Bash", command=script),
                       self._say(LONG_TECHNICAL)])
        self.assertEqual(self._run("h1").stdout, "")

    def test_script_that_writes_a_file_is_a_change(self) -> None:
        script = "python3 - <<'EOF'\nopen('/srv/out.txt', 'w').write('hi')\nEOF"
        self._records([self._user("תכתוב", "u1"), self._tool("Bash", command=script),
                       self._say(LONG_TECHNICAL)])
        self.assertIn("block", self._run("h2").stdout)

    def test_dropped_test_numbers_block_end_to_end(self) -> None:
        self._records([self._user("תתקן", "u1"), self._tool("Edit", file_path="/srv/app.py"),
                       self._say("הרצתי את כל הבדיקות: 42/42 עברו."),
                       self._say(LONG_TECHNICAL + "\n\n" + GOOD_HE)])
        self.assertIn("42", self._reason(self._run("n1").stdout))

    def test_respects_stop_hook_active(self) -> None:
        self._write(LONG_TECHNICAL)
        self.assertEqual(self._run("s6", stop_hook_active=True).stdout, "")

    def test_user_config_overrides_the_shipped_default(self) -> None:
        self._write(LONG_TECHNICAL + "\n\n" + GOOD_EN)
        self.assertIn("no plain-language recap", self._reason(self._run("s7").stdout))
        self.assertEqual(self._run("s8", config=ENGLISH_CONFIG).stdout, "")

    def test_fails_open_on_bad_input(self) -> None:
        env = os.environ.copy()
        env["RECAP_MARKER_DIR"] = str(self.markers)
        for payload in ("not-json", "", "[]", '{"session_id":"../../etc","transcript_path":"/nope"}'):
            result = subprocess.run([sys.executable, str(self.hook)], input=payload,
                                    text=True, capture_output=True, check=False, env=env)
            self.assertEqual(result.returncode, 0, payload)
            self.assertEqual(result.stdout, "", payload)

    def test_fails_open_on_broken_user_config(self) -> None:
        broken = self.root / "broken.json"
        broken.write_text("{ not json", encoding="utf-8")
        self._write(LONG_TECHNICAL)
        # A broken override must fall through to the shipped config, not disable the hook.
        self.assertIn("block", self._run("s9", config=broken).stdout)


class CodexHookTests(HookTestCase):
    hook = CODEX_HOOK

    def _write(self, closing: str, command: str | None = None) -> None:
        records = []
        if command:
            records.append({"type": "response_item",
                            "payload": {"type": "custom_tool_call", "name": "exec", "input": command}})
        records.append({"type": "event_msg",
                        "payload": {"type": "agent_message", "phase": "final", "message": closing}})
        self.transcript.write_text(
            "\n".join(json.dumps(r, ensure_ascii=False) for r in records) + "\n", encoding="utf-8")

    def test_blocks_when_recap_missing(self) -> None:
        self._write(LONG_TECHNICAL, "await tools.apply_patch('*** Begin Patch')")
        self.assertIn("no plain-language recap at all", self._reason(self._run("c1").stdout))

    def test_detects_shell_writes(self) -> None:
        self._write(LONG_TECHNICAL, "cat > /srv/app.py <<'EOF'\nx = 1\nEOF")
        self.assertIn("no plain-language recap", self._reason(self._run("c2").stdout))

    def test_ignores_read_only_commands(self) -> None:
        self._write(LONG_TECHNICAL, "ls -la /srv 2>/dev/null | head -5")
        self.assertEqual(self._run("c3").stdout, "")

    def test_allows_good_recap(self) -> None:
        self._write(LONG_TECHNICAL + "\n\n" + GOOD_HE, "await tools.apply_patch('*** Begin Patch')")
        self.assertEqual(self._run("c4").stdout, "")

    def test_read_only_session_is_ignored(self) -> None:
        self._write(LONG_TECHNICAL)
        self.assertEqual(self._run("c5").stdout, "")

    @staticmethod
    def _exec_command(command: str) -> dict:
        code = "const r = await tools.exec_command(" + json.dumps({"cmd": command}) + ")"
        return {"type": "response_item", "payload": {"type": "custom_tool_call", "name": "exec",
                                                     "input": code}}

    @staticmethod
    def _started(turn_id: str) -> dict:
        return {"type": "event_msg", "payload": {"type": "task_started", "turn_id": turn_id}}

    @staticmethod
    def _final(text: str) -> dict:
        return {"type": "response_item", "payload": {
            "type": "message", "role": "assistant", "phase": "final",
            "content": [{"type": "output_text", "text": text}]}}

    def _records(self, records: list[dict]) -> None:
        self.transcript.write_text(
            "\n".join(json.dumps(r, ensure_ascii=False) for r in records) + "\n", encoding="utf-8")

    def test_detects_writes_inside_exec_command(self) -> None:
        self._records([self._started("t1"),
                       self._exec_command("cat > /srv/app.py <<'EOF'\nx = 1\nEOF"),
                       self._final(LONG_TECHNICAL)])
        self.assertIn("block", self._run("c6").stdout)

    def test_read_only_exec_command_is_ignored(self) -> None:
        self._records([self._started("t1"), self._exec_command("ls -la /srv 2>/dev/null | head"),
                       self._final(LONG_TECHNICAL)])
        self.assertEqual(self._run("c7").stdout, "")

    def test_changes_from_an_earlier_turn_do_not_count(self) -> None:
        patch = {"type": "response_item", "payload": {
            "type": "custom_tool_call", "name": "exec",
            "input": "await tools.apply_patch('*** Begin Patch')"}}
        self._records([self._started("t1"), patch, self._final(LONG_TECHNICAL + "\n\n" + GOOD_HE),
                       self._started("t2"), self._final(LONG_TECHNICAL)])
        self.assertEqual(self._run("c8").stdout, "")


class ParityTests(HookTestCase):
    """Both hooks, fed the same turn in their own log format, give the same verdict."""

    def _verdict(self, hook: Path, records: list[dict], session: str) -> str:
        self.hook = hook
        self.transcript.write_text(
            "\n".join(json.dumps(r, ensure_ascii=False) for r in records) + "\n", encoding="utf-8")
        return self._run(session).stdout

    def test_same_verdicts(self) -> None:
        samples = [LONG_TECHNICAL, LONG_TECHNICAL + "\n\n" + GOOD_HE,
                   LONG_TECHNICAL + "\n\n" + GOOD_HE.replace("**מה להחליט**", "מה להחליט")]
        for index, closing in enumerate(samples):
            claude = self._verdict(CLAUDE_HOOK, [
                {"type": "assistant", "message": {"content": [
                    {"type": "tool_use", "name": "Edit", "input": {"file_path": "/srv/app.py"}}]}},
                {"type": "assistant", "message": {"content": [{"type": "text", "text": closing}]}},
            ], f"p-claude-{index}")
            codex = self._verdict(CODEX_HOOK, [
                {"type": "response_item", "payload": {
                    "type": "custom_tool_call", "name": "exec",
                    "input": "await tools.apply_patch('*** Begin Patch')"}},
                {"type": "response_item", "payload": {
                    "type": "message", "role": "assistant", "phase": "final",
                    "content": [{"type": "output_text", "text": closing}]}},
            ], f"p-codex-{index}")
            self.assertEqual(claude, codex, closing[-60:])


if __name__ == "__main__":
    unittest.main()
