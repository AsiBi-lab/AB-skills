# plain-language-recap

A `Stop` hook for **Claude Code** and **Codex** that refuses to let a session end
with "done ✅" after it changed your files.

If a turn edited anything, the closing message has to carry a real
plain-language recap — one you can read **instead of** the long message above
it. That means two things at once: **anyone can understand it** (everyday words,
short sentences, no unexplained jargon), and **nothing important is dropped**
(every change, the real test numbers, anything that failed, anything still
open).

When a recap falls short, the hook does not nag. It says which rule broke:

```
This turn changed files, so it must end with a plain, complete Hebrew recap.
What is wrong right now:
- These professional words are not explained, so not everyone will understand
  them: "commit" (say "שמירת גרסה"), "באג" (say "תקלה").
- The message reports a test result (42) but the recap drops its numbers.
- The "איך בדקתי ומה יצא" part does not say what was actually checked.
```

## What it checks

The recap has four **bold** parts — what changed, how it was checked and what
came out, what is still open, what to decide — and has to clear every gate:

| Gate | What it catches |
|---|---|
| **Title and four parts** | No recap, or a wall of prose with no skimmable structure |
| **Bold headings, real content** | Headings that disappear, or `What to decide: nothing.` |
| **Length follows the work** | A status line after a turn that touched eight files |
| **Language** | Headings in your language, body in English |
| **Plain words** | `deploy`, `merge`, `regex` with no explanation — the hook suggests the plain word. A term explained in brackets, or mentioned in "quotes", is fine |
| **Short sentences** | Sentences over 25 words |
| **Few raw names** | A wall of paths, flags, and file names |
| **Numbers kept** | The message says "179 tests pass"; the recap doesn't |
| **Failures kept** | The message says "3 failed" or "I didn't check X"; the recap is silent |
| **Checks explained** | "The tests passed" — instead of what each check makes sure of |
| **Every change told** | Six files changed, one vague line about them |

It only fires on turns that **changed files** — and it counts shell writes
(`cat > file`, `sed -i`, `tee`, `git commit`), not just dedicated edit tools.
Code piped to an interpreter counts only if it writes a file, so a search
script with a `>` in it is not mistaken for an edit. Read-only turns, a question
asked after the work is done, one-line acknowledgements, and subagent output
are left alone.

**Safety:** fail-open on every error, honours the anti-loop flag, and blocks at
most **once per turn**. A broken config falls back to the shipped one rather
than disabling the hook. It can annoy you once; it can never wedge you.

## Install — Claude Code

```
/plugin marketplace add AsiBi-lab/AB-skills
```
```
/plugin install plain-language-recap@ab-skills
```

Update later with `/plugin marketplace update ab-skills`.

## Install — Codex

```bash
git clone https://github.com/AsiBi-lab/AB-skills.git ~/.ab-skills && ~/.ab-skills/plugins/plain-language-recap/codex/install.sh
```

To update:

```bash
git -C ~/.ab-skills pull
```

The installer stores the hook's path, so pulling a new version is enough — no
re-install, and it backs up your existing `~/.codex/hooks.json` first.

## Choose your language

The hook ships with two rulesets — **Hebrew** (the default) and **English** —
and switching is one command, run from this plugin's folder:

```bash
./scripts/use-language.sh english
```

That copies the ruleset to `~/.claude/recap.config.json`, **outside the plugin**,
so your choice and any later edits survive every update. Add `codex` as a second
argument to set it for Codex instead. Re-running backs up your previous config
before replacing it.

Prefer to do it by hand? Copy
[`configs/english.json`](configs/english.json)
to `~/.claude/recap.config.json` yourself. `RECAP_CONFIG=/path/to/config.json`
overrides everything.

### Any other language

There is nothing Hebrew- or English-specific in the code. Copy a bundled config,
translate the strings, and you have a new language:

```jsonc
{
  "language": { "name": "Spanish", "script": "latin", "minRatio": 0.5 },
  "requireBoldHeadings": true,
  "titles": ["En palabras simples"],
  "beats": [
    { "key": "changed", "title": "Qué cambió",
      "labels": ["Qué cambió", "Qué hice"],
      "covers": "each important change on its own line: what, where, and why." }
    // … plus "verified", "open", and "decide"
  ],
  "jargon": [
    { "terms": ["deploy", "desplegar"], "plain": "publicar" }
  ],
  "patterns": {
    "checkExplained": "\\b(?:comprobé|verifiqué)\\b[^.\\n]{0,60}?\\bque\\b|\\bno (?:lo )?comprobé\\b",
    "failureReported": "(?<!\\d)[1-9]\\d*\\s+(?:\\S+\\s+){0,2}?fallar(?:on)?",
    "failureMentioned": "fall|no comprob|error|problema"
  },
  "thresholds": { "minSectionChars": 380, "maxSentenceWords": 25 }
}
```

The four part keys matter: `changed` gets the "every change told" rule and
`verified` gets the "checks explained" rule. `jargon` lists professional words
with the plain word to suggest instead. `patterns` are regular expressions for
how your language says "I checked that…", "3 failed", and so on — see
[`english.json`](configs/english.json) for the full
set; leave one out and that rule is simply skipped. `script` accepts
`"hebrew"`, `"latin"`, or `null` to skip the language check. Loosen the whole
thing through `thresholds`, or set `requireBoldHeadings` to `false`.

Drop a config into `configs/` and it becomes
selectable by name — a pull request adding your language is welcome.

## Also tell your agent what you want

The hook is a safety net, not the instruction. Put the rule in your `CLAUDE.md`
or `AGENTS.md` too, or you will be caught by a standard you never stated.

English:

> Every finished piece of work ends with an "In plain words" section that lets
> me skip the message above it and still know everything important. Anyone
> must be able to understand it: everyday words, short sentences, professional
> terms replaced or explained in brackets. Nothing important may be dropped:
> every change, the real test numbers, anything that failed or was not
> checked. Four parts with **bold** headings — **What changed** (one line per
> change), **How I checked it** (what each check makes sure of, and the
> numbers), **What's still open**, **What to decide**.

Hebrew:

> כל עבודה שמסתיימת נחתמת בסעיף "במילים פשוטות", שאפשר לקרוא במקום כל ההודעה
> ולדעת את כל מה שחשוב. כל אחד צריך להבין אותו: מילים של יום-יום, משפטים
> קצרים, ומילים מקצועיות מוחלפות או מוסברות בסוגריים. שום דבר חשוב לא נשמט:
> כל שינוי, המספרים האמיתיים של הבדיקות, ומה נכשל או לא נבדק. ארבעה חלקים עם
> כותרות **מודגשות** — **מה השתנה** (שורה לכל שינוי), **איך בדקתי ומה יצא**
> (מה כל בדיקה מוודאת, והמספרים), **מה עוד לא סגור**, **מה להחליט**.

## Tests

```bash
python3 -m unittest discover -s tests -p "test_*.py" -v
```

62 tests, no dependencies beyond the standard library. They cover the grading
rules in both languages, both transcript formats, turn detection, the safety
gates, the language-switch script, and the English path end to end.

## Why it exists

Agents are good at technical reports and bad at knowing when you stopped
following. A recap you skim and understand is what turns finished work into a
decision — so it is worth enforcing rather than hoping for.

## License

MIT — see [LICENSE](../../LICENSE). Built by [@AsiBi-lab](https://github.com/AsiBi-lab).
