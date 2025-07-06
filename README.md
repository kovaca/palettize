# Palettize

🎨 A Python utility and CLI tool for generating, previewing, and exporting color maps.

Palettize helps you create and manage colormaps for data visualization, GIS, and web mapping. It provides a simple, powerful command-line interface to:

-   Generate colormaps from a list of colors or from built-in presets.
-   Instantly preview colormaps directly in your terminal.
-   Export colormaps to various formats suitable for different applications.
-   Customize interpolation color space, data scaling, and slicing.

## Installation

This project uses `uv` for dependency management. To install from source:

```bash
git clone https://github.com/your-username/palettize.git # Replace with actual repo URL
cd palettize
uv pip install .
```

For development, install with the `dev` dependencies:

```bash
uv pip install -e .[dev]
```

## Usage

Palettize is built on a simple `verb-noun` philosophy. You use a command like `show` or `create` and tell it what to operate on—either a `preset` name or a list of custom `--colors`.

```bash
palettize --help
```

### Key Commands

-   **`palettize show`**: Render a colormap preview in your terminal.
-   **`palettize create`**: Export a colormap to one or more file formats.
-   **`palettize list`**: List available `presets` or `exporters`.

### Examples

1.  **Show a built-in preset colormap:**
    ```bash
    palettize show viridis
    ```

2.  **Show a custom gradient made of three colors:**
    ```bash
    palettize show --colors "midnightblue,orange,gold"
    ```

3.  **Export the 'spectral' preset to a GDAL color ramp file:**
    The `--domain` flag maps the colormap to your data's range.
    ```bash
    palettize create spectral --format gdal --output spectral_gdal.txt --domain 0,255
    ```

4.  **Create a custom colormap and export it to multiple formats:**
    Use `--steps` to define the number of discrete colors in the output.
    ```bash
    palettize create -c "blue,white,red" --format qgis,mapgl \
      --output "output/rwb_{format}.{ext}" --steps 11 --name "RedWhiteBlue"
    ```
    This creates `output/rwb_qgis.xml` and `output/rwb_mapgl.json`.

5.  **List all available built-in presets:**
    ```bash
    palettize list presets
    ```

6.  **Pass format-specific options during export:**
    Use the `-O` or `--option` flag to pass key-value pairs to an exporter.
    ```bash
    # Tell the 'observable' exporter to create a diverging scale with a pivot
    palettize create RdBu -f observable -o plot.json \
      -O type=diverging -O pivot=0
    ```

## Features

-   **Flexible Colormap Creation**: Generate colormaps from lists of colors (hex, RGB, named) or use built-in presets.
-   **Advanced Interpolation**: Supports various color spaces for interpolation via the ColorAide library (e.g., Oklch, sRGB, LAB).
-   **Terminal Preview**: Instantly visualize any colormap in your terminal.
-   **Multiple Export Formats**: Supports common formats for GIS (GDAL, QGIS, SLD, Titiler) and web (MapLibre GL, Observable Plot).
-   **Customizable Scaling**: Apply linear, power, sqrt, or log scaling to map your data domain to the colormap.
-   **Plugin System for Exporters**: Easily extendable with new export formats.
-   **CLI with Rich Output**: User-friendly command-line interface with clear help messages and rich formatting.

## Available Presets

The incredibly useful `cmap` library is a core dependency used for presets. To see a list of colormap presets, run:
`palettize list presets`



## Available Export Formats

To see a list of all currently registered and available export formats, run:
`palettize list exporters`



