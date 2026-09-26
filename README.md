# AB-skills

A growing collection of [Claude Code](https://claude.com/claude-code) Agent Skills — built for real work, cleaned up, and shared here one at a time.

## Install

Copy a skill folder into your skills directory:

```bash
# global (all projects)
cp -r skills/<name> ~/.claude/skills/<name>

# project-local
cp -r skills/<name> .claude/skills/<name>
```

Claude Code hot-reloads skills — no restart needed.

## Plugins

Add the marketplace once, then install any plugin from it:

```
/plugin marketplace add AsiBi-lab/AB-skills
/plugin install <name>@ab-skills
```

| Plugin | What it does |
|--------|---------------|
| [plain-language-recap](plugins/plain-language-recap/README.md) | Every turn that changed files ends with a plain, complete recap you can read instead of the long message: what changed, how it was checked (with the real numbers), what is still open, what to decide. Jargon gets explained, failures are never dropped. Hebrew and English; Claude Code and Codex. |

## Skills

| Skill | What it does |
|-------|---------------|
| [handoff](skills/handoff/SKILL.md) | Captures session working-memory into `.handoff/HANDOFF.md` so a session can be cleared and resumed later — even on another machine — with zero context loss. |

## License

MIT — see [LICENSE](LICENSE).
