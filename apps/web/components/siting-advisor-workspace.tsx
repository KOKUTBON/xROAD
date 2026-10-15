"use client";

import { STATIC_DEMO } from "@/lib/demo-mode";
import { DEMO_CITY_KEY, demoCenter } from "@/lib/demo-city";

import { apiFetch } from "@/lib/demo-api";

import Link from "next/link";
import { useEffect, useRef, useState, type FormEvent } from "react";

import { WorkspacePage } from "@/components/layout";
import { usePlatformSession } from "@/components/session-provider";
import {
  EmptyState,
  ErrorState,
  LoadingState,
  PageHeader,
  Panel,
  StatusPill,
  WarningState,
} from "@/components/ui";
import { getClientApiBaseUrl } from "@/lib/api-client";
import {
  complianceSummary,
  riskColor,
  suitabilityColor,
  type SitingCandidate,
} from "@/lib/siting-advisor";

type AnalysisPayload = {
  analysis_id: string;
  status: string;
  results: SitingCandidate[];
  provision_gap: {
    metric: string;
    dm_1444_quota: number;
    current_estimate: number | null;
    availability: string;
    caveat: string;
  };
  data_freshness: {
    source_modified_at_utc: string;
    caveats: string[];
  };
};

export function SitingAdvisorWorkspace() {
  const { session } = usePlatformSession();
  const organizationId = session.selectedOrganizationId ?? session.organizationIds[0] ?? "";
  const cityKey = session.selectedMunicipalityId ?? session.municipalityIds[0] ?? (STATIC_DEMO ? DEMO_CITY_KEY : "bari");
  const [facilityType, setFacilityType] = useState<"park" | "school">("park");
  const [minimumPopulation, setMinimumPopulation] = useState("0");
  const [maximumRisk, setMaximumRisk] = useState("100");
  const [analysis, setAnalysis] = useState<AnalysisPayload | null>(null);
  const [selectedId, setSelectedId] = useState<string | null>(null);
  const [mapMode, setMapMode] = useState<"suitability" | "risk">("suitability");
  const [status, setStatus] = useState<"idle" | "loading" | "ready" | "error">("idle");
  const [error, setError] = useState("");
  const mapContainer = useRef<HTMLDivElement>(null);
  const selected =
    analysis?.results.find((row) => row.candidate_id === selectedId) ??
    analysis?.results[0] ??
    null;

  async function requestAnalysis(event?: FormEvent) {
    event?.preventDefault();
    setStatus("loading");
    try {
      const created = await apiFetch(`${getClientApiBaseUrl()}/v1/siting-analyses`, {
        method: "POST",
        credentials: "include",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          organization_id: organizationId,
          city_key: cityKey,
          facility_type: facilityType,
          school_grade: facilityType === "school" ? "primaria" : null,
          constraints: {
            minimum_served_population: Number(minimumPopulation),
            maximum_access_route_risk_percentile: Number(maximumRisk),
            limit: facilityType === "park" ? 10 : 5,
          },
        }),
      });
      if (!created.ok) throw new Error(`Analysis request failed (${created.status}).`);
      const job = (await created.json()) as { analysis_id: string };
      const response = await apiFetch(
        `${getClientApiBaseUrl()}/v1/siting-analyses/${job.analysis_id}/results?organization_id=${encodeURIComponent(organizationId)}`,
        { cache: "no-store", credentials: "include" },
      );
      if (!response.ok) throw new Error(`Analysis results failed (${response.status}).`);
      const payload = (await response.json()) as AnalysisPayload;
      setAnalysis(payload);
      setSelectedId(payload.results[0]?.candidate_id ?? null);
      setStatus("ready");
    } catch (caught) {
      setError(caught instanceof Error ? caught.message : "Siting analysis failed.");
      setStatus("error");
    }
  }

  useEffect(() => {
    if (!mapContainer.current || !analysis?.results.length) return;
    let disposed = false;
    let map: import("maplibre-gl").Map | undefined;
    void import("maplibre-gl").then((maplibre) => {
      if (disposed || !mapContainer.current) return;
      map = new maplibre.Map({
        container: mapContainer.current,
        style: {
          version: 8,
          sources: {
            candidates: {
              type: "geojson",
              data: {
                type: "FeatureCollection",
                features: analysis.results.map((row) => ({
                  type: "Feature",
                  geometry: row.geometry,
                  properties: {
                    candidate_id: row.candidate_id,
                    color:
                      mapMode === "risk"
                        ? riskColor(row.access_route_risk_percentile)
                        : suitabilityColor(row.suitability_score),
                  },
                })),
              },
            },
          },
          layers: [
            { id: "background", type: "background", paint: { "background-color": "#edf1f4" } },
            {
              id: "candidates",
              type: "circle",
              source: "candidates",
              paint: {
                "circle-radius": 10,
                "circle-color": ["get", "color"],
                "circle-stroke-width": 2,
                "circle-stroke-color": "#ffffff",
              },
            },
          ],
        },
        center: demoCenter([16.87, 41.12]),
        zoom: 10.5,
      });
      map.on("click", "candidates", (event) => {
        const id = event.features?.[0]?.properties?.candidate_id;
        if (id) setSelectedId(String(id));
      });
    });
    return () => {
      disposed = true;
      map?.remove();
    };
  }, [analysis, mapMode]);

  const exportBase = analysis
    ? `${getClientApiBaseUrl()}/v1/siting-analyses/${analysis.analysis_id}/export?organization_id=${encodeURIComponent(organizationId)}`
    : "";

  return (
    <WorkspacePage
      header={
        <PageHeader
          eyebrow="Standards-cited planning"
          title="Siting Advisor"
          description="Ask where a public facility can be sited and inspect every legal, safety, access, and equity factor behind the answer."
          meta={<StatusPill label="Advisory screening only" tone="warning" />}
          actions={
            analysis ? (
              <>
                <a className="ghost-button" href={`${exportBase}&output_format=csv`}>Export CSV</a>
                <a className="ghost-button" href={`${exportBase}&output_format=pdf`}>Export PDF</a>
                <Link className="ghost-button" href="/workspace/scenarios">Save or compare scenario</Link>
              </>
            ) : null
          }
        />
      }
    >
      <Panel title="Analysis request" detail="Candidate assessment · deterministic SIT-02 candidate bundle">
        <form className="siting-request-form" onSubmit={(event) => void requestAnalysis(event)}>
          <label>
            Facility type
            <select value={facilityType} onChange={(event) => setFacilityType(event.target.value as "park" | "school")}>
              <option value="park">Public park</option>
              <option value="school">Primary school</option>
            </select>
          </label>
          <label>
            Minimum served population
            <input min="0" type="number" value={minimumPopulation} onChange={(event) => setMinimumPopulation(event.target.value)} />
          </label>
          <label>
            Maximum access-route risk percentile
            <input min="0" max="100" type="number" value={maximumRisk} onChange={(event) => setMaximumRisk(event.target.value)} />
          </label>
          <button className="primary-button" disabled={!organizationId || status === "loading"} type="submit">
            Run siting analysis
          </button>
        </form>
      </Panel>
      {status === "loading" ? <LoadingState title="Evaluating candidate sites" detail="Applying mandatory rules, MCA criteria, and demand refinement." /> : null}
      {status === "error" ? <ErrorState title="Siting analysis unavailable" detail={error} action={<button className="ghost-button" onClick={() => void requestAnalysis()}>Retry</button>} /> : null}
      {status === "idle" ? <EmptyState title="No siting analysis yet" detail="Choose a facility and constraints to rank standards-compliant sites." /> : null}
      {status === "ready" && analysis?.results.length === 0 ? <EmptyState title="No candidate meets these constraints" detail="Relax the population or access-route risk filter and rerun." /> : null}
      {status === "ready" && analysis?.results.length ? (
        <>
          <div className="provision-gap-grid">
            <Panel title="DM 1444 quota" detail={analysis.provision_gap.metric}>
              <strong>{analysis.provision_gap.dm_1444_quota} m²/inhabitant</strong>
            </Panel>
            <Panel title="Current provision" detail={analysis.provision_gap.availability}>
              <strong>{analysis.provision_gap.current_estimate ?? "Not audited"}</strong>
              <p>{analysis.provision_gap.caveat}</p>
            </Panel>
          </div>
          <div className="siting-map-toolbar">
            <button className={mapMode === "suitability" ? "primary-button" : "ghost-button"} onClick={() => setMapMode("suitability")}>Suitability layer</button>
            <button className={mapMode === "risk" ? "primary-button" : "ghost-button"} onClick={() => setMapMode("risk")}>Access-route risk</button>
          </div>
          <div className="siting-results-grid">
            <div className="siting-results-map" ref={mapContainer} aria-label="Siting candidate map" />
            {selected ? (
              <Panel title={`#${selected.rank} ${selected.candidate_id}`} detail={`Suitability ${(selected.suitability_score * 100).toFixed(1)}%`}>
                <p><strong>Served population:</strong> {selected.served_population_estimate.toLocaleString()}</p>
                <p><strong>Access-route risk:</strong> percentile {selected.access_route_risk_percentile}</p>
                <p>{complianceSummary(selected.compliance.results)}</p>
                <h4>Compliance checklist</h4>
                <ul className="citation-checklist">
                  {selected.compliance.results.map((rule) => (
                    <li key={rule.rule_id}>
                      <StatusPill label={`${rule.status} · ${rule.severity}`} tone={rule.status === "pass" ? "success" : "warning"} />
                      <strong>{rule.description}</strong>
                      <a href={rule.source_url} target="_blank" rel="noreferrer">{rule.citation}</a>
                    </li>
                  ))}
                </ul>
              </Panel>
            ) : null}
          </div>
          <WarningState title="Data freshness and decision limits" detail={`${analysis.data_freshness.caveats.join(" ")} Source updated ${analysis.data_freshness.source_modified_at_utc}.`} />
        </>
      ) : null}
    </WorkspacePage>
  );
}
