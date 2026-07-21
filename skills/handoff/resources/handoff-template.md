# HANDOFF.md Template

Copy this structure verbatim into `.handoff/HANDOFF.md`. Fill every section. Write `none` where a section is genuinely empty — do not pad.

The guiding question for every line: **"Does a fresh session already know this from CLAUDE.md, git, the file tree, or memory?"** If yes, leave it out. Capture only working memory.

The doc is **self-resuming**: it opens with a `▶ TO RESUME` block, so a fresh session can pick it up by *reading the file alone* — no skill required. `/handoff resume` is just the convenience trigger that adds disciplined git-drift reconciliation on top of that read.

---

```markdown
---
status: OPEN
written: <UTC, e.g. 2026-06-03T14:32:00Z>
machine: <hostname>
branch: <git branch or "n/a">
head: <short HEAD sha or "n/a">
session_goal: "<one line: what this session was driving toward>"
---

# HANDOFF — <project name> — <short topic>

> **▶ TO RESUME — fresh session, no skill needed**
>
> 1. **Re-ground:** `git status -sb && git log --oneline -8` — compare branch/HEAD against the frontmatter above.
> 2. **If it drifted** (HEAD moved, dirty files now clean, or `machine` differs → `git pull` first): trust **git over this doc** and reconcile §3.
> 3. **Then act:** do **§4 Next action**. Prove it with **§9 How to verify**.
> 4. *(Optional)* `/handoff resume` runs steps 1–2 with full drift-reconciliation and flips `status` to `RESUMED`.

## 1. TL;DR
2–4 sentences. If the reader reads nothing else, where are we and what's next.

## 2. Goal & success criteria
What we're trying to achieve and **why**. The concrete definition of done —
how we'll know it's finished. (Intent, not task list.)

## 3. Status board
- ✅ Done: …
- 🔄 In progress: …  ← the current focus, where the cursor actually is
- ⬜ Not started: …

## 4. Next action  ← the single most important line
The very next concrete step, specific enough to act on in under a minute.
e.g. "Edit `src/foo.ts` `parseDate()` to handle the `null` branch, then run `npm test foo`."

## 5. Key decisions & rationale
Decisions made this session and **why** — so they're not relitigated.
Include rejected options: "Tried X → failed because Y → chose Z."

## 6. Gotchas / landmines
Dead ends, things that broke, environment quirks, "do NOT do X because …".
The stuff that cost time to learn.

## 7. Working state (git + files)
- Branch / HEAD / clean-or-dirty.
- **Uncommitted changes** (the unrecoverable part — be exhaustive):
  - `path/to/file` — what changed and why it's mid-flight.
- Stash / worktree, if any.
- Key files in play (path → role): `path` — why it matters.

## 8. Open questions for the user
Decisions that need the human's input before proceeding. `none` if fully unblocked.

## 9. How to verify
The exact command(s) / checks that prove the work is correct.
e.g. `npm test`, `make build`, a manual check, the success signal to look for.
```

---

## Why the ▶ block lives at the top

It's the **first thing** a fresh reader hits, and it's written to be acted on by a plain read — no skill load, no save machinery. That's the asymmetry the design rests on: **SAVE needs intelligence** (gather state, synthesize the delta, decide what matters, write, archive, commit); **RESUME is "read a self-describing doc + sanity-check git."** The block keeps the read-path self-sufficient; the skill's resume mode only adds disciplined reconciliation.

## Frontmatter fields

| Field | Purpose | Filled by |
|-------|---------|-----------|
| `status` | `OPEN` (awaiting resume) → `RESUMED` (consumed). The SessionStart hook only surfaces `OPEN`. | save sets `OPEN`; resume flips to `RESUMED` |
| `written` | UTC timestamp — drives staleness checks on resume | `date -u +%Y-%m-%dT%H:%M:%SZ` |
| `machine` | Hostname — detects multi-machine handoffs (pull-first) | `hostname` |
| `branch` / `head` | Git anchor — resume compares against live values | `git branch --show-current` / `git rev-parse --short HEAD` |
| `session_goal` | One line shown by the SessionStart hook notice | the model |

## Section priority

If time/space is short, these three carry the handoff:

1. **§4 Next action** — without it, the next session stalls at "what now?".
2. **§7 Uncommitted work** — the only state git can't recover for you.
3. **§5 Decisions** — without it, the next session relitigates settled questions.

The ▶ block + these three are the irreducible core; §1–3, 6, 8–9 are valuable but reconstructable from the repo + these.
