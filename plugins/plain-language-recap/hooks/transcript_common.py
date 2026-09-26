"""Shared rules for reading one turn and deciding whether it changed anything.

Both tools can edit files through a plain shell command, not only through a
dedicated edit tool, so a hook that watches edit tools alone stays silent
through an entire session of real work. And only the CURRENT turn matters: a
question asked after the work is done should not demand another recap.
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field

EDIT_TOOLS = {"Edit", "Write", "MultiEdit", "NotebookEdit", "apply_patch"}


@dataclass
class Turn:
    """What happened since the user's last message."""

    id: str = ""
    changed_files: set[str] = field(default_factory=set)
    shell_changes: int = 0
    texts: list[str] = field(default_factory=list)
    last_text: str = ""

    @property
    def changed_count(self) -> int:
        return len(self.changed_files) + self.shell_changes

    def add_text(self, text: str) -> None:
        self.texts.append(text)
        self.last_text = text


_HEREDOC_RE = re.compile(
    r"<<-?[ \t]*(['\"]?)([A-Za-z_][A-Za-z0-9_]*)\1[^\n]*\n(.*?)(?:\n[ \t]*\2[ \t]*(?:\n|$))",
    re.DOTALL)
_NULL_REDIRECT_RE = re.compile(r"\d?>>?\s*/dev/null")
_SCRATCH_REDIRECT_RE = re.compile(r">>?\s*(?:\"|')?(?:/private)?/tmp/\S+")
_QUOTED_RE = re.compile(r"'[^'\n]*'|\"(?:[^\"\\\n]|\\.)*\"")
_MUTATING_SHELL_RES = (
    re.compile(r"(?<![<>])>>?\s*(?:\"|')?[~./$A-Za-z0-9]"),   # write/append to a path
    re.compile(r"\bsed\b[^|;&]*\s-i\b"),
    re.compile(r"\b(?:tee|patch|install|rsync|ditto)\b"),
    re.compile(r"\b(?:mv|cp|rm|rmdir|ln|chmod|chown)\s+-?\S"),
    re.compile(r"\bgit\s+(?:commit|apply|am|revert|reset|restore|checkout|merge|rebase|stash)\b"),
    re.compile(r"\b(?:npm|pnpm|yarn|bun)\s+(?:i|install|add|remove|uninstall)\b"),
)
# Code fed to an interpreter through a heredoc changes files only if it says so.
_SCRIPT_WRITES_RE = re.compile(
    r"open\([^)]*,\s*['\"][wax]"
    r"|\.write_(?:text|bytes)\(|\.unlink\(|\.rename\(|\.replace\(\s*['\"/~]"
    r"|shutil\.(?:copy|move|rmtree)|os\.(?:remove|rename|replace|unlink)"
    r"|writeFileSync|fs\.writeFile|fs\.rm")


def shell_changed_files(command: str) -> bool:
    """True when a shell command plausibly changed a file outside scratch space.

    Heredoc bodies are data, not shell: only the line that opens them is read as
    shell, and the body counts only if it is code that clearly writes a file.
    Quoted text is blanked so a ">" or "cp " inside a string is not a command.
    """
    if not command:
        return False
    bodies: list[str] = []

    def keep_opening_line(match: re.Match[str]) -> str:
        bodies.append(match.group(3))
        return match.group(0).split("\n", 1)[0] + "\n"

    shell = _HEREDOC_RE.sub(keep_opening_line, command)
    if any(_SCRIPT_WRITES_RE.search(body) for body in bodies):
        return True
    shell = _NULL_REDIRECT_RE.sub(" ", shell)
    shell = _SCRATCH_REDIRECT_RE.sub(" ", shell)
    shell = _QUOTED_RE.sub(lambda m: m.group(0)[0] + "Q" + m.group(0)[0], shell)
    return any(pattern.search(shell) for pattern in _MUTATING_SHELL_RES)
