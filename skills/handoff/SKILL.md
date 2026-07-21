---
name: handoff
description: Use when the user asks to "handoff", "hand off this session", "save context before I clear", "save state so I can /clear", "park this work", "hand on", "resume where I left off", "continue from the handoff", "pick up where we stopped". Captures session working-memory into .handoff/HANDOFF.md so a session can be cleared and resumed in a fresh session — even on another machine — with no loss of momentum. NOT for writing project docs/READMEs, git commit messages, or general status reports.
user-invocable: true
disable-model-invocation: true
argument-hint: "save | resume   (default: auto-detect)"
version: 1.1.0
---

# Handoff — Session Context Handoff & Resume

Capture everything a fresh session needs to continue this work into `.handoff/HANDOFF.md`, commit it, and re-ground it on resume — so the session can be cleared and picked up later with zero context loss, even from a different machine.

## Quick Reference

| Invocation | Mode | What happens |
|-----------|------|--------------|
| `/handoff` · `/handoff save` | **SAVE** (hand-off) | Synthesize working memory → write + archive `HANDOFF.md` → commit (no push). Then safe to `/clear`. |
| `/handoff resume` · `/handoff on` | **RESUME** (hand-on) | Read `HANDOFF.md` → re-ground against live git/files → restate plan + next action → continue. |
| `/handoff resume --fresh` | RESUME, trust-as-is | Skip drift reconciliation, take the doc at face value. |

**The contract:** after a SAVE the user can delete the session *without fear*. RESUME never blindly trusts the doc — it verifies the doc against reality first.

## Mode Selection

| `$ARGUMENTS` | Mode |
|--------------|------|
| empty · `save` · `off` · `out` | SAVE |
| `resume` · `on` · `in` · `load` · `continue` | RESUME |

If `$ARGUMENTS` is empty **and** an `OPEN` `.handoff/HANDOFF.md` exists → ask the user: resume it, or overwrite with a new save? Otherwise empty → SAVE.

## SAVE (hand-off)

Capture the **delta** between what a fresh session auto-loads (CLAUDE.md, git state, file tree, memory) and what only *this* session knows: intent, decisions, dead-ends, the exact next action, and uncommitted-work state.

1. **Gather live state** — run, never guess:
   ```bash
   git rev-parse --show-toplevel 2>/dev/null; git branch --show-current 2>/dev/null; git rev-parse --short HEAD 2>/dev/null; git status -sb 2>/dev/null; git stash list 2>/dev/null; date -u +%Y-%m-%dT%H:%M:%SZ; hostname
   ```
2. **Synthesize** the conversation into the template sections (see [resources/handoff-template.md](resources/handoff-template.md)) — including the `▶ TO RESUME` block the template places right under the title, so the doc is self-resuming by a plain read. Be honest — write `none` for empty sections, never pad. **Uncommitted work is the most important section** — it is the only truly unrecoverable state.
3. **Write** `.handoff/HANDOFF.md` with `status: OPEN`, overwriting any previous current file.
4. **Archive** a timestamped copy to `.handoff/archive/HANDOFF-<UTC>.md`.
5. **Commit** — only if `.handoff/` is **not** gitignored (`git check-ignore -q .handoff` → skip commit if ignored). Stage named files only: `git add .handoff/HANDOFF.md .handoff/archive/HANDOFF-<UTC>.md && git commit -m "chore(handoff): <one-line goal>"`. Never `git add -A`. Never push.
6. **Report** (Hebrew to the user): saved + committed, the one-line goal, then: "בטוח ל-`/clear`. בסשן הבא הרץ `/handoff resume`." If switching machines is likely, remind to `git push` first — otherwise the handoff won't be there on the other machine.

Full steps, gitignore opt-out, non-git fallback, multi-machine reminder: [resources/save-protocol.md](resources/save-protocol.md).

## RESUME (hand-on)

The doc is **self-resuming**: it opens with a `▶ TO RESUME` block, so a fresh session can pick it up by *reading the file alone* — or just by you saying "continue from the handoff". This skill's resume mode adds exactly one thing on top: **disciplined drift-reconciliation against live git** before you trust a possibly-stale doc (git moves and files change between sessions, especially across machines). A handoff is a *hypothesis* about state — verify before acting.

1. **Read** `.handoff/HANDOFF.md`. Note `written`, `machine`, `branch`, `head`.
2. **Re-ground**:
   ```bash
   git branch --show-current 2>/dev/null; git rev-parse --short HEAD 2>/dev/null; git status -sb 2>/dev/null; git log --oneline -8 2>/dev/null
   ```
3. **Reconcile** doc vs reality — surface every drift:

   | Check | If it drifted |
   |-------|---------------|
   | branch == `branch`? | warn; ask before switching branches |
   | HEAD moved past `head`? | list the new commits, fold into the status board |
   | files marked uncommitted still dirty? | confirm; if now committed, say so |
   | `machine` ≠ current host? | tell the user to `git pull` first; compare `git status -sb` vs upstream |
   | named key files still exist? | flag any that moved or vanished |

4. **Restate** to the user (Hebrew): the goal, the status board, the single **next action**, any drift found, and any open questions awaiting their input.
5. **Continue** from the next action. Mark the handoff `status: RESUMED` (the SessionStart hook stops surfacing it once resumed).

Full reconciliation logic, stale-handoff playbook, and the optional SessionStart auto-detect hook: [resources/resume-protocol.md](resources/resume-protocol.md).

## Guidelines

- **Capture the delta, not the repo.** Don't re-describe what CLAUDE.md, git, or the file tree already say. Working memory only: intent, decisions, dead-ends, next action.
- **Uncommitted work is sacred.** It is the one unrecoverable thing. List every dirty file and what's in it. If the work is substantial and the user is leaving, suggest committing to a branch (per their git rules) rather than trusting the doc alone.
- **Honesty over completeness.** Empty section → `none`. A padded handoff erodes trust in the doc — and trust is the whole point.
- **Never push automatically.** Named files only, no `-A`. Push stays user-triggered.
- **Resume re-grounds first.** Verify before you act. A stale handoff acted on blindly is worse than no handoff.

## Resources

| Resource | What |
|----------|------|
| [handoff-template.md](resources/handoff-template.md) | The 10-section `HANDOFF.md` structure + YAML frontmatter |
| [save-protocol.md](resources/save-protocol.md) | Full SAVE steps, gitignore opt-out, non-git + multi-machine handling |
| [resume-protocol.md](resources/resume-protocol.md) | Full RESUME reconciliation + stale-handoff playbook + SessionStart hook |

## Related Skills

- `agentcraft-handoff` — AgentCraft-specific session transfer; this skill is project-agnostic and git-backed
- `using-git-worktrees` — when the uncommitted work should move to an isolated branch instead of riding in the doc

---
*v1.1.0 | 2026-06-04 | self-resuming doc + clean session boundaries: hand-off → /clear → hand-on*
