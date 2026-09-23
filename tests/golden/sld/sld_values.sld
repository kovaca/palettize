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
            <sld:ColorMap type="values">
              <sld:ColorMapEntry color="#0000ff" quantity="0.000000" opacity="1.00" label="#0000ff (0.00)" />
              <sld:ColorMapEntry color="#ffff00" quantity="50.000000" opacity="1.00" label="#ffff00 (50.00)" />
              <sld:ColorMapEntry color="#ff0000" quantity="100.000000" opacity="1.00" label="#ff0000 (100.00)" />
            </sld:ColorMap>
          </sld:RasterSymbolizer>
        </sld:Rule>
      </sld:FeatureTypeStyle>
    </sld:UserStyle>
  </sld:UserLayer>
</sld:StyledLayerDescriptor>