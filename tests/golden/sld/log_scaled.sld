<?xml version='1.0' encoding='utf-8'?>
<sld:StyledLayerDescriptor xmlns:sld="http://www.opengis.net/sld" xmlns:xsi="http://www.w3.org/2001/XMLSchema-instance" version="1.0.0" xsi:schemaLocation="http://www.opengis.net/sld http://schemas.opengis.net/sld/1.0.0/StyledLayerDescriptor.xsd">
  <sld:UserLayer>
    <sld:Name>palettize_layer</sld:Name>
    <sld:UserStyle>
      <sld:Name>palettize_style</sld:Name>
      <sld:IsDefault>1</sld:IsDefault>
      <sld:FeatureTypeStyle>
        <sld:Rule>
          <sld:Name>Default Rule</sld:Name>
          <sld:RasterSymbolizer>
            <sld:ColorMap type="ramp">
              <sld:ColorMapEntry color="#0000ff" quantity="1.000000" opacity="1.00" label="RefMap Start (1.00)" />
              <sld:ColorMapEntry color="#ff8200" quantity="250.750000" opacity="1.00" />
              <sld:ColorMapEntry color="#ff5100" quantity="500.500000" opacity="1.00" />
              <sld:ColorMapEntry color="#ff2f00" quantity="750.250000" opacity="1.00" />
              <sld:ColorMapEntry color="#ff0000" quantity="1000.000000" opacity="1.00" label="RefMap End (1000.00)" />
            </sld:ColorMap>
          </sld:RasterSymbolizer>
        </sld:Rule>
      </sld:FeatureTypeStyle>
    </sld:UserStyle>
  </sld:UserLayer>
</sld:StyledLayerDescriptor>