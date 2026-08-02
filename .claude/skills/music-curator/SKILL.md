---
name: music-curator
description: Build, audit and clean Apple Music playlists for the user. Use whenever they ask to make a playlist, add songs from a list or a screenshot, check whether a playlist matches its name, remove duplicates, split a playlist, replace live versions with studio ones, or undo a change to a playlist. Also use for "what's wrong with this playlist", "find these songs on Apple Music", "put this list into my library".
---

# Curating Apple Music playlists

The user talks about music. You do the searching, matching and checking, and
you never write to their library until they have seen the final result and
said yes.

## Before anything else

Check the session is alive:

```bash
applemusic-mcp status
```

If there is no user token, tell them to run `applemusic-mcp login --chrome`,
sign in in the window that opens, and come back. Do not try to sign in for
them and never handle their password.

## The commands

Reads — run these freely:

| | |
|---|---|
| `aimc playlists` | every playlist, marking the read-only Apple-curated ones |
| `aimc show "<name>"` | tracks with years and links |
| `aimc audit "<name>" [--era 1970-1989]` | duplicates, alternate versions, non-studio cuts, era outliers, one artist under two names |
| `aimc resolve <file>` | match a text list of `Artist — Title` lines against the catalog |
| `aimc history "<name>"` | saved snapshots, oldest first |

Writes — every one of these needs `--yes`, and every one saves a snapshot
before and after by itself:

| | |
|---|---|
| `aimc add "<name>" <catalog-id>… --yes` | |
| `aimc remove "<name>" <entry-id>… --yes` | entry ids, not catalog ids; get them from `show` |
| `aimc create "<name>" [--description "…"] <catalog-id>… --yes` | |
| `aimc restore "<name>" <snapshot-path> --yes` | put a playlist back as a snapshot recorded it |

## The rule that matters most

**Never write without showing the finished result first.**

Present the exact final tracklist — numbered, with artist, title, year and a
link per track — plus what is being added, what is being removed, and anything
you were unsure about. Then stop and wait. A general "yes, do it" earlier in
the conversation is not approval of a specific change.

For a new playlist, offer two or three names and two or three descriptions to
choose from, and make clear they can write their own instead.

## Matching is the hard part, and you are half of it

`aimc resolve` searches and scores, but it only knows the words it is given.
You supply what a search engine cannot:

- **Write the query in the language of the music.** Searching
  `Yumi Arai Nani mo Kikanaide` returns nothing; `荒井由実 何もきかないで`
  returns the song. This is not a Japanese quirk — always prefer the script
  and spelling the artist actually releases under.
- **Know when two names are one artist.** Yumi Arai and Yumi Matsutoya are the
  same person before and after marriage. Mariana Froes releases as Mari Froes.
  Apple files these separately and no amount of string comparison will join
  them.
- **Say what era is wanted** so `--era` can be passed. A playlist called
  "70-80s" is a claim that can be checked.

When a match comes back `review` rather than `high`, show the user the
candidates and let them pick. Never quietly promote a guess.

## Reading an audit

- `duplicate` — the identical recording twice, proven by ISRC. Always a defect.
- `versions` — one song in two different recordings, e.g. original plus a
  remix. Sometimes deliberate. Ask.
- `not-studio` — live, session, karaoke, remix or re-recorded. Before removing
  one, search for a studio original; it may not exist, and saying so is better
  than dropping the track.
- `wrong-era` — recorded outside the window the name claims.
- `split-artist` — one artist under two names. Not a defect in itself; it
  matters when deduplicating or judging what a playlist is really about.

## Things that do not work, so do not promise them

- **Playlist artwork cannot be set programmatically.** Not by the official API
  (Apple say so), not by the web player (its edit dialog has only name,
  description and visibility), not by AppleScript. You can generate a cover
  image; the user has to attach it themselves in the Music app.
- **Apple-curated playlists are read-only.** `aimc` refuses them.
- **There is no reordering endpoint.** Tracks append to the end. Putting a
  playlist in a specific order means removing everything and adding it back —
  which is destructive, so say so and get approval for the reordering itself.

## Undoing

Every write is snapshotted automatically, so "put it back how it was" always
has an answer:

```bash
aimc history "<name>"
aimc restore "<name>" <path-to-the-snapshot-before-the-change> --yes
```

Snapshots live under `~/.local/share/ai-music-curator/snapshots/`.
