"use client";

import { DEMO_CITY_KEY, demoCenter } from "@/lib/demo-city";

import { STATIC_DEMO } from "@/lib/demo-mode";
import { apiFetch } from "@/lib/demo-api";

import { useEffect, useMemo, useRef, useState } from "react";

import { WorkspacePage } from "@/components/layout";
import { usePlatformSession } from "@/components/session-provider";
import {
  EmptyState,
  ErrorState,
  FilterBar,
  LoadingState,
  PageHeader,
  Panel,
  StatusPill,
} from "@/components/ui";
import { getClientApiBaseUrl } from "@/lib/api-client";
import {
  canReviewRecommendations,
  priorityColor,
  reductionIntervalLabel,
  type Recommendation,
} from "@/lib/recommendations";

type Payload = { recommendations: Recommendation[]; recommendation_count: number };

export function ProposedChangesWorkspace() {
  const { session } = usePlatformSession();
  const organizationId = session.selectedOrganizationId ?? session.organizationIds[0] ?? "";
  const cityKey = session.selectedMunicipalityId ?? session.municipalityIds[0] ?? (STATIC_DEMO ? DEMO_CITY_KEY : "bari");
  const [rows, setRows] = useState<Recommendation[]>([]);
  const [selectedId, setSelectedId] = useState<string | null>(null);
  const [stateFilter, setStateFilter] = useState("");
  const [minimumBcr, setMinimumBcr] = useState("0");
  const [status, setStatus] = useState<"loading" | "ready" | "error">("loading");
  const [error, setError] = useState("");
  const mapContainer = useRef<HTMLDivElement>(null);
  const selected = rows.find((row) => row.recommendation_id === selectedId) ?? rows[0] ?? null;
  const mayReview = canReviewRecommendations(session.roles);
  const query = useMemo(() => {
    const params = new URLSearchParams({
      organization_id: organizationId,
      city_key: cityKey,
      minimum_bcr: minimumBcr || "0",
    });
    if (stateFilter) params.set("review_state", stateFilter);
    return params.toString();
  }, [cityKey, minimumBcr, organizationId, stateFilter]);

  async function load() {
    if (!organizationId) return;
    setStatus("loading");
    try {
      const response = await apiFetch(`${getClientApiBaseUrl()}/v1/recommendations?${query}`, {
        cache: "no-store",
        credentials: "include",
      });
      if (!response.ok) throw new Error(`Recommendations request failed (${response.status}).`);
      const payload = (await response.json()) as Payload;
      setRows(payload.recommendations);
      setSelectedId((current) =>
        payload.recommendations.some((row) => row.recommendation_id === current)
          ? current
          : payload.recommendations[0]?.recommendation_id ?? null,
      );
      setStatus("ready");
    } catch (caught) {
      setError(caught instanceof Error ? caught.message : "Recommendations could not be loaded.");
      setStatus("error");
    }
  }

  useEffect(() => void load(), [query]); // eslint-disable-line react-hooks/exhaustive-deps

  useEffect(() => {
    if (!mapContainer.current || rows.length === 0) return;
    let disposed = false;
    let map: import("maplibre-gl").Map | undefined;
    void import("maplibre-gl").then((maplibre) => {
      if (disposed || !mapContainer.current) return;
      map = new maplibre.Map({
        container: mapContainer.current,
        style: {
          version: 8,
          sources: {
            recommendations: {
              type: "geojson",
              data: {
                type: "FeatureCollection",
                features: rows.map((row) => ({
                  type: "Feature",
                  geometry: row.geometry,
                  properties: {
                    recommendation_id: row.recommendation_id,
                    color: priorityColor(row),
                  },
                })),
              },
            },
          },
          layers: [
            {
              id: "background",
              type: "background",
              paint: { "background-color": "#eef2f5" },
            },
            {
              id: "recommendations",
              type: "line",
              source: "recommendations",
              paint: {
                "line-color": ["get", "color"],
                "line-width": 7,
                "line-opacity": 0.9,
              },
            },
          ],
        },
        center: demoCenter([16.87, 41.12]),
        zoom: 11,
      });
      map.on("click", "recommendations", (event) => {
        const id = event.features?.[0]?.properties?.recommendation_id;
        if (id) setSelectedId(String(id));
      });
      map.on("mouseenter", "recommendations", () => {
        if (map) map.getCanvas().style.cursor = "pointer";
      });
      map.on("mouseleave", "recommendations", () => {
        if (map) map.getCanvas().style.cursor = "";
      });
    });
    return () => {
      disposed = true;
      map?.remove();
    };
  }, [rows]);

  async function transition(toState: "engineer_reviewed" | "approved" | "rejected") {
    if (!selected) return;
    let reasonCode: string | undefined;
    let note = "Reviewed in the Proposed Changes workspace.";
    if (toState === "rejected") {
      reasonCode = window.prompt(
        "Reason: site_constraint, insufficient_evidence, cost_or_deliverability, conflicts_with_plan, unsafe_or_inapplicable, duplicate, other",
        "site_constraint",
      ) ?? undefined;
      if (!reasonCode) return;
      note = window.prompt("Review note", "Rejected after engineering review.") ?? note;
    }
    const response = await apiFetch(
      `${getClientApiBaseUrl()}/v1/recommendations/${encodeURIComponent(selected.recommendation_id)}/review`,
      {
        method: "POST",
        credentials: "include",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          organization_id: organizationId,
          city_key: cityKey,
          to_state: toState,
          note,
          reason_code: reasonCode,
        }),
      },
    );
    if (!response.ok) {
      setError(`Review update failed (${response.status}).`);
      setStatus("error");
      return;
    }
    await load();
  }

  return (
    <WorkspacePage
      header={
        <PageHeader
          eyebrow="AI advisory · engineer controlled"
          title="Proposed Changes"
          description="Review evidence-constrained infrastructure treatments before they enter the municipal action plan."
          meta={<StatusPill label={`${rows.length} recommendations`} tone="neutral" />}
          actions={STATIC_DEMO ? <span>Approved action-plan exports require an institutional backend.</span> : (
            <>
              <a className="ghost-button" href={`${getClientApiBaseUrl()}/v1/recommendations/action-plan/export?organization_id=${organizationId}&city_key=${cityKey}&output_format=csv`}>
                Export approved CSV
              </a>
              <a className="ghost-button" href={`${getClientApiBaseUrl()}/v1/recommendations/action-plan/export?organization_id=${organizationId}&city_key=${cityKey}&output_format=pdf`}>
                Export approved PDF
              </a>
            </>
          )}
        />
      }
    >
      <FilterBar>
        <label>
          Review state
          <select value={stateFilter} onChange={(event) => setStateFilter(event.target.value)}>
            <option value="">All states</option>
            <option value="proposed">Proposed</option>
            <option value="engineer_reviewed">Engineer reviewed</option>
            <option value="approved">Approved</option>
            <option value="rejected">Rejected</option>
          </select>
        </label>
        <label>
          Minimum BCR
          <input min="0" step="0.5" type="number" value={minimumBcr} onChange={(event) => setMinimumBcr(event.target.value)} />
        </label>
      </FilterBar>
      {status === "loading" ? <LoadingState title="Loading proposed changes" detail="Reading model outputs and review state." /> : null}
      {status === "error" ? <ErrorState title="Proposed changes unavailable" detail={error} action={<button className="ghost-button" onClick={() => void load()}>Retry</button>} /> : null}
      {status === "ready" && rows.length === 0 ? <EmptyState title="No recommendations match these filters" detail="Reduce the BCR threshold or include another review state." /> : null}
      {status === "ready" && rows.length > 0 ? (
        <div className="proposed-changes-grid">
          <div className="proposed-changes-map" ref={mapContainer} aria-label="Recommendation priority map" />
          {selected ? (
            <Panel
              title={selected.countermeasure_name}
              detail={selected.segment_label ?? "Selected road object"}
            >
              <dl className="detail-grid">
                <div><dt>Expected prevention</dt><dd>{reductionIntervalLabel(selected)}</dd></div>
                <div><dt>Benefit-cost ratio</dt><dd>{selected.benefit_cost_ratio.toFixed(1)}</dd></div>
                <div><dt>Cost band</dt><dd>{selected.cost_band}</dd></div>
                <div><dt>Review state</dt><dd>{selected.review_state.replaceAll("_", " ")}</dd></div>
              </dl>
              <h4>Why this change</h4>
              <ul>{selected.contributing_factors.map((factor) => <li key={factor.label}><strong>{factor.label}:</strong> {factor.value ?? "material contributor"}</li>)}</ul>
              <p><strong>Evidence:</strong> {selected.evidence_source} · {selected.evidence_ref}</p>
              {mayReview && selected.review_state === "proposed" ? (
                <div className="button-row">
                  <button className="primary-button" onClick={() => void transition("engineer_reviewed")}>Record engineer review</button>
                  <button className="danger-button" onClick={() => void transition("rejected")}>Reject</button>
                </div>
              ) : null}
              {mayReview && selected.review_state === "engineer_reviewed" ? (
                <div className="button-row">
                  <button className="primary-button" onClick={() => void transition("approved")}>Approve</button>
                  <button className="danger-button" onClick={() => void transition("rejected")}>Reject</button>
                </div>
              ) : null}
            </Panel>
          ) : null}
        </div>
      ) : null}
    </WorkspacePage>
  );
}
