"""Config-driven quality rules for a plain-language closing recap.

The recap exists so the user can read it INSTEAD of the long message above it,
so it has to be two things at once:

  plain     — anyone can understand it: the everyday language, short sentences,
              no unexplained professional words, not a wall of file names;
  complete  — nothing important is dropped: what changed, what was checked and
              what came out (real numbers, failures included), what is still
              open, and what the user has to decide.

The engine knows nothing about Claude Code or Codex — it takes the recap, the
rest of the turn's text, and how many files changed, and returns the rules it
breaks. The two hooks supply the transcript reading, so both grade identically.

Everything language-specific (titles, headings, the professional-word list,
how a check or a failure is phrased, thresholds) lives in a JSON config, so
adopting another language means writing a config, not editing code.
"""

from __future__ import annotations

import json
import os
import re
from pathlib import Path
from typing import Any

DEFAULT_CONFIG_NAME = "recap.config.json"
BUNDLED_DIR_NAME = "configs"
DEFAULT_LANGUAGE = "hebrew"

SCRIPT_RANGES = {
    "hebrew": "֐-׿",
    "latin": "A-Za-z",
}

# Hebrew glues single-letter prefixes onto words ("בקומיט", "ה-commit"), so a
# term must tolerate a prefix while still ending at a word boundary — otherwise
# "הוק" matches inside "הוקם" and "באג" inside "באג'נדה".
_HEBREW = SCRIPT_RANGES["hebrew"]
_HEBREW_LETTER = "א-ת"
_HEBREW_PREFIX = "(?:[בהוכלמש]{0,2}-?)"

SENTENCE_END_RE = re.compile(r"[.!?…؟。！？]")
SENTENCE_SPLIT_RE = re.compile(r"(?<=[.!?…؟。！？])\s+|\n+")
BULLET_LINE_RE = re.compile(r"(?m)^\s*(?:[-*•‣]|\d+[.)])\s+\S")

# Raw technical tokens: a few help, a wall of them is not plain language.
RAW_NAME_RE = re.compile(
    r"`[^`\n]+`"                                   # code spans
    r"|(?<![\w/-])--?[A-Za-z][\w-]{2,}"            # --flags / -flag
    r"|(?:~|\.)?/[A-Za-z0-9._-]+/[A-Za-z0-9._/-]+" # /paths/like/this
    r"|\b[\w-]+\.(?:py|sh|js|mjs|cjs|ts|tsx|jsx|json|jsonl|md|toml|ya?ml|html|css|sql|rb|go|rs)\b"
)

# A word or two in quotes is being talked ABOUT, not used. Kept short so a
# whole quoted sentence cannot smuggle jargon past the check.
QUOTED_MENTION_RE = re.compile(r'"[^"\n]{1,30}"|“[^”\n]{1,30}”|״[^״\n]{1,30}״')

# Test results written as fractions ("42/42") look the same in every language.
FRACTION_RE = re.compile(r"(?<![\d/.])(\d{1,5})\s*/\s*(\d{1,5})(?![\d/.])")


def _term_pattern(term: str) -> str:
    if re.search(f"[{_HEBREW}]", term):
        return (f"(?<![{_HEBREW_LETTER}]){_HEBREW_PREFIX}{re.escape(term)}"
                f"(?![{_HEBREW_LETTER}'׳])")
    body = re.escape(term).replace(r"\ ", r"\s+")
    if not (term.isupper() and len(term) > 1):  # "UI", "PR" only in capitals
        body = f"(?i:{body})"
    return f"(?<![A-Za-z_]){body}(?![A-Za-z_])"


def _title_pattern(titles: list[str]) -> re.Pattern[str]:
    alternatives = "|".join(re.escape(title) for title in titles)
    return re.compile(
        rf"(?im)^[\s>*_#-]*(?:\*\*|__)?\s*(?:{alternatives})"
        # The closing emphasis must stay on the title's own line, or it would eat
        # the opening "**" of the first part heading on the line below.
        r"[ \t]*(?:\*\*|__)?[ \t]*:?[ \t]*"
    )


def _beat_pattern(labels: list[str]) -> re.Pattern[str]:
    """Match a part heading, recording whether it was visually emphasised.

    A bullet marker counts as a bullet only when whitespace follows, so the `**`
    of a bold heading is never mistaken for a `*` list marker. Longer labels are
    tried first so "How I checked it" is not cut at "How I checked".
    """
    ordered = sorted(labels, key=len, reverse=True)
    alternatives = "|".join(re.escape(label) for label in ordered)
    return re.compile(
        r"(?m)^[ \t]*(?:>[ \t]*)*(?:[-*•‣][ \t]+|\d+[.)][ \t]+)?"
        r"(?P<hash>\#{1,6}[ \t]*)?(?P<bold>\*\*|__)?[ \t]*"
        rf"(?:{alternatives})"
        r"[ \t]*(?:\*\*|__)?[ \t]*[:：]?[ \t]*"
    )


def _explained(text: str, start: int, end: int) -> bool:
    """True when a term sits right next to a bracketed explanation."""
    after = text[end:end + 3].lstrip("`'\" ")
    before = text[max(0, start - 3):start].rstrip("`'\" ")
    return after.startswith("(") or before.endswith("(")


def bundled_configs(plugin_root: Path) -> dict[str, Path]:
    """The rulesets that ship with the plugin, by language name."""
    directory = plugin_root / BUNDLED_DIR_NAME
    if not directory.is_dir():
        return {}
    return {path.stem: path for path in sorted(directory.glob("*.json"))}


def config_search_path(plugin_root: Path) -> list[Path]:
    """Where a config may live, most specific first.

    A user override outside the repo means customising the rules never conflicts
    with pulling a new version of the hook.
    """
    candidates: list[Path] = []
    override = os.environ.get("RECAP_CONFIG")
    if override:
        candidates.append(Path(override).expanduser())
    candidates.append(Path.home() / ".claude" / DEFAULT_CONFIG_NAME)
    candidates.append(Path.home() / ".codex" / DEFAULT_CONFIG_NAME)
    bundled = bundled_configs(plugin_root)
    if DEFAULT_LANGUAGE in bundled:
        candidates.append(bundled[DEFAULT_LANGUAGE])
    candidates.extend(path for name, path in bundled.items() if name != DEFAULT_LANGUAGE)
    return candidates


class RecapRules:
    """The rules a closing recap is graded against."""

    def __init__(self, config: dict[str, Any]) -> None:
        self.raw = config
        thresholds = config.get("thresholds", {})
        self.min_section_chars = int(thresholds.get("minSectionChars", 380))
        self.chars_per_changed_file = int(thresholds.get("charsPerChangedFile", 50))
        self.max_extra_files = int(thresholds.get("maxExtraFiles", 8))
        self.min_section_sentences = int(thresholds.get("minSectionSentences", 5))
        self.min_beat_chars = int(thresholds.get("minBeatChars", 50))
        self.max_raw_names = int(thresholds.get("maxRawNames", 6))
        self.max_sentence_words = int(thresholds.get("maxSentenceWords", 25))
        self.trivial_closing_chars = int(thresholds.get("trivialClosingChars", 200))

        self.require_bold = bool(config.get("requireBoldHeadings", True))
        self.title_re = _title_pattern(list(config["titles"]))
        self.primary_title = config["titles"][0]
        self.beats = [
            (beat["key"], beat["title"], _beat_pattern(list(beat["labels"])))
            for beat in config["beats"]
        ]
        self.beat_titles = {key: title for key, title, _p in self.beats}
        self.jargon = [
            (entry["plain"], re.compile("|".join(_term_pattern(t) for t in entry["terms"])))
            for entry in config.get("jargon", [])
        ]

        # Optional phrasing patterns; a config without one simply skips that rule.
        patterns = {name: re.compile(value, re.IGNORECASE)
                    for name, value in (config.get("patterns") or {}).items()}
        self.test_words_re = patterns.get("testWords")
        self.test_count_re = patterns.get("testCounts")
        self.result_count_re = patterns.get("resultCounts")
        self.not_a_count_before_re = patterns.get("notACountBefore")
        self.failure_reported_re = patterns.get("failureReported")
        self.failure_mentioned_re = patterns.get("failureMentioned")
        self.check_explained_re = patterns.get("checkExplained")

        language = config.get("language") or {}
        script = language.get("script")
        self.script_range = SCRIPT_RANGES.get(script) if script else None
        self.script_name = script
        self.min_script_ratio = float(language.get("minRatio", 0.5))
        self.script_min_letters = int(language.get("minLetters", 40))
        self.language_name = language.get("name", script or "the target language")

    # -- reading ---------------------------------------------------------
    def section(self, text: str) -> str:
        """Everything after the last recap title."""
        matches = list(self.title_re.finditer(text))
        if not matches:
            return ""
        return text[matches[-1].end():].strip()

    def beat_contents(self, section: str) -> dict[str, tuple[str, bool] | None]:
        """Map each part to (content, is_emphasised), or None when absent.

        Content runs from the part's heading to whichever other part starts
        next, so a heading with nothing under it is visibly empty rather than
        borrowing the following part's text.
        """
        found: list[tuple[int, int, str, bool]] = []
        for key, _title, pattern in self.beats:
            match = pattern.search(section)
            if match:
                found.append((match.start(), match.end(), key,
                              bool(match.group("bold") or match.group("hash"))))
        found.sort()

        contents: dict[str, tuple[str, bool] | None] = {key: None for key, _t, _p in self.beats}
        for index, (_start, end, key, emphasised) in enumerate(found):
            stop = found[index + 1][0] if index + 1 < len(found) else len(section)
            contents[key] = (section[end:stop].strip(), emphasised)
        return contents

    def script_ratio(self, text: str) -> float:
        if not self.script_range:
            return 1.0
        primary = len(re.findall(f"[{self.script_range}]", text))
        others = sum(
            len(re.findall(f"[{rng}]", text))
            for name, rng in SCRIPT_RANGES.items()
            if name != self.script_name
        )
        total = primary + others
        if total < self.script_min_letters:
            return 1.0  # too little text to judge; other rules cover it
        return primary / total

    def unexplained_jargon(self, text: str) -> list[tuple[str, str]]:
        """Professional words used without a plain explanation next to them.

        Returns (word as written, plain replacement) once per term. A term is
        fine when a bracketed explanation sits right next to it, either way
        round. Names in code spans and paths, and words merely mentioned in
        short quotes, are skipped.
        """
        def blank(match: re.Match[str]) -> str:
            return " " * len(match.group(0))  # keeps offsets stable

        scan = QUOTED_MENTION_RE.sub(blank, RAW_NAME_RE.sub(blank, text))
        found: list[tuple[str, str]] = []
        for plain, pattern in self.jargon:
            matches = list(pattern.finditer(scan))
            if not matches or any(_explained(scan, m.start(), m.end()) for m in matches):
                continue
            found.append((matches[0].group(0).strip(), plain))
        return found

    def long_sentences(self, text: str) -> list[str]:
        """Sentences too long to read easily, as their first few words."""
        too_long = []
        for sentence in SENTENCE_SPLIT_RE.split(text):
            words = re.sub(r"^\s*(?:[-*•‣]|\d+[.)])\s+", "", sentence).split()
            if len(words) > self.max_sentence_words:
                too_long.append(" ".join(words[:6]) + " …")
        return too_long

    def last_test_fact(self, body: str) -> list[str]:
        """Numbers of the last test result the message reports ("42/42" → 42).

        The last sentence that reports a result wins, since earlier runs are
        usually superseded. Zeros are dropped: "0 failed" need not be repeated.
        """
        last: list[str] = []
        for sentence in SENTENCE_SPLIT_RE.split(body):
            numbers: list[str] = []
            if self.test_words_re and self.test_words_re.search(sentence):
                for match in FRACTION_RE.finditer(sentence):
                    if int(match.group(1)) <= int(match.group(2)):
                        numbers += [match.group(1), match.group(2)]
            if self.test_count_re:
                numbers += [m.group(1) for m in self.test_count_re.finditer(sentence)]
            if self.result_count_re:
                for match in self.result_count_re.finditer(sentence):
                    before = sentence[max(0, match.start() - 12):match.start()]
                    if not (self.not_a_count_before_re and self.not_a_count_before_re.search(before)):
                        numbers.append(match.group(1))
            if numbers:
                last = numbers
        return list(dict.fromkeys(n for n in last if n != "0"))

    # -- grading ---------------------------------------------------------
    def diagnose(self, section: str, body: str = "", changed_count: int = 1) -> list[str]:
        """Return plain descriptions of the rules this recap breaks.

        `body` is everything else said in the turn; `changed_count` is how many
        files (or file-changing commands) the turn touched.
        """
        problems: list[str] = []
        contents = self.beat_contents(section)

        # --- structure ---
        missing = [title for key, title, _p in self.beats if contents[key] is None]
        thin = [title for key, title, _p in self.beats
                if contents[key] is not None and len(contents[key][0]) < self.min_beat_chars]
        unemphasised = [title for key, title, _p in self.beats
                        if contents[key] is not None and not contents[key][1]]
        if self.require_bold and unemphasised:
            problems.append(
                "These headings are not bold, so they do not stand out when the "
                "user skims: " + ", ".join(f'"{t}"' for t in unemphasised)
                + f'. Write each one in bold, the same way "{self.primary_title}" is written.'
            )
        if missing:
            problems.append(
                "The recap is missing its required headings: "
                + ", ".join(f'"{t}"' for t in missing)
                + f". Lay it out as {len(self.beats)} bold parts — "
                + ", ".join(f'"{t}"' for _k, t, _p in self.beats) + "."
            )
        if thin:
            problems.append(
                "These headings exist but have almost nothing under them: "
                + ", ".join(f'"{t}"' for t in thin)
                + ". Give each part at least a couple of real sentences."
            )
        min_chars = (self.min_section_chars
                     + self.chars_per_changed_file * min(changed_count, self.max_extra_files))
        sentences = len(SENTENCE_END_RE.findall(section)) + len(BULLET_LINE_RE.findall(section))
        if len(section) < min_chars or sentences < self.min_section_sentences:
            problems.append(
                "The recap is too short for the work done in this turn — it reads as "
                "a status line, not a replacement for the message. Tell every "
                "important change, check, and open point."
            )

        # --- plain language ---
        if self.script_ratio(section) < self.min_script_ratio:
            problems.append(
                f"The recap is not actually written in {self.language_name}. Write it "
                f"in everyday {self.language_name}; keep other languages only for names "
                "that have no natural equivalent."
            )
        jargon = self.unexplained_jargon(section)
        if jargon:
            problems.append(
                "These professional words are not explained, so not everyone will "
                "understand them: "
                + ", ".join(f'"{word}" (say "{plain}")' for word, plain in jargon)
                + ". Use the plain words, or keep the term and explain it in brackets "
                "right next to it."
            )
        long_ones = self.long_sentences(section)
        if long_ones:
            problems.append(
                f"Some sentences are too long to read easily (over {self.max_sentence_words} "
                "words): " + "; ".join(f'"{s}"' for s in long_ones[:3])
                + ". Split each into two or three short sentences."
            )
        if len(RAW_NAME_RE.findall(section)) > self.max_raw_names:
            problems.append(
                "The recap leans on raw paths, flags, file names, and code instead of "
                "plain words. Keep only the few names that matter, and say what each "
                "one does."
            )

        # --- completeness ---
        numbers = self.last_test_fact(body)
        if any(not re.search(rf"(?<!\d){n}(?!\d)", section) for n in numbers):
            problems.append(
                "The message reports a test result (" + "/".join(numbers)
                + ") but the recap drops its numbers. Keep the real numbers — how many "
                "checks ran, how many passed, how many failed."
            )
        if (self.failure_reported_re and self.failure_reported_re.search(body)
                and not (self.failure_mentioned_re and self.failure_mentioned_re.search(section))):
            problems.append(
                "The message says something failed or was not checked, but the recap "
                "never mentions it. Say what failed or was skipped, and what it means."
            )
        verified = contents.get("verified")
        if (verified is not None and self.check_explained_re
                and not self.check_explained_re.search(verified[0])):
            problems.append(
                f'The "{self.beat_titles["verified"]}" part does not say what was actually '
                "checked — \"the tests passed\" tells the user nothing. Say what each "
                "check makes sure of, or say plainly that it was not checked and why."
            )
        changed = contents.get("changed")
        if changed is not None and changed_count >= 3:
            needed = min((changed_count + 1) // 2, 4)
            items = max(len(BULLET_LINE_RE.findall(changed[0])),
                        len(SENTENCE_END_RE.findall(changed[0])))
            if items < needed:
                problems.append(
                    f"This turn changed {changed_count} files, but "
                    f'"{self.beat_titles["changed"]}" explains them in less than {needed} '
                    "lines. Give each important change its own line: what changed, "
                    "where, and why."
                )
        return problems

    # -- reporting -------------------------------------------------------
    @property
    def missing_recap(self) -> str:
        return "The closing message has no plain-language recap at all."

    @property
    def spec(self) -> str:
        bold = "BOLD " if self.require_bold else ""
        lines = [
            f'The "{self.primary_title}" section must let the user skip the message '
            "above it and still know everything important — in words ANYONE "
            f"understands. Write it in everyday {self.language_name} with short "
            f"sentences, and lay it out as {len(self.beats)} parts, each under its "
            f"own {bold}heading, written the same way the title is:"
        ]
        for beat in self.raw["beats"]:
            lines.append(f"  {beat['title']} — {beat['covers']}")
        lines.append("Replace professional words with plain ones, or explain them in brackets.")
        return "\n".join(lines)

    def reason(self, problems: list[str]) -> str:
        bullets = "\n".join(f"- {problem}" for problem in problems)
        return (
            "This turn changed files, so it must end with a plain, complete "
            f"{self.language_name} recap. What is wrong right now:\n"
            f"{bullets}\n\n{self.spec}\n\n"
            f'Rewrite the closing message with a proper "{self.primary_title}" section. '
            "Do not answer with a bare acknowledgement, and do not hide the technical "
            "story — translate it. Then finish. Do not start new work."
        )


def load_rules(plugin_root: Path) -> RecapRules:
    for candidate in config_search_path(plugin_root):
        try:
            if candidate.is_file():
                return RecapRules(json.loads(candidate.read_text(encoding="utf-8")))
        except Exception:
            continue  # a broken override must not disable the hook
    raise FileNotFoundError("no recap config found")
