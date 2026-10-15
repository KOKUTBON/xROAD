export const dynamic = "force-static";
import { ImageResponse } from "next/og";
import { readFile } from "node:fs/promises";
import path from "node:path";

export const alt = "xROAD — See the risk before the crash. Road risk intelligence.";
export const size = { width: 1200, height: 630 };
export const contentType = "image/png";

export default async function OpengraphImage() {
  const logo = await readFile(path.join(process.cwd(), "public/brand/road-accidents-risk-modeling-icon-512.png"));
  return new ImageResponse(
    <div
      style={{
        width: "100%",
        height: "100%",
        display: "flex",
        flexDirection: "column",
        justifyContent: "space-between",
        padding: "64px 80px",
        background: "radial-gradient(900px 500px at 85% 20%, rgba(255,180,0,0.22), transparent 70%), #0e1013",
        color: "#f4f2ec",
        fontFamily: "sans-serif",
      }}
    >
      <div style={{ display: "flex", alignItems: "center" }}>
        <img src={`data:image/png;base64,${logo.toString("base64")}`} width={96} height={96} alt="" />
        <div style={{ display: "flex", flexDirection: "column", marginLeft: 22 }}>
          <span style={{ fontSize: 40, fontWeight: 800, letterSpacing: -1 }}>xROAD</span>
          <span style={{ fontSize: 18, color: "#8c95a1", letterSpacing: 4 }}>ROAD RISK INTELLIGENCE</span>
        </div>
      </div>
      <div style={{ display: "flex", flexDirection: "column" }}>
        <div style={{ fontSize: 88, fontWeight: 800, letterSpacing: -4, lineHeight: 1 }}>See the risk</div>
        <div style={{ fontSize: 88, fontWeight: 800, letterSpacing: -4, lineHeight: 1.05, color: "#ffb400" }}>
          before the crash.
        </div>
      </div>
      <div style={{ display: "flex", alignItems: "center", fontSize: 24, color: "#b3bac4" }}>
        <div style={{ width: 14, height: 14, borderRadius: 7, background: "#ff4b3e", marginRight: 14 }} />
        Hotspots · exposure-aware risk models · intervention planning
      </div>
      <div
        style={{
          position: "absolute",
          left: 0,
          right: 0,
          bottom: 0,
          height: 12,
          background: "repeating-linear-gradient(-45deg, #ffb400 0 18px, #0e1013 18px 36px)",
        }}
      />
    </div>,
    size,
  );
}
