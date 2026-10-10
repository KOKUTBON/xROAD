import { RISK_LEGEND } from "@/lib/risk-legend";

/**
 * Risk-ramp legend (#180 / #172). Token-bound swatches with label + meaning, so
 * the map's signature data color is always decodable. `orientation` lets it sit
 * as a compact horizontal strip under a map or a vertical overlay panel.
 */
export function MapLegend({
  title = "Risk band",
  orientation = "horizontal",
  showMeaning = true,
}: {
  title?: string;
  orientation?: "horizontal" | "vertical";
  showMeaning?: boolean;
}) {
  return (
    <div className={`risk-legend risk-legend-${orientation}`} aria-label={`${title} legend`}>
      <span className="risk-legend-title">{title}</span>
      <ul className="risk-legend-items">
        {RISK_LEGEND.map((entry) => (
          <li className="risk-legend-item" key={entry.band}>
            <span aria-hidden="true" className="risk-legend-swatch" style={{ background: entry.cssVar }} />
            <span className="risk-legend-label">{entry.label}</span>
            {showMeaning ? <span className="risk-legend-meaning">{entry.meaning}</span> : null}
          </li>
        ))}
      </ul>
    </div>
  );
}
