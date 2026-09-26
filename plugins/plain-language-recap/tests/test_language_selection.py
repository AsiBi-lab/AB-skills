"""Choosing a language must be a real, working path — not a copy-paste exercise."""

from __future__ import annotations

import json
import os
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from conftest_paths import (  # noqa: E402
    CLAUDE_HOOK, CODEX_HOOK, CONFIGS_DIR, HOOKS_DIR, PLUGIN_ROOT,
    USE_LANGUAGE_SCRIPT, load_module,
)
from test_recap_rules import GOOD_EN, GOOD_HE  # noqa: E402

quality = load_module("recap_quality_langsel", HOOKS_DIR / "recap_quality.py")
LONG_TECHNICAL = "I made a detailed technical change in the code. " * 25


class BundledConfigTests(unittest.TestCase):
    def test_every_bundled_config_is_valid_and_loadable(self) -> None:
        bundled = quality.bundled_configs(PLUGIN_ROOT)
        self.assertIn("hebrew", bundled)
        self.assertIn("english", bundled)
        for name, path in bundled.items():
            with self.subTest(language=name):
                rules = quality.RecapRules(json.loads(path.read_text(encoding="utf-8")))
                self.assertEqual(len(rules.beats), 4, f"{name} must define four parts")
                self.assertTrue(rules.primary_title)
                self.assertTrue(rules.spec)

    def test_hebrew_is_the_shipped_default(self) -> None:
        candidates = quality.config_search_path(PLUGIN_ROOT)
        bundled = [c for c in candidates if CONFIGS_DIR in c.parents]
        self.assertEqual(bundled[0].stem, "hebrew")

    def test_english_config_is_reachable_as_a_fallback(self) -> None:
        self.assertIn(CONFIGS_DIR / "english.json", quality.config_search_path(PLUGIN_ROOT))


class UseLanguageScriptTests(unittest.TestCase):
    """The script writes outside the repo, so a user's choice survives updates."""

    def setUp(self) -> None:
        self.temp = tempfile.TemporaryDirectory()
        self.home = Path(self.temp.name)

    def tearDown(self) -> None:
        self.temp.cleanup()

    def _run(self, *args: str) -> subprocess.CompletedProcess:
        env = os.environ.copy()
        env["HOME"] = str(self.home)
        return subprocess.run(["bash", str(USE_LANGUAGE_SCRIPT), *args],
                              text=True, capture_output=True, check=False, env=env)

    def test_selecting_english_writes_the_user_config(self) -> None:
        result = self._run("english")
        self.assertEqual(result.returncode, 0, result.stderr)
        written = self.home / ".claude" / "recap.config.json"
        self.assertTrue(written.is_file())
        self.assertEqual(json.loads(written.read_text(encoding="utf-8"))["language"]["name"], "English")

    def test_it_can_target_codex(self) -> None:
        self.assertEqual(self._run("english", "codex").returncode, 0)
        self.assertTrue((self.home / ".codex" / "recap.config.json").is_file())

    def test_it_backs_up_an_existing_config(self) -> None:
        self._run("english")
        self._run("hebrew")
        backups = list((self.home / ".claude").glob("recap.config.json.bak.*"))
        self.assertEqual(len(backups), 1, "switching languages must not silently discard edits")
        self.assertEqual(
            json.loads((self.home / ".claude" / "recap.config.json").read_text(encoding="utf-8"))
            ["language"]["name"], "Hebrew")

    def test_unknown_language_fails_loudly_and_lists_options(self) -> None:
        result = self._run("klingon")
        self.assertNotEqual(result.returncode, 0)
        self.assertIn("no bundled ruleset", result.stderr)
        self.assertIn("english", result.stdout)

    def test_unknown_tool_is_rejected(self) -> None:
        self.assertNotEqual(self._run("english", "emacs").returncode, 0)
        self.assertFalse((self.home / ".emacs").exists())


class EnglishEndToEndTests(unittest.TestCase):
    """An English user must get the same experience a Hebrew user gets."""

    def setUp(self) -> None:
        self.temp = tempfile.TemporaryDirectory()
        self.root = Path(self.temp.name)
        self.transcript = self.root / "session.jsonl"
        self.home = self.root / "home"
        (self.home / ".claude").mkdir(parents=True)

    def tearDown(self) -> None:
        self.temp.cleanup()

    def _activate_english(self) -> None:
        subprocess.run(["bash", str(USE_LANGUAGE_SCRIPT), "english"], check=True,
                       capture_output=True, text=True,
                       env={**os.environ, "HOME": str(self.home)})

    def _write(self, closing: str) -> None:
        records = [
            {"type": "assistant", "message": {"content": [
                {"type": "tool_use", "name": "Edit", "input": {"file_path": "/srv/app.py"}}]}},
            {"type": "assistant", "message": {"content": [{"type": "text", "text": closing}]}},
        ]
        self.transcript.write_text(
            "\n".join(json.dumps(r, ensure_ascii=False) for r in records) + "\n", encoding="utf-8")

    def _run(self, session_id: str, hook: Path = CLAUDE_HOOK) -> subprocess.CompletedProcess:
        env = os.environ.copy()
        env["HOME"] = str(self.home)
        env["RECAP_MARKER_DIR"] = str(self.root / "markers")
        env.pop("RECAP_CONFIG", None)
        event = {"session_id": session_id, "transcript_path": str(self.transcript)}
        return subprocess.run([sys.executable, str(hook)], input=json.dumps(event),
                              text=True, capture_output=True, check=False, env=env)

    def test_english_recap_passes_after_switching(self) -> None:
        self._activate_english()
        self._write(LONG_TECHNICAL + "\n\n" + GOOD_EN)
        self.assertEqual(self._run("en-ok").stdout, "")

    def test_english_user_is_told_off_in_english(self) -> None:
        self._activate_english()
        self._write(LONG_TECHNICAL)
        payload = json.loads(self._run("en-missing").stdout)
        reason = payload["reason"]
        self.assertIn("What changed", reason)
        self.assertIn("What to decide", reason)
        self.assertNotIn("במילים פשוטות", reason)

    def test_english_config_rejects_a_hebrew_recap(self) -> None:
        self._activate_english()
        self._write(LONG_TECHNICAL + "\n\n" + GOOD_HE)
        reason = json.loads(self._run("en-wronglang").stdout)["reason"]
        self.assertIn("no plain-language recap", reason)

    def test_without_switching_the_default_stays_hebrew(self) -> None:
        self._write(LONG_TECHNICAL + "\n\n" + GOOD_HE)
        self.assertEqual(self._run("he-default").stdout, "")

    def test_codex_hook_honours_the_same_choice(self) -> None:
        self._activate_english()
        records = [
            {"type": "response_item", "payload": {
                "type": "custom_tool_call", "name": "exec",
                "input": "cat > /srv/app.py <<'EOF'\nx\nEOF"}},
            {"type": "event_msg", "payload": {
                "type": "agent_message", "phase": "final",
                "message": LONG_TECHNICAL + "\n\n" + GOOD_EN}},
        ]
        self.transcript.write_text(
            "\n".join(json.dumps(r, ensure_ascii=False) for r in records) + "\n", encoding="utf-8")
        self.assertEqual(self._run("en-codex", CODEX_HOOK).stdout, "")


if __name__ == "__main__":
    unittest.main()
