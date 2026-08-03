# AI Music Curator

Build and clean streaming playlists on your own machine, with your own account,
by describing what you want in plain language. Apple Music today; the design
keeps other services one file away.

You talk to an AI assistant — the one this ships with is Claude Code — and it
does the searching, matching and checking, then shows you the finished playlist
and waits for your yes. There is a command line underneath, and you are welcome
to use it, but it is the machinery rather than the interface.

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
- An AI assistant that can run commands in a folder — [Claude Code](https://claude.com/claude-code)
  is what this is built for. Optional: the command line works on its own.
- No Apple Developer account, and no payment

## Install

One command. It installs what is missing, signs you in, and stops.

```bash
git clone https://github.com/avyshnya/ai-music-curator && cd ai-music-curator && ./setup.sh
```

A browser opens once so you can sign in to Apple Music yourself — the token
goes to your OS keychain, never into this repo, and is scoped to Apple Music
alone. It lasts about 180 days. Revoke it any time with `applemusic-mcp logout`.

Then open Claude Code in that folder and say what you want — it finds the
instructions it needs inside the repository. Nothing else to set up, no files to
manage. Another assistant, or no assistant at all, works too; see
[Which assistant](#which-assistant).

Running `./setup.sh` again is safe: each step checks whether it is already done.

### One copy, not two

`uv` keeps one tool per package name, so there is never a second `aimc` —
running setup from another folder repoints the existing command rather than
duplicating it. Setup notices that and asks before switching, so nobody has
their edits quietly stop taking effect.

```bash
aimc version
```

shows the version, the folder it was built from, and whether anything newer
exists upstream.

### Updates

Nothing updates itself. A tool holding a token to your music library should
not replace its own code between runs, so this one changes only when asked:

```bash
aimc update --yes
```

Without `--yes` it only reports whether an update exists. It refuses to run
when the checkout has uncommitted changes, since pulling would destroy them.

## Use

There is no workflow to learn and no file to manage. You say what you want the
way you would say it to a person who happens to have your whole library open in
front of them. Underneath, every request becomes the same handful of operations:
search the catalog, match text to real recordings, compare against what is
already there, and — only after you approve — write.

**Give it a list, get a playlist.** Paste twenty lines of `Artist — Title` from a
blog, drop in a screenshot of someone's story, or read them off a photographed
record sleeve. It searches each one, tells you which matched confidently and
which need your eye, and shows you the finished tracklist before it touches
anything. A list in Japanese, Portuguese or Cyrillic is not a problem — the
assistant writes the query in the script the artist actually releases under,
which is most of why the match succeeds where transfer services fail.

> Here's a list of songs I found. Make me a playlist.

**Ask for a playlist you can't quite specify.** You do not need the song names.
Describe the thing — a decade, a mood, a country, a feeling, "like that one but
calmer" — and let it propose a tracklist you edit by talking. Then ask it for a
few name and description options, and pick one.

> Build something like my Japan 70-80s playlist, but only the originals.
>
> Something for a long drive at night. Portuguese, nothing after 1990.

**Interrogate what you already have.** A playlist name is a claim, and claims can
be checked. It reads the era from the ISRC rather than the release date, so a
1976 single reissued in 2007 is still 1976, and a 2014 re-recording pretending to
be the original gets caught.

> Check this playlist — does it actually match its name?
>
> What's the oldest thing in here? Show me the decades.
>
> Is anything in my library duplicated across two playlists?

**Clean without losing anything.** Duplicates proven by ISRC, the same song in
two different recordings, live and karaoke cuts sitting where studio versions
should be, tracks recorded outside the era the name promises, one artist filed
under two names. It reports all of it, explains which are real defects and which
are judgement calls, and asks before removing anything. If a live cut is the only
version that exists, it says so instead of quietly dropping the track.

> Clean it up: kill the duplicates and anything that isn't from the era.
>
> Replace the live versions with studio ones where a studio one exists.
>
> Fold my second Japan playlist into the first and drop the overlap.

**Change your mind afterwards.** Every playlist is copied before and after each
change, automatically. Undo is a sentence, not a procedure.

> What did we change yesterday? Put it back the way it was.

**And the small things.** Play a track to check it is the right one before you
commit to it. Get a scrollable HTML page of a long tracklist, with links that
open in the Music app, instead of a wall of terminal output. Generate cover art
for a playlist. See one page for everything you own.

### Which assistant

Built and used with [Claude Code](https://claude.com/claude-code), which picks up
`.claude/skills/music-curator/SKILL.md` from this repository automatically — clone,
run setup, start talking. Nothing to configure.

Nothing about the design is Claude-specific, though. `aimc` is an ordinary
command-line program, and the skill file is ordinary Markdown describing when to
run what, so any assistant that can read a file and run a command in this folder
can drive it. [AGENTS.md](AGENTS.md) exists so the tools that follow that
convention — Codex CLI, Cursor, Gemini CLI and others — find those instructions
without being told. That path is untested; if you try it and it works, or
doesn't, [say so](https://github.com/avyshnya/ai-music-curator/issues).

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

### The command line, if you want it

Everything above is the assistant driving `aimc`, and you can drive it yourself
instead. `aimc --help` lists all of it; the shape is:

- **Look** — `playlists`, `show`, `stats`, `dashboard`, `scan`, `play`
- **Judge** — `audit` finds duplicates, alternate versions, non-studio cuts and
  era outliers; `resolve` matches a text list against the catalog. Neither
  writes anything.
- **Change** — `create`, `add`, `remove`, `merge`, `dedupe`, `delete`. Each one
  requires `--yes`; without it you get the plan and nothing happens.
- **Go back** — `snapshot`, `history`, `restore`
- **Odds and ends** — `cover`, `version`, `update`

Reads are always safe. Writes always snapshot first.

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

- [AGENTS.md](AGENTS.md) — what an AI assistant needs to know to operate this
  safely, and where the full instructions live
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
