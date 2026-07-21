# SAVE Protocol (hand-off)

Full procedure for `/handoff save`. Goal: produce a `HANDOFF.md` complete enough that the user can delete the session without fear.

## Step 1 — Gather live state

Run these and capture the output (do not reconstruct from memory):

```bash
ROOT=$(git rev-parse --show-toplevel 2>/dev/null) ; echo "root=$ROOT"
git branch --show-current 2>/dev/null
git rev-parse --short HEAD 2>/dev/null
git status -sb 2>/dev/null
git stash list 2>/dev/null
date -u +%Y-%m-%dT%H:%M:%SZ
hostname
```

- **Not a git repo** (`ROOT` empty): skip all git steps. Set `branch: n/a`, `head: n/a`. Write the doc; skip the commit. Tell the user it's saved as a plain file (no version history, no multi-machine sync).

## Step 2 — Synthesize working memory

Fill the template ([handoff-template.md](handoff-template.md)) from the conversation. Discipline:

- Capture the **delta** vs what a fresh session auto-loads. Skip anything already in CLAUDE.md, git, the file tree, or memory.
- **§7 uncommitted work is the priority.** For every dirty file, state what changed and why it's mid-flight. This is the only state git cannot recover.
- Empty section → write `none`. Never pad to look thorough.
- §4 next action must be concrete enough to act on in under a minute.

## Step 3 — Write the current file

Ensure the directory exists, then write `.handoff/HANDOFF.md` (overwrite), `status: OPEN`.

```bash
mkdir -p .handoff/archive
```

On first run, also drop a one-line `.handoff/README.md` so the folder is self-explanatory:

```
This folder is managed by the `handoff` skill. HANDOFF.md = current session handoff;
archive/ = timestamped history. Run `/handoff resume` to continue from HANDOFF.md.
```

## Step 4 — Archive a timestamped copy

```bash
TS=$(date -u +%Y%m%dT%H%M%SZ)
cp .handoff/HANDOFF.md ".handoff/archive/HANDOFF-$TS.md"
```

The archive is append-only history. If it grows large, mention pruning to the user (`.handoff/archive/`) — never auto-delete.

## Step 5 — Commit (named files only, no push)

```bash
git check-ignore -q .handoff && echo "IGNORED" || echo "TRACKED"
```

| Result | Action |
|--------|--------|
| `TRACKED` | `git add .handoff/HANDOFF.md ".handoff/archive/HANDOFF-$TS.md"` then `git commit -m "chore(handoff): <one-line goal>"` |
| `IGNORED` | Skip the commit — the user opted this project into local-only handoffs. Say so. |

Rules (from the user's git hygiene):
- **Named files only.** Never `git add -A` / `git add .`.
- **Never push.** Push stays user-triggered.
- If a pre-commit hook fails, fix the cause and make a **new** commit — never `--amend`, never `--no-verify`.

## Step 6 — Report to the user (Hebrew)

State plainly:
- ✅ Saved + committed (or "saved, local-only / not committed" if ignored or non-git).
- The one-line goal.
- "בטוח ל-`/clear`. בסשן הבא הרץ `/handoff resume`."
- **Multi-machine:** if the user might continue on another machine, remind them to `git push` now — the handoff is committed but not pushed, so it won't be on the other machine until they do.

## Opt-out: local-only handoffs for a project

If the user doesn't want handoff noise in a project's history, add `.handoff/` to that repo's `.gitignore`. The SAVE protocol detects this (Step 5) and skips the commit automatically — no skill change needed. The file is still written and resumable locally; it just won't sync across machines.
