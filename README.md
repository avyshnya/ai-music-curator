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

```bash
uv tool install ai-music-curator
```

Sign in once — this reads the Apple Music session from a browser you log into
yourself. The token is stored in your OS keychain, never in this repo, and is
scoped to Apple Music only.

```bash
applemusic-mcp login --chrome
```

## Use

```bash
aimc pull "Japan 70-80s" -o playlists/japan.yaml
```

```bash
aimc resolve tracklist.txt
```

`resolve` reads a plain list of `artist — title` lines, searches the catalog and
prints what it found, what it is unsure about, and what it could not find. It
writes nothing.

## Playlists as files

A playlist is described by a YAML file that lives in git next to the code, with
ISRCs as the track identity. That buys four things the streaming service does
not give you: you review the tracklist before anything is written, `git diff`
shows exactly what changed and when, a deleted playlist is one command from
being restored, and the same file can target a different service later because
an ISRC is not Apple-specific.

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

## Licence

MIT. This is an unofficial project, not affiliated with Apple, for use with your
own account.
