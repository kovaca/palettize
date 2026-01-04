import { defineConfig } from 'astro/config';
import starlight from '@astrojs/starlight';

export default defineConfig({
  site: 'https://kovaca.github.io',
  base: '/palettize',
  integrations: [
    starlight({
      title: 'Palettize',
      description: 'A Python CLI tool for generating, previewing, and exporting colormaps for GIS and web mapping.',
      social: [
        { icon: 'github', label: 'GitHub', href: 'https://github.com/kovaca/palettize' },
      ],
      editLink: {
        baseUrl: 'https://github.com/kovaca/palettize/edit/main/docs/',
      },
      favicon: '/favicon.svg',
      customCss: ['./src/styles/custom.css'],
      sidebar: [
        {
          label: 'Getting Started',
          items: [
            { label: 'Installation', slug: 'getting-started/installation' },
            { label: 'Quick Start', slug: 'getting-started/quick-start' },
          ],
        },
        {
          label: 'CLI Reference',
          items: [
            { label: 'Overview', slug: 'cli' },
            { label: 'palettize show', slug: 'cli/show' },
            { label: 'palettize create', slug: 'cli/create' },
            { label: 'palettize list', slug: 'cli/list' },
            { label: 'palettize info', slug: 'cli/info' },
          ],
        },
        {
          label: 'Python API',
          items: [
            { label: 'Overview', slug: 'python-api' },
            { label: 'Colormap Class', slug: 'python-api/colormap' },
            { label: 'Scaling Functions', slug: 'python-api/scaling' },
            { label: 'Exporters', slug: 'python-api/exporters' },
          ],
        },
        {
          label: 'Export Formats',
          collapsed: false,
          items: [
            { label: 'Overview', slug: 'export-formats' },
            { label: 'GDAL', slug: 'export-formats/gdal' },
            { label: 'QGIS', slug: 'export-formats/qgis' },
            { label: 'SLD (OGC)', slug: 'export-formats/sld' },
            { label: 'TiTiler', slug: 'export-formats/titiler' },
            { label: 'MapLibre GL JS', slug: 'export-formats/maplibre-gl' },
            { label: 'Observable Plot', slug: 'export-formats/observable-plot' },
            { label: 'Google Earth Engine', slug: 'export-formats/gee' },
            { label: 'Hex (Plaintext)', slug: 'export-formats/hex' },
            { label: 'RGBA (Plaintext)', slug: 'export-formats/rgba' },
          ],
        },
        {
          label: 'Guides',
          items: [
            { label: 'Color Interpolation', slug: 'guides/color-interpolation' },
            { label: 'Data Scaling', slug: 'guides/data-scaling' },
            { label: 'Using Presets', slug: 'guides/presets' },
            { label: 'Custom Exporters', slug: 'guides/custom-exporters' },
          ],
        },
        {
          label: 'Examples',
          items: [
            { label: 'GIS Workflows', slug: 'examples/gis-workflows' },
            { label: 'Web Mapping', slug: 'examples/web-mapping' },
          ],
        },
      ],
      tableOfContents: { minHeadingLevel: 2, maxHeadingLevel: 3 },
      lastUpdated: true,
    }),
  ],
});
