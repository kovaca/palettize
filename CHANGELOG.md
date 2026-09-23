# Changelog

## [0.0.1] - 2026-09-22

### Added

- `palettize analyze` checks lightness, perceptual step size, and color vision (protanopia, deuteranopia, tritanopia). `--json` prints a report; `--strict` exits non-zero when problems are found.
- Colormap transforms, each returning a new map: `reversed()`, `cut()`, `resampled()`, `quantized()`, `blend()`, and `concat()` / `+`. The CLI exposes them as `--reverse`, `--cut`, and `--steps`.
- Portable colormap files. `Colormap.save()` / `load()` and `palettize create --save` write JSON that any command accepts in place of a preset name.
- `palettize show --output` writes a PNG or SVG preview, with no image library required.
- Preset discovery: `list presets --search/--category/--namespace/--swatch/--limit`, `list categories`, and `palettize presets <name>`.
- `palettize formats` lists export formats and the options each one accepts.
- Bulk sampling (`hex_colors`, `rgb_colors`, `rgba_colors`, `hsl_colors`, `colors`) and colormap protocols (`__call__`, `__len__`, `__iter__`).
- `palettize info` prints the version, links, and a banner.
- More `get_color()` formats: `hsl_tuple`, `hsl_string`, `rgb_float`, `rgba_float`, `oklch_string`, `css_color`, plus `output_space="display-p3"`.
- New exporters: `json`, `css`, `hsl`, `gimp`, and `svg`. `hex` and `rgba` gained output-format options.

### Changed

- Interpolation uses ColorAide, so multi-stop maps follow the correct hue path. Existing maps sample the same colors.
- `-v` works after a subcommand, and diagnostics go to stderr.
- `-O` values are coerced from the format's declared options. Unknown keys warn. `palettize formats` says which formats use `--domain` and `--scale`.
- GDAL omits the comment header unless `-v` is set, and emits an `nv` nodata line unless `-O nodata=false`.
- Minimum Python is 3.10.

### Fixed

- RGB tuples no longer break later color calls by shadowing ColorAide's `alpha()` method. An alpha of `0.5` on byte RGB stays half-opaque.
- Colormap files accept only schema version 1. JSON `true`, `0`, and newer versions are refused.
- SLD no longer builds a reversed `ColorStop` on its fallback path. GEE escapes attribute values.
- Stop positions are rounded on construction, so chained cuts and a save/load round-trip stay exact.
- A global `-O` typo warns, the same way a namespaced one does. `nodata=false` suppresses a GDAL nodata line even when `nodata_value` is set.
- CSS selectors, GIMP palette names, and SVG gradient ids can no longer break out of the file they generate.

### Internal

- Golden-file tests cover every exporter (`pytest --update-golden` to accept an intentional format change). CI runs on `uv` and gates releases on the test matrix.
- The exporter registry loads on demand. Unused `webcolors` dependency removed.

## [0.0.1a2] - 2025-07-13

### Added

- Support for exporting colormaps to GEE. CSS-like array of strings (default) or GEE-flavored SLD color ramp XML (sld). 



## [0.0.1a1] - 2025-07-06
Alpha release of Palettize.

### Added

- Initialized basic project structure, core logic, basic plugin system, and CLI.  
- Support for creating colormaps from preset palettes from `cmap` dependency.  
- Support for exporting colormaps to various formats.
  - GDAL gdaldem color-relief txt format
  - QGIS color ramp XML
  - SLD color ramp XML
  - Titiler url encoded colormap string
  - Mapgl color interpolation expression  
  - Observable Plot color object
