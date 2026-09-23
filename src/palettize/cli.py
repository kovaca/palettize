"""Command-line interface for Palettize, built with Typer."""

from __future__ import annotations

import json as json_module
import random
import sys
import traceback
from pathlib import Path
from typing import Any

import typer
from rich.console import Console
from rich.panel import Panel
from rich.table import Table
from rich.text import Text

from palettize import __version__, analysis, render
from palettize.core import Colormap, InputColor
from palettize.exceptions import (
    ColormapFileError,
    ExporterOptionError,
    InvalidColorError,
    PalettizeError,
    PresetNotFoundError,
)
from palettize.exporters import (
    exporter_file_extension,
    get_exporter,
    list_available_exporters,
)
from palettize.presets import get_preset_info, list_categories, search_presets
from palettize.scaling import get_scaler_by_name


class ExitCodes:
    """Process exit codes, stable across releases so scripts can branch on them."""

    SUCCESS = 0
    USAGE_ERROR = 1
    INVALID_COLOR = 2
    EXPORT_ERROR = 3
    RESOURCE_NOT_FOUND = 4
    UNEXPECTED_ERROR = 5


class AppState:
    """Global flags collected by the root callback."""

    def __init__(self) -> None:
        self.verbose_level = 0


app_state = AppState()

app = typer.Typer(
    name="palettize",
    help="🎨 Generate, inspect, and export colormaps for data visualization and mapping.",
    rich_markup_mode="markdown",
    no_args_is_help=True,
)
# highlight=False disables Rich's repr auto-highlighter, which would otherwise
# bold stray numbers and parentheses inside prose, table cells, and version strings.
console = Console(color_system="truecolor", highlight=False)
err_console = Console(stderr=True, color_system="truecolor", highlight=False)


# ----------------------------------------------------------------------
# Error reporting
# ----------------------------------------------------------------------


def _fail(message: str, code: int) -> typer.Exit:
    """Print an error to stderr and build the matching Exit for the caller to raise."""
    err_console.print(f"[bold red]Error:[/bold red] {message}")
    if app_state.verbose_level > 1:
        err_console.print(
            Panel(
                traceback.format_exc(),
                title="[bold yellow]Traceback[/bold yellow]",
                border_style="red",
            )
        )
    return typer.Exit(code=code)


def _parse_range(value: str, param_name: str) -> tuple[float, float]:
    """Parse a ``"min,max"`` string into an ordered pair of floats."""
    parts = value.split(",")
    if len(parts) != 2:
        raise typer.BadParameter(
            f"{param_name} must be two comma-separated numbers (e.g. '0,1'). Got: '{value}'"
        )
    try:
        low, high = float(parts[0].strip()), float(parts[1].strip())
    except ValueError:
        raise typer.BadParameter(
            f"{param_name} must be two comma-separated numbers (e.g. '0,1'). Got: '{value}'"
        ) from None
    if low > high:
        raise typer.BadParameter(f"{param_name}: min ({low}) cannot be greater than max ({high}).")
    return low, high


# ----------------------------------------------------------------------
# Colormap resolution
# ----------------------------------------------------------------------


def resolve_colormap(
    source: str | None = None,
    colors: list[str] | None = None,
    *,
    interpolation_space: str = "oklch",
    cut: str = "0,1",
    reverse: bool = False,
    steps: int | None = None,
    name: str | None = None,
) -> Colormap:
    """Build a colormap from whichever source the user supplied.

    ``source`` may be a preset name (``viridis``) or a path to a colormap file
    saved by ``palettize create --save``. Exactly one of ``source`` or ``colors``
    must be given.

    Raises:
        typer.Exit: With the appropriate exit code, after reporting the problem.
    """
    if source and colors:
        raise _fail(
            "A colormap name and --colors are mutually exclusive; pick one.",
            ExitCodes.USAGE_ERROR,
        )
    if not source and not colors:
        raise _fail(
            "Provide a preset name, a saved colormap file, or --colors.",
            ExitCodes.USAGE_ERROR,
        )

    cut_start, cut_end = _parse_range(cut, "--cut")
    if not (0.0 <= cut_start <= 1.0 and 0.0 <= cut_end <= 1.0):
        raise _fail("--cut values must be between 0.0 and 1.0.", ExitCodes.USAGE_ERROR)

    try:
        if colors:
            expanded: list[InputColor] = [
                color.strip() for item in colors for color in item.split(",") if color.strip()
            ]
            if not expanded:
                raise _fail("No valid colors provided in --colors.", ExitCodes.USAGE_ERROR)
            colormap = Colormap.from_list(
                expanded, name=name, interpolation_space=interpolation_space
            )
        elif source is None:
            # Unreachable: the guards above require a source or colors.
            raise _fail("No colormap source given.", ExitCodes.USAGE_ERROR)
        elif _looks_like_path(source):
            colormap = Colormap.load(source)
            colormap.interpolation_space = interpolation_space
        else:
            colormap = Colormap.from_preset(source, interpolation_space=interpolation_space)
    except ColormapFileError as e:
        raise _fail(str(e), ExitCodes.RESOURCE_NOT_FOUND) from e
    except PresetNotFoundError as e:
        raise _fail(str(e), ExitCodes.RESOURCE_NOT_FOUND) from e
    except InvalidColorError as e:
        raise _fail(str(e), ExitCodes.INVALID_COLOR) from e
    except ValueError as e:
        raise _fail(str(e), ExitCodes.INVALID_COLOR) from e
    except Exception as e:
        raise _fail(
            f"Unexpected problem building the colormap: {e}", ExitCodes.UNEXPECTED_ERROR
        ) from e

    # Order matters: cut selects a window, then reverse mirrors it, then steps
    # bands the result. Reversing after cutting is what users expect from
    # "the top 80% of viridis, reversed".
    if (cut_start, cut_end) != (0.0, 1.0):
        colormap = colormap.cut(cut_start, cut_end)
    if reverse:
        colormap = colormap.reversed()
    if steps:
        colormap = colormap.quantized(steps)
    if name:
        colormap.name = name
    return colormap


def _looks_like_path(source: str | None) -> bool:
    """Whether ``source`` should be read as a colormap file rather than a preset name."""
    if not source:
        return False
    if source.endswith(".json") or source.endswith(".palettize.json"):
        return True
    return ("/" in source or "\\" in source) and Path(source).exists()


# ----------------------------------------------------------------------
# Global options
# ----------------------------------------------------------------------


def version_callback(value: bool) -> None:
    if value:
        console.print(f"Palettize CLI Version: {__version__}")
        raise typer.Exit(code=ExitCodes.SUCCESS)


def verbosity_callback(value: int) -> int:
    app_state.verbose_level = value
    return value


def verbose_option() -> Any:
    """A per-command ``-v`` so the flag works on either side of the subcommand.

    Typer binds options on the root callback only before the subcommand name,
    but `palettize create -v` is what people actually type.
    """
    return typer.Option(
        0,
        "--verbose",
        "-v",
        count=True,
        help="Increase output verbosity. Use -vv for tracebacks.",
        show_default=False,
    )


def _apply_verbosity(level: int) -> None:
    """Merge a command-level ``-v`` with any given before the subcommand."""
    app_state.verbose_level = max(app_state.verbose_level, level)


@app.callback()
def global_options(
    version: bool | None = typer.Option(
        None,
        "--version",
        "-V",
        callback=version_callback,
        is_eager=True,
        help="Show the application's version and exit.",
    ),
    verbose: int | None = typer.Option(
        0,
        "--verbose",
        "-v",
        count=True,
        callback=verbosity_callback,
        help="Increase output verbosity. Use -vv for tracebacks.",
        show_default=False,
    ),
) -> None:
    """
    Palettize: generate, inspect, and export colormaps from the command line.

    Commands that take a colormap accept a preset name (`viridis`), a saved
    colormap file (`./my-map.json`), or `--colors "red,white,blue"`.
    """


# ----------------------------------------------------------------------
# show
# ----------------------------------------------------------------------


@app.command()
def show(
    colormap_name: str | None = typer.Argument(
        None, help="Preset name (e.g. 'viridis') or path to a saved colormap JSON file."
    ),
    colors: list[str] | None = typer.Option(
        None, "--colors", "-c", help="Build a colormap from these colors instead."
    ),
    width: int | None = typer.Option(
        None, "--width", "-w", help="Preview width. Defaults to the terminal width."
    ),
    height: int = typer.Option(1, "--height", "-H", min=1, help="Preview height in lines."),
    steps: int | None = typer.Option(
        None, "--steps", "-n", min=1, help="Render as this many discrete bands."
    ),
    reverse: bool = typer.Option(False, "--reverse", "-r", help="Reverse the colormap."),
    interpolation_space: str = typer.Option(
        "oklch", "--space", "-s", help="Color space used for interpolation."
    ),
    cut: str = typer.Option("0,1", "--cut", help="Use only this sub-segment, e.g. '0.2,0.8'."),
    name: str | None = typer.Option(None, "--name", help="Display name for the colormap."),
    output: Path | None = typer.Option(
        None,
        "--output",
        "-o",
        help="Write a preview image instead of drawing in the terminal (.png or .svg).",
    ),
    hex_values: bool = typer.Option(False, "--hex", help="Also print the hex value of each step."),
    verbose: int = verbose_option(),
) -> None:
    """Preview a colormap in the terminal, or write it to an image file."""
    _apply_verbosity(verbose)
    colormap = resolve_colormap(
        colormap_name,
        colors,
        interpolation_space=interpolation_space,
        cut=cut,
        reverse=reverse,
        steps=steps,
        name=name,
    )

    if output is not None:
        try:
            written = render.write_image(
                colormap, output, width=width or 512, height=max(height, 32)
            )
        except (OSError, ValueError) as e:
            raise _fail(str(e), ExitCodes.EXPORT_ERROR) from e
        console.print(f"[green]Wrote preview to[/green] {written}")
        return

    actual_width = max(10, width if width is not None else (console.width or 80))
    if app_state.verbose_level > 0:
        console.print(f"Preview of '{colormap.name or 'custom'}' ({actual_width}x{height}):")
    console.print(render.terminal_swatch(colormap, actual_width, height))

    if hex_values:
        count = steps or 8
        for position, color in zip(
            analysis.sample_positions(count),
            colormap.hex_colors(count),
            strict=True,
        ):
            console.print(
                Text(render.BLOCK * 2, style=color),
                Text(f" {position:.3f}  {color}"),
                sep="",
            )


# ----------------------------------------------------------------------
# analyze
# ----------------------------------------------------------------------


@app.command()
def analyze(
    colormap_name: str | None = typer.Argument(
        None, help="Preset name (e.g. 'viridis') or path to a saved colormap JSON file."
    ),
    colors: list[str] | None = typer.Option(
        None, "--colors", "-c", help="Analyze a colormap built from these colors."
    ),
    samples: int = typer.Option(
        analysis.DEFAULT_SAMPLES, "--samples", min=2, help="Number of samples to take."
    ),
    reverse: bool = typer.Option(False, "--reverse", "-r", help="Reverse the colormap."),
    cut: str = typer.Option("0,1", "--cut", help="Analyze only this sub-segment."),
    interpolation_space: str = typer.Option(
        "oklch", "--space", "-s", help="Color space used for interpolation."
    ),
    as_json: bool = typer.Option(
        False, "--json", help="Emit machine-readable JSON instead of a report."
    ),
    strict: bool = typer.Option(False, "--strict", help="Exit non-zero if any warnings are found."),
    verbose: int = verbose_option(),
) -> None:
    """Check a colormap's lightness, perceptual uniformity, and colorblind safety."""
    _apply_verbosity(verbose)
    colormap = resolve_colormap(
        colormap_name,
        colors,
        interpolation_space=interpolation_space,
        cut=cut,
        reverse=reverse,
    )
    report = analysis.analyze(colormap, samples=samples)

    if as_json:
        sys.stdout.write(json_module.dumps(report.to_dict(), indent=2) + "\n")
    else:
        _print_analysis(colormap, report)

    if strict and report.warnings:
        raise typer.Exit(code=ExitCodes.EXPORT_ERROR)


def _print_analysis(colormap: Colormap, report: analysis.ColormapAnalysis) -> None:
    """Render an analysis as a human-readable terminal report."""
    total_width = console.width or 80
    # Reserve room for the label, retention percentage, verdict, and cell padding
    # that sit beside each strip, so nothing gets truncated on a narrow terminal.
    strip_width = max(12, min(64, total_width - 40))

    console.print()
    console.print(f"[bold]{report.name}[/bold]  [dim]{len(colormap)} stops[/dim]")
    console.print()

    strips = Table(show_header=False, box=None, padding=(0, 1, 0, 2))
    strips.add_column(style="dim", no_wrap=True)
    strips.add_column(no_wrap=True)
    strips.add_column(justify="right", no_wrap=True)
    strips.add_column(no_wrap=True)

    strips.add_row("original", render.terminal_swatch(colormap, strip_width), "", "")
    for cvd in report.cvd:
        simulated = Colormap.from_list(list(cvd.colors))
        strips.add_row(
            cvd.key,
            render.terminal_swatch(simulated, strip_width),
            f"{cvd.worst_retention:.0%} kept",
            "[green]ok[/green]" if cvd.is_distinguishable else "[red]degraded[/red]",
        )
    console.print(strips)
    console.print()

    stats = Table(show_header=False, box=None, padding=(0, 2, 0, 2))
    stats.add_column(style="dim", no_wrap=True)
    stats.add_column()
    stats.add_row("lightness", f"{report.lightness.shape}, {report.lightness.direction}")
    stats.add_row("", analysis.sparkline(report.lightness.values))
    stats.add_row("range", f"{report.lightness.span:.0f} of 100")
    stats.add_row(
        "uniformity",
        f"variation {report.uniformity.coefficient_of_variation:.2f} "
        f"({'even' if report.uniformity.is_uniform else 'uneven'})",
    )
    stats.add_row(
        "step size",
        f"mean {report.uniformity.mean:.1f} ΔE, "
        f"range {report.uniformity.minimum:.1f}-{report.uniformity.maximum:.1f}",
    )
    console.print(stats)
    console.print()

    if report.notes or report.warnings:
        findings = Table(show_header=False, box=None, padding=(0, 2, 0, 2))
        findings.add_column(no_wrap=True, width=4)
        findings.add_column(overflow="fold")
        for note in report.notes:
            findings.add_row("[blue]note[/blue]", note)
        for warning in report.warnings:
            findings.add_row("[yellow]warn[/yellow]", warning)
        console.print(findings)
    if not report.warnings:
        console.print("  [green]No problems detected.[/green]")
    console.print()


# ----------------------------------------------------------------------
# create
# ----------------------------------------------------------------------


@app.command()
def create(
    colormap_name: str | None = typer.Argument(
        None, help="Preset name (e.g. 'viridis') or path to a saved colormap JSON file."
    ),
    colors: list[str] | None = typer.Option(
        None, "--colors", "-c", help="Build a colormap from these colors instead."
    ),
    formats: list[str] = typer.Option(
        [],
        "--format",
        "-f",
        help="Export format identifiers, e.g. 'gdal,qgis'. See `palettize formats`.",
    ),
    output: str | None = typer.Option(
        None,
        "--output",
        "-o",
        help="Output path pattern. Supports {name}, {format}, {ext}. Defaults to stdout.",
    ),
    save: Path | None = typer.Option(
        None,
        "--save",
        help="Also save the colormap itself as a reusable Palettize JSON file.",
    ),
    domain: str = typer.Option(
        "0,1", "--domain", "-d", help="Data domain for scaling, e.g. '0,100'."
    ),
    scale: str = typer.Option(
        "linear", "--scale", help="Scaling type: linear, power, sqrt, log, symlog."
    ),
    scale_exponent: float | None = typer.Option(
        None, "--scale-exponent", help="Exponent for the 'power' scale."
    ),
    scale_log_base: float | None = typer.Option(
        None, "--scale-log-base", help="Log base for 'log'/'symlog' scales."
    ),
    scale_symlog_linthresh: float | None = typer.Option(
        None, "--scale-symlog-linthresh", help="Linear threshold for the 'symlog' scale."
    ),
    steps: int | None = typer.Option(
        7, "--steps", "-n", min=2, help="Number of color steps in the output."
    ),
    precision: int | None = typer.Option(
        None, "--precision", min=0, help="Decimal places for numeric values."
    ),
    reverse: bool = typer.Option(False, "--reverse", "-r", help="Reverse the colormap."),
    interpolation_space: str = typer.Option(
        "oklch", "--space", "-s", help="Color space used for interpolation."
    ),
    cut: str = typer.Option("0,1", "--cut", help="Use only this sub-segment, e.g. '0.2,0.8'."),
    name: str | None = typer.Option(
        None, "--name", help="Name for the colormap, used in output and file naming."
    ),
    option: list[str] | None = typer.Option(
        None,
        "--option",
        "-O",
        help="Format-specific option, e.g. 'gdal:nodata=false'. Repeatable.",
    ),
    verbose: int = verbose_option(),
) -> None:
    """Export a colormap to one or more file formats."""
    _apply_verbosity(verbose)
    colormap = resolve_colormap(
        colormap_name,
        colors,
        interpolation_space=interpolation_space,
        cut=cut,
        reverse=reverse,
        name=name,
    )

    if save is not None:
        try:
            written = colormap.save(save)
        except OSError as e:
            raise _fail(f"Could not save colormap: {e}", ExitCodes.EXPORT_ERROR) from e
        if app_state.verbose_level > 0 or not formats:
            console.print(f"[green]Saved colormap to[/green] {written}")

    if not formats:
        if save is None:
            raise _fail(
                "Nothing to do: pass --format to export, or --save to store the colormap.",
                ExitCodes.USAGE_ERROR,
            )
        return

    domain_min, domain_max = _parse_range(domain, "--domain")
    scaler = _build_scaler(
        scale,
        domain_min,
        domain_max,
        scale_exponent,
        scale_log_base,
        scale_symlog_linthresh,
    )

    namespaced_options, explicit_keys = _parse_exporter_options(option or [])

    requested = [f.strip() for item in formats for f in item.split(",") if f.strip()]
    if not requested:
        raise _fail("No valid format specified with --format.", ExitCodes.USAGE_ERROR)

    base_name = colormap.name or colormap_name or "custom_map"
    succeeded = True

    for fmt in requested:
        exporter = get_exporter(fmt)
        if exporter is None:
            err_console.print(
                f"[bold red]Error:[/bold red] Exporter '{fmt}' not found. "
                f"Run 'palettize formats' to see the available formats."
            )
            succeeded = False
            continue

        if app_state.verbose_level > 0:
            console.print(f"Exporting to [cyan]{fmt}[/cyan]...")

        final_options: dict[str, Any] = dict(namespaced_options.get("_global", {}))
        final_options.update(namespaced_options.get(fmt, {}))
        if steps:
            final_options.setdefault("num_colors", steps)
        if precision is not None:
            final_options.setdefault("precision", precision)
        final_options.setdefault("name", base_name)
        final_options["scale_type"] = scale
        final_options.setdefault("verbose", app_state.verbose_level > 0)

        # Global `-O key=value` applies to every format, so a typo there must
        # warn even when that format has no namespaced options of its own.
        supplied_keys = explicit_keys.get(fmt, set()) | explicit_keys.get("_global", set())
        unknown = exporter.options.unknown(supplied_keys)
        if unknown:
            err_console.print(
                f"[yellow]Warning:[/yellow] '{fmt}' does not accept "
                f"{', '.join(repr(k) for k in unknown)}. "
                f"Run 'palettize formats {fmt}' to see its options."
            )

        try:
            payload = exporter.export(
                colormap, scaler, domain_min, domain_max, options=final_options
            )
        except ExporterOptionError as e:
            err_console.print(f"[bold red]Error in '{fmt}' options:[/bold red] {e}")
            succeeded = False
            continue
        except Exception as e:
            err_console.print(f"[bold red]Failed to export to {fmt}:[/bold red] {e}")
            if app_state.verbose_level > 1:
                err_console.print(
                    Panel(
                        traceback.format_exc(),
                        title="[bold yellow]Traceback[/bold yellow]",
                        border_style="red",
                    )
                )
            succeeded = False
            continue

        if output:
            extension = exporter.default_file_extension or "txt"
            path = Path(output.format(name=base_name, format=fmt, ext=extension))
            try:
                path.parent.mkdir(parents=True, exist_ok=True)
                path.write_text(payload, encoding="utf-8")
            except OSError as e:
                err_console.print(f"[bold red]Could not write {path}:[/bold red] {e}")
                succeeded = False
                continue
            if app_state.verbose_level > 0:
                console.print(f"[green]Wrote {path}[/green]")
        else:
            # Write raw, bypassing Rich: exporter payloads contain brackets that
            # Rich would parse as markup, and ANSI codes would corrupt redirects.
            sys.stdout.write(payload)
            if not payload.endswith("\n"):
                sys.stdout.write("\n")

    if not succeeded:
        raise typer.Exit(code=ExitCodes.EXPORT_ERROR)

    if app_state.verbose_level > 0:
        console.print("[bold green]Export complete.[/bold green]")


def _build_scaler(
    scale: str,
    domain_min: float,
    domain_max: float,
    exponent: float | None,
    log_base: float | None,
    linthresh: float | None,
) -> Any:
    """Instantiate the requested scaling function, reporting missing arguments."""
    kwargs: dict[str, Any] = {}
    scale_type = scale

    if scale == "power":
        if exponent is None:
            raise _fail(
                "--scale-exponent is required when using --scale power.",
                ExitCodes.USAGE_ERROR,
            )
        kwargs["exponent"] = exponent
    elif scale == "sqrt":
        scale_type = "power"
        kwargs["exponent"] = 0.5

    if scale in ("log", "symlog") and log_base is not None:
        kwargs["base"] = log_base
    if scale == "symlog":
        if linthresh is None:
            raise _fail(
                "--scale-symlog-linthresh is required when using --scale symlog.",
                ExitCodes.USAGE_ERROR,
            )
        kwargs["linthresh"] = linthresh

    try:
        return get_scaler_by_name(
            name=scale_type, domain_min=domain_min, domain_max=domain_max, **kwargs
        )
    except ValueError as e:
        raise _fail(f"Could not create scaler: {e}", ExitCodes.USAGE_ERROR) from e


def _parse_exporter_options(
    options: list[str],
) -> tuple[dict[str, dict[str, Any]], dict[str, set[str]]]:
    """Split ``-O`` flags into per-exporter option dicts.

    Returns the parsed options plus, for each exporter, the set of keys the user
    named explicitly, so unknown keys can be reported without flagging the
    options the CLI itself injects.
    """
    parsed: dict[str, dict[str, Any]] = {"_global": {}}
    explicit: dict[str, set[str]] = {}

    for entry in options:
        if "=" not in entry:
            raise _fail(
                f"Invalid --option '{entry}'. Use 'key=value' or 'exporter:key=value'.",
                ExitCodes.USAGE_ERROR,
            )
        key_part, value = entry.split("=", 1)
        if ":" in key_part:
            exporter_key, option_key = key_part.split(":", 1)
        else:
            exporter_key, option_key = "_global", key_part
        parsed.setdefault(exporter_key, {})[option_key] = value
        explicit.setdefault(exporter_key, set()).add(option_key)

    # Global options apply to every exporter, so include them in each key set.
    global_keys = explicit.get("_global", set())
    for exporter_key in list(explicit):
        if exporter_key != "_global":
            explicit[exporter_key] |= global_keys
    return parsed, explicit


# ----------------------------------------------------------------------
# formats
# ----------------------------------------------------------------------


@app.command()
def formats(
    identifier: str | None = typer.Argument(
        None, help="Show the options accepted by a single format."
    ),
) -> None:
    """List export formats, or detail the options accepted by one of them."""
    if identifier is None:
        table = Table(title="Export formats", header_style="bold magenta")
        table.add_column("Format", style="cyan")
        table.add_column("Description")
        table.add_column("Ext", style="dim")
        for key, label in sorted(list_available_exporters().items()):
            table.add_row(key, label, exporter_file_extension(key) or "")
        console.print(table)
        console.print("\n[dim]Run 'palettize formats <format>' to see a format's options.[/dim]")
        return

    exporter = get_exporter(identifier)
    if exporter is None:
        raise _fail(
            f"Unknown format '{identifier}'. Run 'palettize formats' to see the list.",
            ExitCodes.RESOURCE_NOT_FOUND,
        )

    console.print()
    console.print(f"[bold cyan]{exporter.identifier}[/bold cyan] — {exporter.name}")
    extension = exporter.default_file_extension
    if extension:
        console.print(f"[dim]Default extension: .{extension}[/dim]")
    if exporter.uses_scaler:
        note = "Places colors at data values: both --domain and --scale change the output."
    elif exporter.uses_domain:
        note = "Records --domain in the output; --scale applies only under some options."
    else:
        note = "Emits a plain color list; --domain and --scale do not apply."
    console.print(f"[dim]{note}[/dim]")
    console.print()

    if not len(exporter.options):
        console.print("This format accepts no options.")
        return

    table = Table(header_style="bold magenta")
    table.add_column("Option", style="cyan")
    table.add_column("Type")
    table.add_column("Default", style="dim")
    table.add_column("Description")
    for opt in exporter.options:
        table.add_row(opt.name, opt.type_label, opt.default_label, opt.help)
    console.print(table)
    console.print(
        f"\n[dim]Use with: palettize create <colormap> -f {exporter.identifier} "
        f"-O {exporter.identifier}:<option>=<value>[/dim]"
    )


# ----------------------------------------------------------------------
# list
# ----------------------------------------------------------------------

list_app = typer.Typer(name="list", help="List available presets or export formats.")
app.add_typer(list_app)


@list_app.command(name="presets")
def list_presets_command(
    search: str | None = typer.Option(
        None, "--search", "-q", help="Only show presets whose name contains this text."
    ),
    category: str | None = typer.Option(
        None,
        "--category",
        help="Filter by category: sequential, diverging, cyclic, qualitative, miscellaneous.",
    ),
    namespace: str | None = typer.Option(
        None, "--namespace", help="Filter by publisher, e.g. 'colorbrewer'."
    ),
    swatch: bool = typer.Option(
        False, "--swatch", help="Draw a gradient preview beside each preset."
    ),
    limit: int = typer.Option(
        50, "--limit", min=0, help="Maximum rows to show. Use 0 for no limit."
    ),
) -> None:
    """List the built-in and `cmap` preset palettes."""
    results = search_presets(query=search, category=category, namespace=namespace)

    if not results:
        filters = ", ".join(
            f"{label}={value!r}"
            for label, value in (
                ("search", search),
                ("category", category),
                ("namespace", namespace),
            )
            if value
        )
        console.print(f"No presets matched {filters or 'the given filters'}.")
        if category and category not in list_categories():
            console.print(f"[dim]Known categories: {', '.join(list_categories())}[/dim]")
        return

    shown = results if limit == 0 else results[:limit]

    table = Table(title=f"Presets ({len(results)} matching)", header_style="bold magenta")
    table.add_column("Name", style="cyan", no_wrap=True)
    table.add_column("Category")
    table.add_column("Source", style="dim")
    if swatch:
        table.add_column("Preview")

    for info in shown:
        row = [info.name, info.category, info.namespace]
        if swatch:
            try:
                preview = render.terminal_swatch(Colormap.from_preset(info.name), width=24)
            except PalettizeError:
                preview = Text("unavailable", style="dim")
            row.append(preview)  # type: ignore[arg-type]
        table.add_row(*row)

    console.print(table)
    if limit and len(results) > limit:
        console.print(
            f"[dim]Showing {limit} of {len(results)}. "
            f"Use --limit 0 to see them all, or narrow with --search.[/dim]"
        )


@list_app.command(name="exporters")
def list_exporters_command() -> None:
    """List the available export formats. Alias for `palettize formats`."""
    formats(identifier=None)


@list_app.command(name="categories")
def list_categories_command() -> None:
    """List the preset categories available for `--category`."""
    for name in list_categories():
        count = len(search_presets(category=name))
        console.print(f"  [cyan]{name}[/cyan]  [dim]{count} presets[/dim]")


# ----------------------------------------------------------------------
# info
# ----------------------------------------------------------------------

ASCII_ART_FULL = """
███████╗  █████╗ ██╗     ███████╗████████╗████████╗██╗███████╗███████╗
 ██╔══██╗██╔══██╗██║     ██╔════╝╚══██╔══╝╚══██╔══╝██║╚══███╔╝██╔════╝
 ██████╔╝███████║██║     █████╗     ██║      ██║   ██║  ███╔╝ █████╗
 ██╔═══╝ ██╔══██║██║     ██╔══╝     ██║      ██║   ██║ ███╔╝  ██╔══╝
 ██║     ██║  ██║███████╗███████╗   ██║      ██║   ██║███████╗███████╗
 ╚═╝     ╚═╝  ╚═╝╚══════╝╚══════╝   ╚═╝      ╚═╝   ╚═╝╚══════╝╚══════╝
"""

ASCII_ART_COMPACT = """
▄▀▀▄ ▄▀▀▄ █   ▄▀▀ ▀▀█▀▀ ▀▀█▀▀ █ ▀▀█ ▄▀▀
█▀▀  █▀▀█ █   █▀▀   █     █   █  ▄▀ █▀▀
█    █  █ █▄▄ █▄▄   █     █   █ █▄▄ █▄▄
"""

COLOR_QUOTES = [
    '"Color is a power which directly influences the soul." — Wassily Kandinsky',
    '"The purest and most thoughtful minds are those which love color the most." — John Ruskin',
    '"Color is the keyboard, the eyes are the harmonies, the soul is the piano." — Wassily Kandinsky',
    "\"I found I could say things with color and shapes that I couldn't say any other way.\" — Georgia O'Keeffe",
    '"Color does not add a pleasant quality to design — it reinforces it." — Pierre Bonnard',
    '"Mere color, unspoiled by meaning, can speak to the soul in a thousand ways." — Oscar Wilde',
    '"Colors are the smiles of nature." — Leigh Hunt',
    '"The whole world, as we experience it visually, comes to us through the mystic realm of color." — Hans Hofmann',
    '"Color is my daylong obsession, joy, and torment." — Claude Monet',
    '"Why do two colors, put one next to the other, sing?" — Pablo Picasso',
    '"There is no blue without yellow and without orange." — Vincent van Gogh',
    '"In nature, light creates the color. In the picture, color creates the light." — Hans Hofmann',
    '"What we see is filtered sensory information; perception is shaped by our expectations." — Norwood Russell Hanson',
    '"By convention there is color... but in reality there are atoms and the void." — Edward Robert Harrison',
    '"Life is about using the whole box of crayons." — RuPaul',
    '"Color! What a deep and mysterious language, the language of dreams." — Paul Gauguin',
]

BANNER_COLORMAPS = [
    "turbo",
    "viridis",
    "magma",
    "inferno",
    "plasma",
    "cividis",
    "mako",
    "rocket",
]


def _gradient_text(text: str, colormap: Colormap) -> Text:
    """Color each character by its column, so the gradient runs left to right."""
    lines = text.split("\n")
    max_len = max((len(line) for line in lines), default=1)
    # Sample once per column rather than once per character.
    palette = colormap.hex_colors(max(2, max_len))

    result = Text()
    for index, line in enumerate(lines):
        if index:
            result.append("\n")
        for column, char in enumerate(line):
            if char == " ":
                result.append(" ")
            else:
                result.append(char, style=palette[min(column, len(palette) - 1)])
    return result


@app.command()
def info() -> None:
    """Show version, links, and a colorful banner."""
    width = console.width or 80
    art = ASCII_ART_FULL if width >= 72 else ASCII_ART_COMPACT
    colormap = Colormap.from_preset(random.choice(BANNER_COLORMAPS))

    console.print(_gradient_text(art.strip(), colormap))
    console.print()
    console.print(f"[bold]Version:[/bold] {__version__}")
    console.print(
        "[bold]Description:[/bold] Generate, inspect, and export colormaps for data "
        "visualization and mapping applications."
    )
    console.print()
    console.print(
        "[bold]GitHub:[/bold] [link=https://github.com/kovaca/palettize]"
        "https://github.com/kovaca/palettize[/link]"
    )
    console.print(
        "[bold]Docs:[/bold] [link=https://kovaca.github.io/palettize]"
        "https://kovaca.github.io/palettize[/link]"
    )
    console.print()
    console.print(f"[dim italic]{random.choice(COLOR_QUOTES)}[/dim italic]")


@app.command(name="presets")
def preset_info_command(
    name: str = typer.Argument(..., help="Preset name to describe."),
) -> None:
    """Show metadata and a preview for a single preset."""
    info_data = get_preset_info(name)
    if info_data is None:
        raise _fail(
            f"Preset '{name}' not found. Try 'palettize list presets --search {name}'.",
            ExitCodes.RESOURCE_NOT_FOUND,
        )

    colormap = Colormap.from_preset(name)
    console.print()
    console.print(f"[bold cyan]{info_data.name}[/bold cyan]")
    console.print(render.terminal_swatch(colormap, min(64, max(16, (console.width or 80) - 4))))
    console.print()

    table = Table(show_header=False, box=None, padding=(0, 2, 0, 0))
    table.add_column(style="dim")
    table.add_column()
    table.add_row("category", info_data.category)
    table.add_row("namespace", info_data.namespace or "—")
    table.add_row("stops", str(len(colormap)))
    if info_data.license:
        table.add_row("license", info_data.license)
    if info_data.source:
        table.add_row("source", info_data.source)
    console.print(table)
    console.print()
