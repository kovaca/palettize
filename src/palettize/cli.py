# src/palettize/cli.py

"""Command-Line Interface for Palettize, built with Typer."""

from typing import Optional, List, Tuple, Dict, Any
import typer
from rich.console import Console
from rich.table import Table
from palettize.exporters import list_available_exporters, get_exporter
from palettize.presets import list_available_presets
from palettize.core import Colormap
from palettize.exceptions import PresetNotFoundError, InvalidColorError
from palettize.scaling import get_scaler_by_name
from palettize import __version__
import traceback
from rich.panel import Panel
from pathlib import Path


# --- Helper function to parse comma-separated min,max string ---
def parse_min_max_str(value_str: str, param_name: str) -> Tuple[float, float]:
    """Parses a string like 'min,max' into a tuple of two floats."""
    try:
        min_val_str, max_val_str = value_str.split(",")
        min_val = float(min_val_str.strip())
        max_val = float(max_val_str.strip())
        if min_val > max_val:
            raise typer.BadParameter(
                f"{param_name}: min value ({min_val}) cannot be greater than max value ({max_val})."
            )
        return min_val, max_val
    except ValueError:
        raise typer.BadParameter(
            f"{param_name}: Must be two comma-separated numbers (e.g., '0,1'). Got: '{value_str}'"
        )


# --- CLI Exit Codes ---
class ExitCodes:
    SUCCESS = 0
    USAGE_ERROR = 1
    INVALID_COLOR = 2
    EXPORT_ERROR = 3
    RESOURCE_NOT_FOUND = 4
    UNEXPECTED_ERROR = 5


# Application state for global options
class AppState:
    def __init__(self):
        self.verbose_level = 0
        self.quiet = False


app_state = AppState()

app = typer.Typer(
    name="palettize",
    help="🎨 A Python utility and CLI tool for generating, previewing, and exporting color maps.",
    add_completion=False,
    rich_markup_mode="markdown",
)

console = Console(color_system="truecolor")


# --- Global Options Callback ---
def version_callback(value: bool):
    if value:
        console.print(f"Palettize CLI Version: {__version__}")
        raise typer.Exit(code=ExitCodes.SUCCESS)


def verbosity_callback(ctx: typer.Context, param: typer.CallbackParam, value: int):
    app_state.verbose_level = value
    return value


def quiet_callback(ctx: typer.Context, param: typer.CallbackParam, value: bool):
    app_state.quiet = value
    return value


@app.callback()
def global_options(
    ctx: typer.Context,
    version: Optional[bool] = typer.Option(
        None,
        "--version",
        "-V",
        callback=version_callback,
        is_eager=True,
        help="Show the application's version and exit.",
    ),
    verbose: Optional[int] = typer.Option(
        0,
        "--verbose",
        "-v",
        count=True,
        callback=verbosity_callback,
        help="Increase output verbosity. Use -vv for more detail.",
        show_default=False,
    ),
    quiet: Optional[bool] = typer.Option(
        False,
        "--quiet",
        "-q",
        callback=quiet_callback,
        is_flag=True,
        help="Suppress all informational output; only errors will be shown.",
        show_default=False,
    ),
):
    """
    Palettize: Generate, preview, and export colormaps from the command line.
    Use `[COMMAND] --help` for more information on a specific command.
    """
    pass


# --- Core Helper Functions ---


def _create_colormap_from_options(
    preset: Optional[str],
    colors: Optional[List[str]],
    cut: str,
    interpolation_space: str,
    name: Optional[str],
) -> Colormap:
    """Helper to create a Colormap object from common CLI options."""
    if colors and preset:
        console.print(
            "[bold red]Error:[/bold red] --colors and a preset name are mutually exclusive.",
            style="bold red",
        )
        raise typer.Exit(code=ExitCodes.USAGE_ERROR)

    if not colors and not preset:
        console.print(
            "[bold red]Error:[/bold red] Either --colors or a preset name must be provided.",
            style="bold red",
        )
        raise typer.Exit(code=ExitCodes.USAGE_ERROR)

    try:
        cut_min, cut_max = parse_min_max_str(cut, "--cut")
        if not (0.0 <= cut_min <= 1.0 and 0.0 <= cut_max <= 1.0):
            raise typer.BadParameter("--cut values must be between 0.0 and 1.0.")
    except typer.BadParameter as e:
        console.print(f"[bold red]Error:[/bold red] {e.message}", style="bold red")
        raise typer.Exit(code=ExitCodes.USAGE_ERROR)

    actual_colors_list: Optional[List[str]] = None
    if colors:
        actual_colors_list = []
        for color_item in colors:
            actual_colors_list.extend(
                [c.strip() for c in color_item.split(",") if c.strip()]
            )
        if not actual_colors_list:
            console.print(
                "[bold red]Error:[/bold red] No valid colors provided in the --colors option.",
                style="bold red",
            )
            raise typer.Exit(code=ExitCodes.USAGE_ERROR)

    try:
        if preset:
            colormap_obj = Colormap.from_preset(
                preset_name=preset,
                interpolation_space=interpolation_space,
                cut_start=cut_min,
                cut_end=cut_max,
            )
        elif actual_colors_list:
            colormap_obj = Colormap.from_list(
                actual_colors_list,
                interpolation_space=interpolation_space,
                name=name,
                cut_start=cut_min,
                cut_end=cut_max,
            )
        else:
            # This path should not be reachable due to checks above.
            raise typer.Exit(code=ExitCodes.UNEXPECTED_ERROR)

        if name:
            colormap_obj.name = name

        return colormap_obj

    except InvalidColorError as e:
        console.print(
            f"[bold red]Error creating colormap:[/bold red] {e}", style="bold red"
        )
        raise typer.Exit(code=ExitCodes.INVALID_COLOR)
    except PresetNotFoundError as e:
        console.print(f"[bold red]Error:[/bold red] {e}", style="bold red")
        raise typer.Exit(code=ExitCodes.RESOURCE_NOT_FOUND)
    except Exception as e:
        console.print(
            f"[bold red]An unexpected error occurred during colormap creation:[/bold red] {e}",
            style="bold red",
        )
        if app_state.verbose_level > 0:
            console.print(
                Panel(
                    traceback.format_exc(),
                    title="[bold yellow]Detailed Traceback[/bold yellow]",
                    border_style="red",
                )
            )
        raise typer.Exit(code=ExitCodes.UNEXPECTED_ERROR)


def _parse_exporter_options(options: List[str]) -> Dict[str, Any]:
    """Parses repeatable -O/--option flags into a dictionary."""
    parsed_options: Dict[str, Any] = {"_global": {}}
    for option_str in options:
        if "=" not in option_str:
            console.print(
                f"[bold red]Error:[/bold red] Invalid format for --option '{option_str}'. Must be 'key=value' or 'exporter:key=value'."
            )
            raise typer.Exit(code=ExitCodes.USAGE_ERROR)

        key_part, value = option_str.split("=", 1)

        if ":" in key_part:
            exporter_key, option_key = key_part.split(":", 1)
            if exporter_key not in parsed_options:
                parsed_options[exporter_key] = {}
            parsed_options[exporter_key][option_key] = value
        else:
            # No namespace, store it as a global option for exporters to check
            parsed_options["_global"][key_part] = value

    return parsed_options


# --- Helper function for terminal rendering ---
def _render_colormap_to_terminal(
    console: Console, colormap_obj: Colormap, width: Optional[int], height: int
):
    """Renders the given Colormap object to the terminal."""
    console_width = console.width if console.width is not None else 80

    # Use user-provided width, otherwise default to console width. Enforce minimum of 10.
    actual_width = width if width is not None else console_width
    actual_width = max(10, actual_width)

    if not app_state.quiet:
        console.print(
            f"Rendering preview of '{colormap_obj.name or 'custom'}' ({actual_width}x{height} chars):"
        )

    for _ in range(height):
        for i in range(actual_width):
            norm_pos = i / (actual_width - 1 if actual_width > 1 else 1)
            hex_color_srgb = colormap_obj.get_color(norm_pos)
            console.print(f"[{hex_color_srgb}]█[/]", end="")
        console.print()


# --- 'list' subcommand group ---
list_app = typer.Typer(name="list", help="List available presets or export formats.")
app.add_typer(list_app)


@list_app.command(name="exporters")
def list_exporters_command():
    """List all available (registered) colormap exporters."""
    exporters = list_available_exporters()
    table = Table(title="Available Palettize Exporters", header_style="bold magenta")
    table.add_column("Identifier", style="dim cyan", width=30)
    table.add_column("Name")
    for identifier, name in sorted(exporters.items()):
        table.add_row(identifier, name)
    console.print(table)


@list_app.command(name="presets")
def list_presets_command():
    """List all available built-in preset palettes."""
    presets = list_available_presets()
    table = Table(title="Available Preset Palettes", header_style="bold magenta")
    table.add_column("Name", style="dim cyan")
    for preset_name in sorted(presets):
        table.add_row(preset_name)
    console.print(table)


# --- Top-level commands ---


@app.command()
def show(
    preset_name: Optional[str] = typer.Argument(
        None, help="Name of a preset palette (e.g., 'viridis')."
    ),
    colors: Optional[List[str]] = typer.Option(
        None,
        "--colors",
        "-c",
        help="List of input colors (e.g., 'red,blue', '#ff0000'). Use multiple times or comma-separate.",
    ),
    width: Optional[int] = typer.Option(
        None,
        "--width",
        "-w",
        help="Width for terminal preview in characters. Defaults to terminal width.",
    ),
    height: int = typer.Option(
        1, "--height", "-H", min=1, help="Height for terminal preview in lines."
    ),
    interpolation_space: str = typer.Option(
        "oklch", "--space", "-s", help="Color space for interpolation."
    ),
    cut: str = typer.Option(
        "0,1", "--cut", help="Sub-segment of the colormap to use, e.g., '0.2,0.8'."
    ),
    name: Optional[str] = typer.Option(
        None, "--name", help="Set a display name for the colormap."
    ),
):
    """Show a colormap or preset by rendering it in the terminal."""
    colormap_obj = _create_colormap_from_options(
        preset=preset_name,
        colors=colors,
        cut=cut,
        interpolation_space=interpolation_space,
        name=name,
    )
    _render_colormap_to_terminal(console, colormap_obj, width, height)


@app.command()
def create(
    preset_name: Optional[str] = typer.Argument(
        None, help="Name of a preset palette to export (e.g., 'viridis')."
    ),
    colors: Optional[List[str]] = typer.Option(
        None, "--colors", "-c", help="List of input colors to create a colormap from."
    ),
    formats: List[str] = typer.Option(
        ...,
        "--format",
        "-f",
        help="One or more export format identifiers (e.g., 'gdal,qgis').",
    ),
    output: Optional[str] = typer.Option(
        None,
        "--output",
        "-o",
        help="Output path pattern. Use {name}, {format}, {ext}. If omitted, prints to standard output.",
    ),
    domain: str = typer.Option(
        "0,1", "--domain", "-d", help="Data domain for scaling, e.g., '0,100'."
    ),
    scale: str = typer.Option(
        "linear", "--scale", help="Scaling type: linear, power, sqrt, log, symlog."
    ),
    scale_exponent: Optional[float] = typer.Option(
        None, "--scale-exponent", help="Exponent for 'power' scale."
    ),
    scale_log_base: Optional[float] = typer.Option(
        None, "--scale-log-base", help="Log base for 'log'/'symlog' scales."
    ),
    scale_symlog_linthresh: Optional[float] = typer.Option(
        None, "--scale-symlog-linthresh", help="Linear threshold for 'symlog' scale."
    ),
    steps: Optional[int] = typer.Option(
        7,
        "--steps",
        "-n",
        min=2,
        help="Number of discrete color steps for ramp outputs.",
    ),
    precision: Optional[int] = typer.Option(
        None, "--precision", min=0, help="Decimal places for numeric values in output."
    ),
    interpolation_space: str = typer.Option(
        "oklch", "--space", "-s", help="Color space for interpolation."
    ),
    cut: str = typer.Option(
        "0,1", "--cut", help="Sub-segment of the colormap to use, e.g., '0.2,0.8'."
    ),
    name: Optional[str] = typer.Option(
        None, "--name", help="Name for the colormap, used in file naming and output."
    ),
    option: Optional[List[str]] = typer.Option(
        None,
        "--option",
        "-O",
        help="Pass a format-specific option, e.g., 'gdal:precision=5'. Use multiple times.",
    ),
):
    """Create and export a colormap to one or more file formats."""
    colormap_obj = _create_colormap_from_options(
        preset=preset_name,
        colors=colors,
        cut=cut,
        interpolation_space=interpolation_space,
        name=name,
    )

    # --- Parse Arguments and Set Up ---

    # Parse domain argument
    try:
        domain_min, domain_max = parse_min_max_str(domain, "--domain")
    except typer.BadParameter as e:
        console.print(f"[bold red]Error:[/bold red] {e.message}", style="bold red")
        raise typer.Exit(code=ExitCodes.USAGE_ERROR)

    # Instantiate Scaler
    scaler_options = {}
    actual_scale_type = scale
    if scale == "power":
        if scale_exponent is None:
            console.print(
                "[bold red]Error:[/bold red] --scale-exponent is required when using --scale=power."
            )
            raise typer.Exit(code=ExitCodes.USAGE_ERROR)
        scaler_options["exponent"] = scale_exponent
    elif scale == "sqrt":
        actual_scale_type = "power"
        scaler_options["exponent"] = 0.5
    if scale in ["log", "symlog"] and scale_log_base is not None:
        scaler_options["base"] = scale_log_base
    if scale == "symlog":
        if scale_symlog_linthresh is None:
            console.print(
                "[bold red]Error:[/bold red] --scale-symlog-linthresh is required when using --scale=symlog."
            )
            raise typer.Exit(code=ExitCodes.USAGE_ERROR)
        scaler_options["linthresh"] = scale_symlog_linthresh

    try:
        scaler = get_scaler_by_name(
            name=actual_scale_type,
            domain_min=domain_min,
            domain_max=domain_max,
            **scaler_options,
        )
    except ValueError as e:
        console.print(
            f"[bold red]Error creating scaler:[/bold red] {e}", style="bold red"
        )
        raise typer.Exit(code=ExitCodes.USAGE_ERROR)

    # Parse exporter-specific options
    exporter_options = _parse_exporter_options(option or [])

    # Process format list
    actual_formats = []
    for f_item in formats:
        actual_formats.extend([f.strip() for f in f_item.split(",") if f.strip()])

    if not actual_formats:
        console.print(
            "[bold red]Error:[/bold red] No valid format specified with --format.",
            style="bold red",
        )
        raise typer.Exit(code=ExitCodes.USAGE_ERROR)

    # --- Perform Export ---

    overall_success = True
    base_colormap_name = colormap_obj.name or (
        preset_name if preset_name else "custom_map"
    )

    for fmt in actual_formats:
        exporter = get_exporter(fmt)
        if not exporter:
            console.print(
                f"[bold red]Error:[/bold red] Exporter '{fmt}' not found.",
                style="bold red",
            )
            overall_success = False
            continue

        if not app_state.quiet:
            console.print(f"Exporting to [cyan]{fmt}[/cyan] format...")

        # Combine global and format-specific options
        final_options = exporter_options.get("_global", {}).copy()
        final_options.update(exporter_options.get(fmt, {}))
        # Add core CLI options that exporters might use
        if steps:
            final_options["num_colors"] = steps
        if precision:
            final_options["precision"] = precision
        final_options["name"] = base_colormap_name
        final_options["scale_type"] = scale

        try:
            output_str = exporter.export(
                colormap_obj, scaler, domain_min, domain_max, options=final_options
            )

            # Handle output
            if output:
                f_ext = exporter.default_file_extension or "txt"
                output_path_str = output.format(
                    name=base_colormap_name, format=fmt, ext=f_ext
                )
                output_path = Path(output_path_str)
                output_path.parent.mkdir(parents=True, exist_ok=True)
                output_path.write_text(output_str)
                if not app_state.quiet:
                    console.print(f"[green]Successfully wrote to {output_path}[/green]")
            else:
                # If no output path, print to stdout
                console.print(output_str)

        except Exception as e:
            console.print(
                f"[bold red]Failed to export to {fmt}:[/bold red] {e}", style="bold red"
            )
            if app_state.verbose_level > 0:
                console.print(
                    Panel(
                        traceback.format_exc(),
                        title="[bold yellow]Detailed Traceback[/bold yellow]",
                        border_style="red",
                    )
                )
            overall_success = False

    if not overall_success:
        raise typer.Exit(code=ExitCodes.EXPORT_ERROR)

    if not app_state.quiet:
        console.print("[bold green]Export process completed.[/bold green]")
