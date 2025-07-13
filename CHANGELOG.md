# Changelog

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
