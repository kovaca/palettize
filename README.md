# Palettize

🎨 A Python utility and CLI tool for generating, previewing, and exporting colormaps. 

Palettize helps create colormaps for data visualization, GIS, and web mapping. It provides a simple command-line interface to:

-   Generate colormaps from a list of colors or from built-in presets.
-   Preview colormaps directly in the terminal.
-   Export colormaps to various formats suitable for different applications.
-   Customize interpolation color space, data scaling, and slicing.

## Installation

```bash
# Run it without installing
uvx palettize show viridis

# Or install it
uv pip install palettize
pip install palettize
```

## Quick tour

```bash
palettize show viridis                  # preview a colormap in the terminal
palettize analyze viridis               # check it for perceptual problems
palettize list presets --search blue    # find a colormap
palettize formats                       # see the export formats
palettize create viridis -f gdal -o ramp.txt --domain 0,3000
```

### Preview

```bash
palettize show viridis                        # full-width gradient bar
palettize show viridis --steps 7 --hex        # 7 discrete bands, with hex codes
palettize show -c "midnightblue,orange,gold"  # a colormap of your own
palettize show viridis -o preview.png         # write a PNG or SVG instead
```

### Analyze

`palettize analyze` answers the question that actually matters: is this colormap safe to
publish? It reports whether lightness increases steadily, whether equal data steps look
equally different, and how the map degrades for each form of color vision deficiency.

```bash
palettize analyze cividis
palettize analyze jet --strict     # exit non-zero when problems are found, for CI
palettize analyze viridis --json   # machine-readable
```

```
cividis  256 stops

  original  ████████████████████████████████████████
  protan    ████████████████████████████████████████   96% kept   ok
  deutan    ████████████████████████████████████████   87% kept   ok
  tritan    ████████████████████████████████████████   72% kept   ok

  lightness    sequential, ascending
               ▁▁▁▁▂▂▂▂▃▃▃▃▄▄▄▄▅▅▅▅▆▆▆▆▇▇▇▇████
  range        66 of 100
  uniformity   variation 0.16 (even)
  step size    mean 2.8 ΔE, range 1.6-3.7

  No problems detected.
```

### Export

```bash
# A GDAL color-relief ramp over your data's actual range
palettize create viridis -f gdal -o elevation.txt --domain 0,3000

# Several formats at once, with a filename pattern
palettize create -c "blue,white,red" -f qgis,mapgl \
  -o "out/{name}_{format}.{ext}" --steps 11 --name RedWhiteBlue

# Non-linear scaling, for skewed data
palettize create viridis -f gdal --domain 1,10000 --scale log

# Format-specific options
palettize create viridis -f gdal -O gdal:nodata=false
```

Run `palettize formats <name>` to see exactly which options a format accepts, with types and
defaults — no guessing.

### Transform and reuse

Every command accepts `--reverse`, `--cut`, and `--steps`, and any colormap can be saved to a
portable JSON file and used anywhere a preset name would be:

```bash
palettize create viridis --cut 0.2,0.8 --reverse --save my-map.json
palettize show my-map.json
palettize create my-map.json -f css -o theme.css
```

## Python API

```python
from palettize import Colormap, analyze, create_colormap, get_scaler_by_name

cmap = Colormap.from_preset("viridis")

# Sampling
cmap(0.5)                      # '#21918d'
cmap.hex_colors(5)             # ['#440154', '#3b528b', '#21918d', '#5cc863', '#fde725']
cmap.rgb_colors(5)
len(cmap)                      # 256 stops

# Transforms all return new colormaps
cmap.reversed()                # name becomes 'viridis_r'
cmap.cut(0.2, 0.8)             # a sub-range; cuts compose
cmap.resampled(11)             # refit to 11 evenly spaced stops
cmap.quantized(5)              # 5 hard-edged bands
cmap.blend(Colormap.from_preset("magma"), 0.5)
cmap + Colormap.from_preset("magma")   # concatenate

# Save and reload
cmap.reversed().save("my-map.json")
Colormap.load("my-map.json")

# Perceptual analysis
report = analyze(cmap)
report.lightness.shape          # 'sequential'
report.uniformity.is_uniform    # True
report.warnings                 # plain-language descriptions of any problems

# Map data values onto colors
scaler = get_scaler_by_name("log", domain_min=1, domain_max=1000)
cmap.apply_scaler(250, scaler)

# Or start from a list of colors
create_colormap(colors=["#0000ff", "white", "#ff0000"], name="BlueWhiteRed")
```

## Export formats

| Format | Identifier | Use case |
| --- | --- | --- |
| GDAL color relief | `gdal` | `gdaldem` raster styling |
| QGIS color ramp | `qgis` | QGIS styles |
| OGC SLD | `sld` | GeoServer, MapServer |
| TiTiler | `titiler` | Tile server URL parameter |
| MapLibre GL | `mapgl` | Web map style expressions |
| Observable Plot | `observable` | Plot scale definitions |
| Google Earth Engine | `gee` | GEE JavaScript snippets |
| CSS | `css` | Custom properties |
| SVG | `svg` | Gradient definitions |
| GIMP palette | `gimp` | GIMP, Inkscape, Krita |
| JSON | `json` | Generic interchange |
| Hex / RGBA / HSL | `hex`, `rgba`, `hsl` | Plain text color lists |

`palettize formats` lists these with their file extensions; `palettize formats <name>` shows
each one's options.

## Features

- **~650 presets** from the [`cmap`](https://github.com/tlambert03/cmap) catalog, searchable
  by name, category, and publisher.
- **Perceptual interpolation** in any ColorAide space (Oklch by default), with correct hue
  paths and gamut handling.
- **Perceptual analysis** built in: lightness monotonicity, ΔE2000 uniformity, and
  colorblind simulation for protanopia, deuteranopia, and tritanopia.
- **Composable transforms** — reverse, cut, resample, quantize, blend, concatenate.
- **Portable colormap files** you can save, share, and feed back into any command.
- **Plugin system** for third-party export formats via the `palettize.exporters` entry point.
- **No image dependencies** — PNG output is written with the standard library alone.

## Development

```bash
uv sync --extra dev
uv run pytest                    # run the tests
uv run pytest --update-golden    # accept intentional export-format changes
uv run ruff check src/ tests/
uv run mypy src/palettize
```

Exporter output is covered by golden-file tests. When you deliberately change a format, run
`pytest --update-golden` and review the resulting diff before committing.

## License

MIT
