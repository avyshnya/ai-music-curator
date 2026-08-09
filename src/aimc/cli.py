"""Command line interface.

This exists so that operations are executed the same way every time instead of
being improvised per request. Reads are free; every write snapshots first and
refuses to run without --yes.
"""

from __future__ import annotations

import json
import sys
from pathlib import Path

import typer

from . import snapshots
from .audit import audit as run_audit
from .library import Library, NotEditable, PlaylistNotFound
from .match import Query, best_matches
from .providers.apple import AppleMusic
from .providers.base import Playlist, PlaylistTrack
from .text import recording_year

app = typer.Typer(
    add_completion=False,
    help="Curate and clean Apple Music playlists. Reads are safe; "
         "writes always snapshot first and need --yes.",
)


def _lib() -> Library:
    return Library(AppleMusic())


def _die(msg: str) -> None:
    typer.secho(msg, fg=typer.colors.RED, err=True)
    raise typer.Exit(1)


def _preview(playlist, tracks, sample: int = 6) -> None:
    """Show enough of a playlist to recognise it before a destructive action.

    Name and count alone identify nothing in a large library; a few real
    tracks do. Prints the name, description, count, a sample of tracks, and a
    link to the first so it can be opened and checked.
    """
    typer.secho(f"{playlist.name} — {len(tracks)} tracks", bold=True)
    if playlist.description:
        typer.echo(f"  {playlist.description}")
    for t in tracks[:sample]:
        year = recording_year(t.song.isrc, t.song.release_date)
        typer.echo(f"    {t.song.artist} — {t.song.title}" + (f"  · {year}" if year else ""))
    if len(tracks) > sample:
        typer.echo(f"    … and {len(tracks) - sample} more")
    first_url = next((t.song.url for t in tracks if t.song.url), None)
    if first_url:
        typer.echo(f"  open: {first_url}")


def _parse_line(line: str) -> tuple[str, str] | None:
    """Split 'Artist — Title'. Any of four dashes, because sources vary."""
    for sep in (" — ", " – ", " - ", " | "):
        if sep in line:
            artist, title = (x.strip() for x in line.split(sep, 1))
            return artist, title
    return None


def _resolve_lines(raw: str, window):
    """Match each line against the catalog.

    Yields ``(line, parsed, match)`` where ``parsed`` is None when the line was
    not readable at all and ``match`` is None when nothing was found — two
    different failures that deserve two different messages.

    Shared by `resolve` and `pick` on purpose: two commands that answer "what
    does this list mean" must not be able to answer it differently.
    """
    am = AppleMusic()
    for line in [ln.strip() for ln in raw.splitlines() if ln.strip()]:
        parsed = _parse_line(line)
        if parsed is None:
            yield line, None, None
            continue
        artist, title = parsed
        hits = am.search_songs(f"{artist} {title}", limit=15)
        top = best_matches(hits, Query(artist=artist, title=title, era=window), limit=1)
        yield line, parsed, (top[0] if top else None)


def _era(era: str | None) -> tuple[int, int] | None:
    if not era:
        return None
    try:
        lo, hi = era.split("-")
        return int(lo), int(hi)
    except ValueError:
        _die(f"--era wants a range like 1970-1989, got {era!r}")


# --- reads ------------------------------------------------------------------


@app.command("playlists")
def cmd_playlists() -> None:
    """List every playlist in the library."""
    for p in _lib().playlists():
        lock = "" if p.editable else "  (read-only, Apple-curated)"
        typer.echo(f"{p.name}{lock}")


@app.command("show")
def cmd_show(
    playlist: str,
    links: bool = typer.Option(True, help="Include a link to each track."),
    html_out: Path = typer.Option(
        None, "--html", help="Write a self-contained HTML page here instead of printing."
    ),
) -> None:
    """Print a playlist, one track per line — or render it as an HTML page."""
    try:
        p, tracks = _lib().tracks(playlist)
    except PlaylistNotFound as e:
        _die(str(e))
    if html_out is not None:
        from .htmlview import render
        Path(html_out).write_text(render(p, tracks), encoding="utf-8")
        typer.echo(str(html_out))
        return
    typer.echo(f"{p.name} — {len(tracks)} tracks\n")
    for i, t in enumerate(tracks, 1):
        s = t.song
        year = recording_year(s.isrc, s.release_date)
        line = f"{i:3}. {s.artist} — {s.title}"
        if year:
            line += f"  · {year}"
        typer.echo(line)
        if links and s.url:
            typer.echo(f"     {s.url}")


@app.command("pick")
def cmd_pick(
    playlist: str = typer.Option(None, "--playlist", help="A playlist already in the library."),
    source: Path = typer.Option(
        None, "--from", help="File of 'Artist — Title' lines, or - for stdin."
    ),
    ids: str = typer.Option(None, "--ids", help="Comma-separated catalog ids."),
    era: str = typer.Option(None, help="Expected recording years, e.g. 1970-1989."),
    title: str = typer.Option("", "--title", help="Heading, for a list that is not a playlist."),
    description: str = typer.Option("", "--description", help="Sub-heading for that list."),
    out: Path = typer.Option(None, "--out", help="Write the answer here as JSON."),
    port: int = typer.Option(0, help="0 asks the OS for a free port."),
    timeout: float = typer.Option(
        900, help="Seconds to wait for the Done button. 0 waits indefinitely."
    ),
) -> None:
    """Put a list of songs in front of a person and return what they kept.

    This is how a tracklist gets shown — any tracklist, whether it is already a
    playlist or a set of candidates that does not exist yet. A list printed to a
    terminal cannot be listened to, and a list retyped into chat as numbers is a
    transcription error waiting to happen.

    Writes nothing. It reports a decision; carrying it out is another command.
    """
    from .picker import choose, selection

    given = [bool(playlist), source is not None, bool(ids)]
    if sum(given) != 1:
        _die("вибери рівно одне джерело: --playlist, --from або --ids")

    window = _era(era)
    in_library = False
    unresolved: list[str] = []

    if playlist:
        try:
            pl, tracks = _lib().tracks(playlist)
        except PlaylistNotFound as e:
            _die(str(e))
        in_library = True
    else:
        am = AppleMusic()
        songs = []
        if ids:
            for cid in [c.strip() for c in ids.split(",") if c.strip()]:
                song = am.get_song(cid)
                if song is None:
                    unresolved.append(cid)
                    continue
                songs.append(song)
        else:
            raw = sys.stdin.read() if str(source) == "-" else Path(source).read_text()
            for line, _parsed, match in _resolve_lines(raw, window):
                if match is None:
                    unresolved.append(line)
                    continue
                songs.append(match.song)
        if not songs:
            _die("нема чого показувати — жоден рядок не знайшовся в каталозі")
        tracks = [PlaylistTrack(song=s) for s in songs]
        pl = Playlist(id="proposal", name=title or "Обери треки", description=description)

    for u in unresolved:
        typer.secho(f"—  не знайдено: {u}", fg=typer.colors.YELLOW, err=True)

    kept = choose(pl, tracks, port=port, in_library=in_library,
                  timeout=timeout if timeout > 0 else None)
    if kept is None:
        # A closed tab is not a small answer, it is no answer. Saying so and
        # exiting non-zero keeps it from being read as "keep everything".
        typer.secho("відповіді не було — вікно закрили або вийшов час; нічого не змінено",
                    fg=typer.colors.YELLOW, err=True)
        raise typer.Exit(2)

    payload = selection(tracks, kept)
    payload["source"] = "playlist" if in_library else "list"
    payload["playlist"] = pl.name if in_library else None
    payload["unresolved"] = unresolved

    text = json.dumps(payload, ensure_ascii=False, indent=2)
    if out is not None:
        Path(out).write_text(text, encoding="utf-8")
        typer.echo(str(out))
    else:
        typer.echo(text)
    typer.secho(f"лишили {len(payload['kept'])} · прибрали {len(payload['dropped'])}",
                fg=typer.colors.GREEN, err=True)


@app.command("name")
def cmd_name(
    names: str = typer.Option(..., "--names", help="Suggested names, separated by |."),
    descriptions: str = typer.Option("", "--descriptions", help="Suggested descriptions, by |."),
    count: int = typer.Option(0, help="How many tracks are waiting, shown as context."),
    out: Path = typer.Option(None, "--out", help="Write the answer here as JSON."),
    port: int = typer.Option(0, help="0 asks the OS for a free port."),
    timeout: float = typer.Option(900, help="Seconds to wait. 0 waits indefinitely."),
) -> None:
    """Ask, in the browser, what a new playlist should be called.

    The name is part of the result, so it is chosen in the same place as the
    tracks rather than negotiated in chat afterwards.
    """
    from .naming import choose as choose_name

    opts = [n.strip() for n in names.split("|") if n.strip()]
    descs = [d.strip() for d in descriptions.split("|") if d.strip()]
    if not opts:
        _die("--names порожній")

    answer = choose_name(opts, descs, count, port=port,
                         timeout=timeout if timeout > 0 else None)
    if answer is None:
        typer.secho("назви не обрано — вікно закрили або вийшов час; нічого не створено",
                    fg=typer.colors.YELLOW, err=True)
        raise typer.Exit(2)

    chosen, desc = answer
    text = json.dumps({"name": chosen, "description": desc}, ensure_ascii=False, indent=2)
    if out is not None:
        Path(out).write_text(text, encoding="utf-8")
        typer.echo(str(out))
    else:
        typer.echo(text)


@app.command("stats")
def cmd_stats(
    playlist: str,
    html_out: Path = typer.Option(
        None, "--html", help="Write the dashboard as an HTML page here."
    ),
) -> None:
    """A quick dashboard: decades, top artists, non-studio count, year span."""
    from .stats import compute
    try:
        p, tracks = _lib().tracks(playlist)
    except PlaylistNotFound as e:
        _die(str(e))
    s = compute(tracks)
    if html_out is not None:
        from .htmlview import render_stats
        Path(html_out).write_text(render_stats(p, s), encoding="utf-8")
        typer.echo(str(html_out))
        return
    span = f"{s.year_min}–{s.year_max}" if s.year_min and s.year_max else "—"
    typer.echo(f"{p.name} — {s.total} tracks · {span} · {s.non_studio} non-studio\n")
    typer.echo("decades:")
    for k, v in s.decades:
        typer.echo(f"  {k}: {v}")
    typer.echo("top artists:")
    for k, v in s.top_artists:
        typer.echo(f"  {v:2}  {k}")


@app.command("version")
def cmd_version() -> None:
    """Which copy is installed, where it came from, and whether it is current."""
    from .selfupdate import check, installed_from, local_version
    repo = installed_from()
    if repo is None:
        typer.echo("встановлено не з теки (або встановлення не знайдено)")
        return
    typer.echo(f"версія: {local_version(repo) or '?'}")
    typer.echo(f"зібрано з: {repo}")
    typer.echo("одна команда aimc на систему — другої копії не буває")
    behind, msg = check(repo)
    typer.secho(msg, fg=typer.colors.YELLOW if behind else typer.colors.GREEN)
    if behind:
        typer.echo("оновитися: aimc update")


@app.command("update")
def cmd_update(
    yes: bool = typer.Option(False, "--yes", help="Required. Without it, only checks."),
) -> None:
    """Bring this copy up to date. Never happens on its own."""
    from .selfupdate import check, installed_from, update
    repo = installed_from()
    if repo is None:
        _die("не бачу, з якої теки встановлено — онови вручну")
    behind, msg = check(repo)
    typer.echo(msg)
    if not behind:
        return
    if not yes:
        typer.secho("перевірка — додай --yes щоб оновити", fg=typer.colors.YELLOW)
        return
    ok, out = update(repo)
    typer.secho(out, fg=typer.colors.GREEN if ok else typer.colors.RED)


@app.command("dashboard")
def cmd_dashboard(
    out: Path = typer.Option(None, "--out", help="Write the page here instead of a temp file."),
    open_it: bool = typer.Option(True, "--open/--no-open", help="Open in your browser."),
) -> None:
    """One page for everything you have: services, then detail for each."""
    import tempfile

    from .dashboard import render
    from .librarywide import overview, scan, scan_findings
    from .picker import open_in_browser

    lib = _lib()
    typer.echo("читаю бібліотеку — це один запит на трек, буде не миттєво…")
    s = scan(lib)
    data = [(overview(s, "Apple Music"), scan_findings(s))]
    path = Path(out) if out else Path(tempfile.gettempdir()) / "aimc-dashboard.html"
    path.write_text(render(data), encoding="utf-8")
    typer.echo(str(path))
    if open_it:
        open_in_browser(path.resolve().as_uri())


@app.command("cover")
def cmd_cover(
    playlist: str,
    subtitle: str = typer.Option("", help="Small line under the title."),
    palette: str = typer.Option("sunset", help="sunset · dusk · neon · warm"),
    shape: str = typer.Option("sun", help="sun · ring · peak"),
    out: Path = typer.Option(Path("covers"), help="Where to write the files."),
    open_it: bool = typer.Option(True, "--open/--no-open"),
) -> None:
    """Generate cover art for a playlist.

    Attaching it stays manual: Apple exposes no way to set playlist artwork.
    """
    from .cover import PALETTES, SHAPES, make
    from .picker import open_in_browser

    if palette not in PALETTES:
        _die(f"палітри {palette!r} немає — є: {', '.join(PALETTES)}")
    if shape not in SHAPES:
        _die(f"форми {shape!r} немає — є: {', '.join(SHAPES)}")
    svg_path, png_path = make(playlist, subtitle or "", Path(out), palette, shape)
    typer.echo(str(svg_path))
    if png_path:
        typer.echo(str(png_path))
        if open_it:
            open_in_browser(png_path.resolve().as_uri())
    else:
        typer.secho("PNG не зроблено — не знайдено Chrome для рендеру",
                    fg=typer.colors.YELLOW)
    typer.secho("Постав її руками: Music.app → правий клік на плейлісті → "
                "Edit Playlist → перетягни файл", fg=typer.colors.YELLOW)


@app.command("audit")
def cmd_audit(
    playlist: str,
    era: str = typer.Option(None, help="Expected recording years, e.g. 1970-1989."),
) -> None:
    """Report duplicates, alternate versions, non-studio cuts and era outliers."""
    try:
        p, tracks = _lib().tracks(playlist)
    except PlaylistNotFound as e:
        _die(str(e))
    findings = run_audit(tracks, _era(era))
    typer.echo(f"{p.name} — {len(tracks)} tracks, {len(findings)} findings\n")
    for f in findings:
        typer.echo(str(f))
    if not findings:
        typer.secho("nothing to fix", fg=typer.colors.GREEN)


@app.command("resolve")
def cmd_resolve(
    source: Path = typer.Argument(..., help="File of 'Artist — Title' lines, or - for stdin."),
    era: str = typer.Option(None, help="Expected recording years, e.g. 1970-1989."),
) -> None:
    """Match a text list against the catalog. Writes nothing."""
    raw = sys.stdin.read() if str(source) == "-" else Path(source).read_text()
    window = _era(era)
    found = missing = 0
    for line, parsed, m in _resolve_lines(raw, window):
        if parsed is None:
            typer.secho(f"?  cannot read: {line}", fg=typer.colors.YELLOW)
            continue
        if m is None:
            missing += 1
            artist, title = parsed
            typer.secho(f"—  {artist} — {title}: not found", fg=typer.colors.RED)
            continue
        found += 1
        colour = typer.colors.GREEN if m.confidence == "high" else typer.colors.YELLOW
        typer.secho(f"{m.confidence:>6}  {m.song.artist} — {m.song.title}", fg=colour)
        typer.echo(f"        {m.song.album} · {m.year} · {'; '.join(m.reasons)}")
        if m.song.url:
            typer.echo(f"        {m.song.url}")
    typer.echo(f"\n{found} matched, {missing} not found")


@app.command("history")
def cmd_history(playlist: str) -> None:
    """List saved snapshots for a playlist, oldest first."""
    try:
        paths = _lib().history(playlist)
    except PlaylistNotFound as e:
        _die(str(e))
    if not paths:
        typer.echo("no snapshots yet")
        return
    for p in paths:
        typer.echo(f"{snapshots.describe(p)}\n  {p}")


# --- writes -----------------------------------------------------------------


@app.command("snapshot")
def cmd_snapshot(playlist: str) -> None:
    """Save a copy of a playlist right now."""
    try:
        typer.echo(_lib().snapshot(playlist, "manual"))
    except PlaylistNotFound as e:
        _die(str(e))


@app.command("add")
def cmd_add(
    playlist: str,
    catalog_ids: list[str] = typer.Argument(...),
    yes: bool = typer.Option(False, "--yes", help="Required. Confirms the write."),
) -> None:
    """Add catalog tracks to a playlist."""
    if not yes:
        _die("refusing to write without --yes")
    try:
        _lib().add(playlist, catalog_ids)
    except (PlaylistNotFound, NotEditable) as e:
        _die(str(e))
    typer.secho(f"added {len(catalog_ids)} track(s)", fg=typer.colors.GREEN)


@app.command("remove")
def cmd_remove(
    playlist: str,
    entry_ids: list[str] = typer.Argument(..., help="Entry ids, not catalog ids."),
    yes: bool = typer.Option(False, "--yes", help="Required. Confirms the write."),
) -> None:
    """Remove entries from a playlist."""
    if not yes:
        _die("refusing to write without --yes")
    try:
        _lib().remove(playlist, entry_ids)
    except (PlaylistNotFound, NotEditable) as e:
        _die(str(e))
    typer.secho(f"removed {len(entry_ids)} entry(ies)", fg=typer.colors.GREEN)


@app.command("scan")
def cmd_scan() -> None:
    """Checks that only make sense across the whole library."""
    from .librarywide import scan, scan_findings
    s = scan(_lib())
    finds = scan_findings(s)
    typer.echo(f"{len(s.own)} своїх плейлістів, {len(finds)} зауважень\n")
    for f in finds:
        typer.echo(str(f))
    if not finds:
        typer.secho("бібліотека чиста", fg=typer.colors.GREEN)


@app.command("play")
def cmd_play(
    playlist: str,
    number: int = typer.Argument(..., help="Номер треку зі списку show."),
) -> None:
    """Play one track of a playlist in the Music app (macOS)."""
    from .nowplaying import NotSupported, play_track
    try:
        p, tracks = _lib().tracks(playlist)
    except PlaylistNotFound as e:
        _die(str(e))
    if not 1 <= number <= len(tracks):
        _die(f"у {p.name!r} треків {len(tracks)}, а просять #{number}")
    s = tracks[number - 1].song
    try:
        ok, msg = play_track(p.name, s.title, s.artist)
    except NotSupported as e:
        _die(str(e))
    typer.secho(f"{'▶' if ok else '×'} {msg}",
                fg=typer.colors.GREEN if ok else typer.colors.RED)


@app.command("create")
def cmd_create(
    name: str,
    description: str = typer.Option("", help="Playlist description."),
    catalog_ids: list[str] = typer.Argument(None),
    yes: bool = typer.Option(False, "--yes", help="Required. Confirms the write."),
) -> None:
    """Create a playlist, optionally filled."""
    if not yes:
        _die("refusing to write without --yes")
    pid = _lib().create(name, description, list(catalog_ids or []))
    typer.secho(f"created {name!r} ({pid})", fg=typer.colors.GREEN)


@app.command("rename")
def cmd_rename(
    playlist: str,
    new_name: str,
    yes: bool = typer.Option(False, "--yes", help="Required. Confirms the write."),
) -> None:
    """Give a playlist a different name. The tracks are untouched."""
    if not yes:
        _die("refusing to write without --yes")
    try:
        p = _lib().rename(playlist, new_name)
    except (PlaylistNotFound, NotEditable) as e:
        _die(str(e))
    typer.secho(f"renamed to {p.name!r}", fg=typer.colors.GREEN)


@app.command("merge")
def cmd_merge(
    source: str,
    target: str,
    dedupe: bool = typer.Option(True, help="Also drop repeats already in the target."),
    yes: bool = typer.Option(False, "--yes", help="Required. Without it, this is a dry run."),
) -> None:
    """Fold one playlist into another. Prints the plan; --yes carries it out."""
    lib = _lib()
    try:
        plan = lib.plan_merge(source, target, dedupe=dedupe)
    except (PlaylistNotFound, ValueError) as e:
        _die(str(e))

    typer.echo(f"{plan.source.name} -> {plan.target.name}\n")
    typer.echo(f"already in {plan.target.name}: {len(plan.already_there)}")
    typer.echo(f"to add: {len(plan.to_add)}")
    for t in plan.to_add:
        typer.echo(f"  + {t.song.artist} — {t.song.title}")
    if plan.duplicates:
        typer.echo(f"\nrepeats to drop from {plan.target.name}: {len(plan.duplicates)}")
        for t in plan.duplicates:
            typer.echo(f"  - {t.song.artist} — {t.song.title}")

    if plan.empty:
        typer.secho("\nnothing to do", fg=typer.colors.GREEN)
        return
    if not yes:
        typer.secho("\ndry run — pass --yes to carry this out", fg=typer.colors.YELLOW)
        return
    try:
        lib.apply_merge(plan)
    except NotEditable as e:
        _die(str(e))
    typer.secho("merged", fg=typer.colors.GREEN)


@app.command("dedupe")
def cmd_dedupe(
    playlist: str,
    yes: bool = typer.Option(False, "--yes", help="Required. Without it, this is a dry run."),
) -> None:
    """Drop repeated recordings, keeping the first of each."""
    lib = _lib()
    try:
        dupes = lib.duplicate_entries(playlist)
    except PlaylistNotFound as e:
        _die(str(e))
    if not dupes:
        typer.secho("no repeats", fg=typer.colors.GREEN)
        return
    for t in dupes:
        typer.echo(f"  - {t.song.artist} — {t.song.title}")
    if not yes:
        typer.secho(f"\n{len(dupes)} repeat(s) — pass --yes to remove", fg=typer.colors.YELLOW)
        return
    try:
        lib.dedupe(playlist)
    except NotEditable as e:
        _die(str(e))
    typer.secho(f"removed {len(dupes)}", fg=typer.colors.GREEN)


@app.command("delete")
def cmd_delete(
    playlist: str,
    yes: bool = typer.Option(False, "--yes", help="Required. Without it, this only previews."),
) -> None:
    """Delete a playlist. Snapshots it first so restore is still possible."""
    lib = _lib()
    try:
        p, tracks = lib.tracks(playlist)
    except PlaylistNotFound as e:
        _die(str(e))
    # Enough to recognise WHICH playlist this is. In a library of a hundred,
    # a name and a count identify nothing — the tracks do.
    _preview(p, tracks)
    if not yes:
        typer.secho("\npreview — pass --yes to delete", fg=typer.colors.YELLOW)
        return
    try:
        lib.delete(playlist)
    except NotEditable as e:
        _die(str(e))
    typer.secho(f"deleted {p.name!r}", fg=typer.colors.GREEN)


@app.command("restore")
def cmd_restore(
    playlist: str,
    snapshot: Path,
    yes: bool = typer.Option(False, "--yes", help="Required. Confirms the write."),
) -> None:
    """Put a playlist back exactly as a snapshot recorded it."""
    if not yes:
        _die("refusing to write without --yes")
    try:
        _lib().restore(playlist, snapshot)
    except (PlaylistNotFound, NotEditable) as e:
        _die(str(e))
    typer.secho("restored", fg=typer.colors.GREEN)


if __name__ == "__main__":
    app()
