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

## Skills

| Skill | What it does |
|-------|---------------|
| [handoff](skills/handoff/SKILL.md) | Captures session working-memory into `.handoff/HANDOFF.md` so a session can be cleared and resumed later — even on another machine — with zero context loss. |

## License

MIT — see [LICENSE](LICENSE).
