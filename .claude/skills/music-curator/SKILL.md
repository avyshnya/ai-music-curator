---
name: music-curator
description: Build, audit and clean Apple Music playlists for the user. Use whenever they ask to make a playlist, add songs from a list or a screenshot, check whether a playlist matches its name, remove duplicates, split a playlist, replace live versions with studio ones, or undo a change to a playlist. Also use for "what's wrong with this playlist", "find these songs on Apple Music", "put this list into my library".
---

# Curating Apple Music playlists

The user talks about music. You do the searching, matching and checking, and
you never write to their library until they have seen the final result in the
browser and pressed Done.

## Before anything else

Check the session is alive:

```bash
applemusic-mcp status
```

If there is no user token, tell them to run `applemusic-mcp login --chrome`,
sign in in the window that opens, and come back. Do not try to sign in for
them and never handle their password.

## The rule that overrides everything else

**Never put a list of songs in the conversation. Show it with `aimc pick`.**

Not a numbered list in chat. Not a markdown table. Not an HTML file you wrote
yourself and attached. Not "here are the tracks, tell me the numbers to drop".
Every list of songs — a playlist that exists, a set of candidates that does
not, the result of an audit, the tracks you propose removing — goes in front of
the user through `aimc pick`, which opens their real browser and hands their
answer back to you.

This is not a stylistic preference. A list in chat cannot be listened to, and
asking someone to read numbers back is a transcription error waiting to happen.
The page has cover art, a 30-second preview on every row, a checkbox on every
row, and a Done button that returns the selection directly.

If you catch yourself typing a tracklist into a reply, stop and run `aimc pick`
instead.

```bash
aimc pick --playlist "Japan 70-80s" --out /tmp/choice.json
aimc pick --from /tmp/candidates.txt --title "Learning the City" --out /tmp/choice.json
aimc pick --ids 1440840099,1561771400 --title "Candidates" --out /tmp/choice.json
```

The command blocks until Done is pressed — that is correct, let it wait. Run it
in the background and pick the result up when it finishes, so the user is not
staring at a frozen turn.

The JSON it writes is ready to use as-is:

| key | what it is for |
|---|---|
| `kept_catalog_ids` | feed straight to `create` or `add` |
| `dropped_entry_ids` | feed straight to `remove` |
| `kept` / `dropped` | full rows, if you need to talk about them |
| `unresolved` | lines that matched nothing — mention these |

**Exit code 2 means no answer** — the tab was closed or the wait ran out. It
does NOT mean "keep everything" and it does NOT mean "drop everything". Change
nothing, say the window was closed, and offer to open it again.

## Building a new playlist

Four steps, in this order. Do not skip to the end.

1. Work out the candidates yourself and write them to a file as
   `Artist — Title` lines. This is the part that needs your judgement — see
   *Matching* below.
2. `aimc pick --from <file> --title "<working title>"` — they hear the tracks
   and uncheck what they do not want.
3. `aimc name --names "A|B|C" --descriptions "1|2|3" --count <n>` — they choose
   what it is called, in the browser, from your suggestions or their own.
4. `aimc create "<chosen name>" --description "<chosen>" <kept ids…> --yes`

## Cleaning a playlist that exists

1. `aimc audit "<name>" [--era 1970-1989]` — find out what is actually wrong.
2. Tell them in prose what the audit found: how many duplicates, how many live
   cuts, how many outside the era. Counts and reasoning belong in chat.
3. `aimc pick --playlist "<name>"` — the tracks themselves go in the browser,
   pre-checked; they uncheck what should go.
4. `aimc remove "<name>" <dropped_entry_ids…> --yes`

## The commands

Reads — run these freely, they write nothing:

| | |
|---|---|
| `aimc playlists` | every playlist, marking the read-only Apple-curated ones |
| `aimc show "<name>"` | tracks as text. For YOU to read, never as the way to show a list to the user |
| `aimc stats "<name>"` | decades, top artists, non-studio count, year span |
| `aimc audit "<name>" [--era …]` | duplicates, alternate versions, non-studio cuts, era outliers, one artist under two names |
| `aimc scan` | the same checks across the whole library |
| `aimc resolve <file> [--era …]` | match a text list against the catalog and print the result |
| `aimc history "<name>"` | saved snapshots, oldest first |
| `aimc dashboard` | one browser page for the whole library |
| `aimc version` | which copy is installed and whether it is current |

Interactive — these open the user's browser and return their answer:

| | |
|---|---|
| `aimc pick …` | the only sanctioned way to show a list of songs |
| `aimc name --names "…\|…"` | choose a name and description for something about to be created |

Writes — every one needs `--yes`, and every one snapshots before and after:

| | |
|---|---|
| `aimc create "<name>" [--description "…"] <catalog-id>… --yes` | |
| `aimc add "<name>" <catalog-id>… --yes` | |
| `aimc remove "<name>" <entry-id>… --yes` | entry ids, not catalog ids — take them from `pick` |
| `aimc merge <source> <target> --yes` | without `--yes` it prints the plan |
| `aimc dedupe "<name>" --yes` | drop repeated recordings, keep the first |
| `aimc delete "<name>" --yes` | snapshots first, so restore still works |
| `aimc restore "<name>" <snapshot-path> --yes` | put it back as a snapshot recorded it |
| `aimc snapshot "<name>"` | save a copy right now |

Odds and ends: `aimc cover "<name>"` generates artwork (attaching it is manual —
see below), `aimc play "<name>" <n>` plays one track in Music.app, `aimc update
--yes` updates the tool itself.

## What still belongs in the conversation

Showing the list is the browser's job. Judgement is yours, and it goes in chat:

- what you found and what it means — "eleven of these are re-recordings, not the
  originals"
- where you had to decide something — an ambiguous artist, a title that exists
  in two versions, a track you could not find at all
- what you propose doing about it

Say those things. Then open the page.

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
- **Know when one title is two recordings.** Nubya Garcia's "Source" exists on
  a 2018 EP and as the 2020 album's title track — different songs. When a title
  could mean either, check, and say which one you took.
- **Say what era is wanted** so `--era` can be passed. A playlist called
  "70-80s" is a claim that can be checked.

When a match comes back `review` rather than `high`, put both candidates in the
page and let them pick. Never quietly promote a guess.

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
  description and visibility), not by AppleScript. `aimc cover` generates an
  image; the user attaches it themselves in the Music app.
- **Apple-curated playlists are read-only.** `aimc` refuses them.
- **There is no reordering endpoint.** Tracks append to the end. Putting a
  playlist in a specific order means removing everything and adding it back —
  which is destructive, so say so and get approval for the reordering itself.
- **Full playback only works for tracks already in the library.** In the picker
  page a candidate gets the 30-second preview only; AppleScript cannot see a
  catalog track the library does not hold.

## Undoing

Every write is snapshotted automatically, so "put it back how it was" always
has an answer:

```bash
aimc history "<name>"
aimc restore "<name>" <path-to-the-snapshot-before-the-change> --yes
```

Snapshots live under `~/.local/share/ai-music-curator/snapshots/`.
