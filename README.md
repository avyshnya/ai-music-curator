# AI Music Curator

Build and clean streaming playlists from the command line, on your own machine,
with your own account. Apple Music today; the design keeps other services one
file away.

**Status: early.** The matching layer and its tests are real; the CLI is being
built. Nothing here writes to your library without showing you the exact result
first.

## Why this exists

Transferring a text list of songs into Apple Music is a solved problem on paper
and a broken one in practice. Services like Soundiiz and TuneMyMusic will do it,
but they need an account, they upload your library to their servers, and they
charge past a trial. Worse, they quietly fail at matching: a real transfer of a
Japanese 70s–80s list produced a playlist where only one of five requested
tracks was correct, one was a 2014 cover credited to the wrong artist, and three
were silently missing — after which Apple's "add similar" suggestions filled the
gap with 2018 J-pop.

The transport is not the hard part. **Matching is.** That is what this project
is about.

## What is different here

**Era is read from the ISRC, not the release date.** Apple reports the date of
the release it happens to be serving, so a 1976 single reissued digitally in
2007 reports 2007. Its ISRC still says 76. Filtering an era on `releaseDate`
silently keeps re-recordings and drops originals.

**Word boundaries are ignored when comparing.** The catalog lists
`Natsu wo Akirame te` where your source says `Natsu wo Akiramete`, and both
`Hatsu Koi` and `Hatsukoi` exist. Where a space falls is not information.

**Long romanised vowels fold, but only as a fallback.** `Jouzu` / `Jōzu` /
`Jozu` are one song. That fold also collapses `good` onto `god`, so it never
runs by default — it is a weaker second-pass key, scored below an exact match.

**Titles split on `/`.** Japanese releases are listed as
`English Title / Romaji Title` — `The Wind / Futou Wo Wataru Kaze`. A query for
either half has to match.

**The artist is verified, never assumed.** Searching a title alone returns
covers by other people. A search for `何もきかないで` returns Lynyrd Skynyrd,
matched through an English translation of the title.

## Requirements

- macOS, Linux or Windows
- Python 3.11+
- An active Apple Music subscription
- No Apple Developer account, and no payment

## Install

One command. It installs what is missing, signs you in, and stops.

```bash
git clone https://github.com/avyshnya/ai-music-curator && cd ai-music-curator && ./setup.sh
```

A browser opens once so you can sign in to Apple Music yourself — the token
goes to your OS keychain, never into this repo, and is scoped to Apple Music
alone. It lasts about 180 days. Revoke it any time with `applemusic-mcp logout`.

Then open Claude Code in that folder and say what you want. Nothing else to set
up, no files to manage.

Running `./setup.sh` again is safe: each step checks whether it is already done.

## Use

You talk; the tool works. There is no workflow to learn and no file to manage.

> Here's a list of songs I found. Make me a playlist.

> Build something like my Japan 70-80s playlist, but only the originals.

> Check this playlist — does it actually match its name?

> Clean it up: kill the duplicates and anything that isn't from the era.

Ask in whatever words you'd use with a person. Underneath, each of those becomes
the same handful of operations: search the catalog, match text to real
recordings, compare against what's already there, and — only after you approve —
write.

### Nothing is written until you say so

Before anything reaches your library you see the finished thing: the exact
tracklist in order, what's being added, what's being removed, and where a match
was uncertain. For a new playlist you also get a few suggested names and
descriptions to pick from, or you type your own. Then it writes.

### History you don't have to think about

Every playlist this tool touches is copied before and after each change,
automatically. You never save, export or name a file. Ask what changed, or to
put a playlist back the way it was, and the answer already exists — Apple Music
itself keeps no history at all, so this is the only undo there is.

Copies live under `~/.local/share/ai-music-curator/snapshots/`, outside the
repository, because they are your listening data and not source code.

Under the hood a playlist is a text file identified by ISRCs rather than
Apple-specific ids, which is what makes the history diffable and what will let
the same playlist target another service later. You are not expected to care.

### For scripting

There is a CLI underneath if you want one — `aimc --help`. It is the machinery,
not the point.

## Security

The Apple Music user token lives in your OS keychain (or a `0600` file where no
keychain exists) and is scoped to Apple Music — it gives no access to your Apple
ID, payments, or any other Apple service. Revoke it with
`applemusic-mcp logout`, or by changing your Apple ID password.

Transport to Apple Music is [applemusic-mcp](https://github.com/epheterson/applemusic-mcp)
(MIT), pinned to an exact version. It is never auto-updated; each version bump
is preceded by reading the upstream diff, and the result is recorded in
[deps.lock.md](deps.lock.md) along with the original security audit.

## What this does not do

- **Set playlist artwork.** Not possible programmatically. The official API does
  not support it (confirmed by Apple on the developer forums), the web player's
  edit dialog offers only name, description and visibility, and Music.app
  declares an `artwork` element for playlists in AppleScript that does not
  work. This tool can generate cover images; putting one on a playlist is a
  manual step in Apple's own app.
- **Play music.** Use a music player.
- **Download anything.**

## Project docs

- [DEVLOG.md](DEVLOG.md) — why the code is the way it is: every matching rule
  traced back to the real failure that motivated it
- [BACKLOG.md](BACKLOG.md) — what was tried and does not work, with evidence
- [deps.lock.md](deps.lock.md) — the pinned dependency and its security audit
- [Issues](https://github.com/avyshnya/ai-music-curator/issues) — what is next

## Licence

MIT. This is an unofficial project, not affiliated with Apple, for use with your
own account.

## Developing

```bash
PYTHONPATH=src uv run --with pytest --with typer pytest -q
uv run --with ruff ruff check src tests
```

Reinstalling the CLI from a working copy needs `--no-cache`:

```bash
uv tool install --force --no-cache .
```

Without it `uv` can serve a cached wheel and you will test the previous
version while believing you are testing the current one. This bites hardest
when the checkout lives on a cloud-synced folder, where modification times are
not always what a build tool expects.
