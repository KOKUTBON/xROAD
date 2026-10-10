export const dynamic = "force-static";
import { publicAsset } from "@/lib/demo-mode";
import type { MetadataRoute } from "next";

export default function manifest(): MetadataRoute.Manifest {
  return {
    name: "Road Accidents Risk Modeling",
    short_name: "xROAD",
    description: "See road risk before it becomes a crash.",
    start_url: publicAsset("/"),
    display: "standalone",
    background_color: "#0e1013",
    theme_color: "#0e1013",
    icons: [
      { src: publicAsset("/brand/road-accidents-risk-modeling-icon.svg"), sizes: "any", type: "image/svg+xml", purpose: "any" },
      { src: publicAsset("/brand/road-accidents-risk-modeling-icon-512.png"), sizes: "512x512", type: "image/png", purpose: "any" },
    ],
  };
}
