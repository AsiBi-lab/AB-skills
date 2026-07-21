# RESUME Protocol (hand-on)

Full procedure for `/handoff resume`. Core principle: **the handoff is a hypothesis about state — verify it against reality before acting.**

> The `HANDOFF.md` doc opens with a self-contained `▶ TO RESUME` block — a fresh session (or just "continue from the handoff") can act on the doc with **no skill**. This procedure is the disciplined version `/handoff resume` runs: the same steps, with full drift-reconciliation and the `status` flip.

## Step 1 — Read the doc

Read `.handoff/HANDOFF.md`. Pull the frontmatter: `written`, `machine`, `branch`, `head`, `session_goal`. If no `HANDOFF.md` exists, tell the user there's nothing to resume and offer a fresh start.

## Step 2 — Re-ground against live state

```bash
git branch --show-current 2>/dev/null
git rev-parse --short HEAD 2>/dev/null
git status -sb 2>/dev/null
git log --oneline -8 2>/dev/null
```

## Step 3 — Reconcile (surface every drift)

| Check | Drift handling |
|-------|----------------|
| Current branch == `branch`? | If not, **warn** and ask before `git checkout` — the user may have moved deliberately. |
| HEAD moved past `head`? | List commits since `head` (`git log --oneline <head>..HEAD`). Fold them into the status board — some "in progress" items may now be done. |
| Files marked uncommitted in §7 still dirty? | Confirm via `git status`. If now committed, note it and drop from the "to finish" list. If still dirty, that work is intact — resume it. |
| `machine` ≠ current host? | **Multi-machine.** Tell the user to `git pull` first (`git status -sb` shows ahead/behind). The handoff was committed elsewhere; ensure you have it *and* any later commits before acting. |
| Named key files (§7) still exist? | Flag any that moved or vanished — the plan may need adjustment. |

`--fresh` flag: skip Step 3 entirely and trust the doc as-is. Use only when the user knows nothing changed.

## Step 4 — Restate to the user (Hebrew)

Give a tight briefing, not a doc dump:
- **Goal** (one line, from §2).
- **Status board** (§3), updated for any drift found in Step 3.
- **Next action** (§4) — the single concrete step.
- **Drift** — anything reconciliation surfaced (branch moved, new commits, missing file).
- **Open questions** (§8) — anything awaiting their decision.

End with: "להמשיך מכאן?" unless the next action is obviously safe and the user already said go.

## Step 5 — Continue & mark consumed

Start executing from §4. Flip the doc's frontmatter `status: OPEN` → `status: RESUMED` (a one-line edit). This stops the SessionStart hook from re-surfacing it. The archived copy in `.handoff/archive/` keeps the original `OPEN` snapshot.

## Stale-handoff playbook

| Symptom | Read it as | Do |
|---------|-----------|-----|
| HEAD far past `head`, many new commits | Work continued elsewhere/after the save | Reconcile hard; the doc's status board is likely outdated — trust git over the doc. |
| `written` is days old | Handoff may be obsolete | Re-ground fully; confirm the goal still stands before acting. |
| §7 dirty files now all clean + committed | The mid-flight work got finished/committed | Treat §3 in-progress as likely done; re-verify with §9. |
| branch in doc doesn't exist | Branch merged/deleted | Find where it landed (`git log --all --oneline | grep`), confirm with user. |

When git and the doc disagree, **git wins** — it's ground truth. The doc explains *intent*; git holds *state*.

## Optional: SessionStart auto-detect hook

A global hook can surface an `OPEN` handoff automatically at the start of any new session, in any project — so after `/clear` the next session reminds you it's there.

**Script:** `~/.claude/skills/handoff/hooks/handoff-session-start.sh` (ships with this skill). It reads `.handoff/HANDOFF.md` in the project, and if `status: OPEN`, injects a one-line notice suggesting `/handoff resume`. It is read-only, fast, and silently no-ops when there's no open handoff.

**Register it** by appending to the `SessionStart` matcher in `~/.claude/settings.json`:

```json
{ "type": "command", "command": "bash ~/.claude/skills/handoff/hooks/handoff-session-start.sh" }
```

The hook only *notifies*. The actual resume is always the user running `/handoff resume` — nothing auto-loads context or runs work without the user.
