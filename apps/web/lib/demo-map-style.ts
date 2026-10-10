import type { StyleSpecification } from "maplibre-gl";
import { STATIC_DEMO } from "./demo-mode";

/** Public demo street tiles use ordinary browser requests with visible attribution. */
export function demoMapStyle(original: StyleSpecification): StyleSpecification {
  if (!STATIC_DEMO) return original;
  const style = structuredClone(original);
  for (const [id, source] of Object.entries(style.sources)) {
    if (id === "carto-labels") {
      delete style.sources[id];
    } else if (id.startsWith("carto-") && source.type === "raster") {
      source.tiles = ["https://tile.openstreetmap.org/{z}/{x}/{y}.png"];
      source.maxzoom = 19;
      source.attribution = '© <a href="https://www.openstreetmap.org/copyright">OpenStreetMap</a> contributors';
    }
  }
  style.layers = style.layers.filter((layer) => layer.id !== "carto-labels-basemap");
  for (const layer of style.layers) {
    if (layer.id === "carto-dark-basemap" && layer.type === "raster") {
      layer.paint = { ...layer.paint, "raster-brightness-max": 0.45, "raster-saturation": -0.6 };
    }
  }
  return style;
}
