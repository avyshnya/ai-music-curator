# Instructions for AI assistants

This repository is a tool you operate on the user's behalf, not only a codebase
you edit. Two different jobs, and it is worth knowing which one you are doing.

## Curating the user's music

Read [.claude/skills/music-curator/SKILL.md](.claude/skills/music-curator/SKILL.md)
and follow it. It lists every command, which ones are safe to run freely, and how
to read an audit. Claude Code loads it automatically; other assistants should read
it as their first step when the user mentions playlists, songs or their library.

Three rules from that file matter enough to repeat here:

- **Never write to the library until the user has seen the exact final result and
  said yes.** A general "go ahead" earlier in the conversation is not approval of
  a specific change. Every write command requires `--yes` for this reason.
- **Never handle the user's Apple ID or password.** If `applemusic-mcp status`
  shows no user token, tell them to run `applemusic-mcp login --chrome` and sign
  in themselves.
- **Do not promise what does not work** — playlist artwork cannot be set
  programmatically, Apple-curated playlists are read-only, and there is no
  reordering endpoint. The skill file explains each.

## Working on the code

```bash
PYTHONPATH=src uv run --with pytest --with typer pytest -q
uv run --with ruff ruff check src tests
```

Reinstalling the CLI from a working copy needs `--no-cache`, or `uv` may serve a
cached wheel and you will test the previous version believing it is the current
one:

```bash
uv tool install --force --no-cache .
```

[DEVLOG.md](DEVLOG.md) records why each matching rule exists, traced to the real
failure that motivated it. [BACKLOG.md](BACKLOG.md) records what was tried and
does not work, with evidence — read it before proposing something that looks
obviously missing. The Apple Music dependency is pinned deliberately; see
[deps.lock.md](deps.lock.md) and do not widen the constraint without reading the
upstream diff.
