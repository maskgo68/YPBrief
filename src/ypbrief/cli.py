from __future__ import annotations

from pathlib import Path

import click

from .archive import ArchiveService
from .config import load_settings
from .database import Database
from .daily import DailyDigestService
from .exporter import Exporter
from .llm import ConfigError
from .provider_config import create_provider_from_database
from .sources import SourceService
from .summarizer import Summarizer
from .transcripts import TranscriptFetcher
from .video_processor import VideoProcessor
from .youtube import YouTubeDataClient


@click.group()
@click.option("--env-file", default="key.env", show_default=True, help="Path to key.env")
@click.pass_context
def cli(ctx: click.Context, env_file: str) -> None:
    """YPBrief command line interface."""
    settings = load_settings(env_file)
    ctx.obj = {
        "settings": settings,
        "db": Database(settings.db_path),
    }


def _make_archive(ctx: click.Context) -> ArchiveService:
    settings = ctx.obj["settings"]
    if not settings.youtube_data_api_key:
        raise click.ClickException("YOUTUBE_DATA_API_KEY is required")
    db = ctx.obj["db"]
    db.initialize()
    return ArchiveService.from_api_key(db=db, youtube_api_key=settings.youtube_data_api_key)


def _make_summarizer(ctx: click.Context) -> Summarizer:
    db = ctx.obj["db"]
    db.initialize()
    settings = ctx.obj["settings"]
    try:
        provider = create_provider_from_database(db, settings)
    except ConfigError as exc:
        raise click.ClickException(str(exc)) from exc
    return Summarizer(db=db, provider=provider, settings=settings)


def _make_source_service(ctx: click.Context) -> SourceService:
    settings = ctx.obj["settings"]
    if not settings.youtube_data_api_key:
        raise click.ClickException("YOUTUBE_DATA_API_KEY is required")
    db = ctx.obj["db"]
    db.initialize()
    return SourceService(db=db, youtube=YouTubeDataClient(settings.youtube_data_api_key))


def _make_daily_service(ctx: click.Context) -> DailyDigestService:
    settings = ctx.obj["settings"]
    db = ctx.obj["db"]
    db.initialize()
    try:
        provider = create_provider_from_database(db, settings)
    except ConfigError as exc:
        raise click.ClickException(str(exc)) from exc
    return DailyDigestService(db=db, provider=provider, export_dir=settings.export_dir, settings=settings)


@cli.command("config")
@click.pass_context
def show_config(ctx: click.Context) -> None:
    settings = ctx.obj["settings"]
    click.echo(f"Provider: {settings.llm_provider}")
    click.echo(f"Database: {settings.db_path}")
    click.echo(f"Exports: {settings.export_dir}")


@cli.command("init-db")
@click.pass_context
def init_db(ctx: click.Context) -> None:
    settings = ctx.obj["settings"]
    db = ctx.obj["db"]
    db.initialize()
    click.echo(f"Initialized database: {settings.db_path}")


@cli.command("search")
@click.argument("query")
@click.option("--limit", default=10, show_default=True, type=int)
@click.pass_context
def search(ctx: click.Context, query: str, limit: int) -> None:
    db = ctx.obj["db"]
    db.initialize()
    results = db.search(query, limit=limit)
    if not results:
        click.echo("No matches found.")
        return
    for row in results:
        click.echo(f"{row['video_id']} | {row['video_title']} | {row['start_time']}")
        click.echo(row["text"])


@cli.group("channel")
def channel() -> None:
    """Manage saved channels."""


@channel.command("add")
@click.argument("channel_input")
@click.pass_context
def channel_add(ctx: click.Context, channel_input: str) -> None:
    archive = _make_archive(ctx)
    channel_info = archive.add_channel(channel_input)
    click.echo(f"Added channel: {channel_info.channel_name} ({channel_info.channel_id})")


@channel.command("list")
@click.pass_context
def channel_list(ctx: click.Context) -> None:
    db = ctx.obj["db"]
    db.initialize()
    channels = db.list_channels()
    if not channels:
        click.echo("No channels saved.")
        return
    for row in channels:
        click.echo(
            " | ".join(
                [
                    row["channel_id"],
                    row["channel_name"],
                    row.get("handle") or "",
                    row.get("uploads_playlist_id") or "",
                ]
            )
        )


@channel.command("delete")
@click.argument("channel_ref")
@click.pass_context
def channel_delete(ctx: click.Context, channel_ref: str) -> None:
    db = ctx.obj["db"]
    db.initialize()
    db.delete_channel(channel_ref)
    click.echo(f"Deleted channel: {channel_ref}")


@cli.group("source")
def source() -> None:
    """Manage channel, playlist, and video sources."""


@source.command("add")
@click.argument("source_input")
@click.option("--type", "source_type", type=click.Choice(["channel", "playlist", "video"]))
@click.option("--name")
@click.option("--display-name")
@click.option("--disabled", is_flag=True)
@click.pass_context
def source_add(
    ctx: click.Context,
    source_input: str,
    source_type: str | None,
    name: str | None,
    display_name: str | None,
    disabled: bool,
) -> None:
    service = _make_source_service(ctx)
    row = service.add(
        source_input,
        source_type=source_type,
        name=name,
        display_name=display_name,
        enabled=not disabled,
    )
    click.echo(f"Added source: {row['source_name']} ({row['source_type']}:{row['youtube_id']})")


@source.command("list")
@click.option("--enabled-only", is_flag=True)
@click.pass_context
def source_list(ctx: click.Context, enabled_only: bool) -> None:
    service = _make_source_service(ctx)
    rows = service.list(enabled_only=True) if enabled_only else service.list()
    if not rows:
        click.echo("No sources saved.")
        return
    for row in rows:
        click.echo(
            " | ".join(
                [
                    str(row["source_id"]),
                    row["source_type"],
                    "enabled" if row["enabled"] else "disabled",
                    row["source_name"],
                    row["youtube_id"],
                ]
            )
        )


@source.command("enable")
@click.argument("source_id", type=int)
@click.pass_context
def source_enable(ctx: click.Context, source_id: int) -> None:
    service = _make_source_service(ctx)
    service.enable(source_id)
    click.echo(f"Enabled source: {source_id}")


@source.command("disable")
@click.argument("source_id", type=int)
@click.pass_context
def source_disable(ctx: click.Context, source_id: int) -> None:
    service = _make_source_service(ctx)
    service.disable(source_id)
    click.echo(f"Disabled source: {source_id}")


@source.command("delete")
@click.argument("source_id", type=int)
@click.pass_context
def source_delete(ctx: click.Context, source_id: int) -> None:
    service = _make_source_service(ctx)
    service.delete(source_id)
    click.echo(f"Deleted source: {source_id}")


@source.command("import")
@click.argument("path", type=click.Path(exists=True, dir_okay=False, path_type=Path))
@click.pass_context
def source_import(ctx: click.Context, path: Path) -> None:
    service = _make_source_service(ctx)
    count = service.import_yaml(path)
    click.echo(f"Imported sources: {count}")


@source.command("export")
@click.argument("path", type=click.Path(dir_okay=False, path_type=Path))
@click.pass_context
def source_export(ctx: click.Context, path: Path) -> None:
    service = _make_source_service(ctx)
    service.export_yaml(path)
    click.echo(f"Exported sources: {path}")


@cli.command("update")
@click.option("--channel", "channel_ref", required=True, help="Channel id, name, or handle to update")
@click.option("--language", "languages", multiple=True, help="Preferred transcript language")
@click.pass_context
def update(ctx: click.Context, channel_ref: str, languages: tuple[str, ...]) -> None:
    archive = _make_archive(ctx)
    stats = archive.update_channel(channel_ref, languages=list(languages) or None)
    click.echo(
        " ".join(
            [
                f"videos_seen={stats['videos_seen']}",
                f"transcripts_saved={stats['transcripts_saved']}",
                f"failed={stats['failed']}",
            ]
        )
    )


@cli.group("video")
def video() -> None:
    """Process individual videos."""


@video.command("process")
@click.argument("video_input")
@click.pass_context
def process_video(ctx: click.Context, video_input: str) -> None:
    settings = ctx.obj["settings"]
    if not settings.youtube_data_api_key:
        raise click.ClickException("YOUTUBE_DATA_API_KEY is required")
    db = ctx.obj["db"]
    db.initialize()
    try:
        provider = create_provider_from_database(db, settings)
    except ConfigError as exc:
        raise click.ClickException(str(exc)) from exc

    processor = VideoProcessor.from_api_key(
        db=db,
        youtube_api_key=settings.youtube_data_api_key,
        transcripts=TranscriptFetcher.from_settings(settings),
        provider=provider,
        export_dir=settings.export_dir,
        settings=settings,
    )
    result = processor.process(video_input)
    click.echo(f"Processed video: {result.video_id}")
    click.echo(f"Saved summary: {result.summary_id}")
    click.echo(f"Exported source: {result.source_vtt}")
    click.echo(f"Exported transcript: {result.transcript_md}")
    click.echo(f"Exported summary: {result.summary_md}")


@cli.group("summarize")
def summarize() -> None:
    """Generate summaries from cleaned transcripts."""


@summarize.command("video")
@click.argument("video_id")
@click.pass_context
def summarize_video(ctx: click.Context, video_id: str) -> None:
    summarizer = _make_summarizer(ctx)
    summary_id = summarizer.summarize_video(video_id)
    click.echo(f"Saved summary: {summary_id}")


@cli.group("daily")
def daily() -> None:
    """Generate daily digest outputs."""


@daily.command("summarize")
@click.option("--date", "run_date", required=True, help="Daily digest date, YYYY-MM-DD")
@click.option("--video-id", "video_ids", multiple=True, required=True, help="Video id to include")
@click.pass_context
def daily_summarize(ctx: click.Context, run_date: str, video_ids: tuple[str, ...]) -> None:
    service = _make_daily_service(ctx)
    result = service.summarize_videos(list(video_ids), run_date=run_date)
    click.echo(f"Saved daily summary: {result.summary_id}")
    click.echo(f"Videos included: {result.video_count}")
    click.echo(f"Exported daily summary: {result.daily_summary}")
    click.echo(f"Exported videos manifest: {result.videos_manifest}")
    click.echo(f"Exported failed manifest: {result.failed_manifest}")


@cli.group("export")
def export() -> None:
    """Export local transcripts and summaries."""


@export.command("transcript")
@click.option("--video-id", required=True)
@click.option("--format", "file_format", default="md", show_default=True, type=click.Choice(["md", "txt"]))
@click.pass_context
def export_transcript(ctx: click.Context, video_id: str, file_format: str) -> None:
    settings = ctx.obj["settings"]
    db = ctx.obj["db"]
    db.initialize()
    output = Exporter(db, settings.export_dir).export_transcript(video_id, file_format=file_format)
    click.echo(f"Exported source: {output.source}")
    click.echo(f"Exported transcript: {output.transcript}")


@export.command("summary")
@click.option("--video-id", required=True)
@click.pass_context
def export_summary(ctx: click.Context, video_id: str) -> None:
    settings = ctx.obj["settings"]
    db = ctx.obj["db"]
    db.initialize()
    output = Exporter(db, settings.export_dir).export_summary(video_id)
    click.echo(f"Exported summary: {output}")
