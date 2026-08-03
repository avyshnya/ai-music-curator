"""Command line interface.

This exists so that operations are executed the same way every time instead of
being improvised per request. Reads are free; every write snapshots first and
refuses to run without --yes.
"""

from __future__ import annotations

import sys
from pathlib import Path

import typer

from . import snapshots
from .audit import audit as run_audit
from .library import Library, NotEditable, PlaylistNotFound
from .match import Query, best_matches
from .providers.apple import AppleMusic
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
    am = AppleMusic()
    found = missing = 0
    for line in [ln.strip() for ln in raw.splitlines() if ln.strip()]:
        for sep in (" — ", " – ", " - ", " | "):
            if sep in line:
                artist, title = (x.strip() for x in line.split(sep, 1))
                break
        else:
            typer.secho(f"?  cannot read: {line}", fg=typer.colors.YELLOW)
            continue
        hits = am.search_songs(f"{artist} {title}", limit=15)
        top = best_matches(hits, Query(artist=artist, title=title, era=window), limit=1)
        if not top:
            missing += 1
            typer.secho(f"—  {artist} — {title}: not found", fg=typer.colors.RED)
            continue
        m = top[0]
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
