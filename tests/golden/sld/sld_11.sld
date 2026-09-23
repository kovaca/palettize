<?xml version='1.0' encoding='utf-8'?>
<sld:StyledLayerDescriptor xmlns:se="http://www.opengis.net/se" xmlns:sld="http://www.opengis.net/sld" xmlns:xsi="http://www.w3.org/2001/XMLSchema-instance" version="1.1.0" xsi:schemaLocation="http://www.opengis.net/sld http://schemas.opengis.net/sld/1.1.0/StyledLayerDescriptor.xsd">
  <sld:UserLayer>
    <sld:Name>palettize_layer</sld:Name>
    <sld:UserStyle>
      <sld:Name>palettize_style</sld:Name>
      <sld:IsDefault>1</sld:IsDefault>
      <sld:FeatureTypeStyle>
        <sld:Rule>
          <sld:Name>Default Rule</sld:Name>
          <sld:RasterSymbolizer>
            <se:ChannelSelection>
              <se:GrayChannel>
                <se:SourceChannelName>2</se:SourceChannelName>
              </se:GrayChannel>
            </se:ChannelSelection>
            <se:ColorMap type="ramp">
              <se:ColorMapEntry color="#0000ff" quantity="0.000000" opacity="1.00" label="RefMap Start (0.00)" />
              <se:ColorMapEntry color="#ffff00" quantity="50.000000" opacity="1.00" />
              <se:ColorMapEntry color="#ff0000" quantity="100.000000" opacity="1.00" label="RefMap End (100.00)" />
            </se:ColorMap>
          </sld:RasterSymbolizer>
        </sld:Rule>
      </sld:FeatureTypeStyle>
    </sld:UserStyle>
  </sld:UserLayer>
</sld:StyledLayerDescriptor>