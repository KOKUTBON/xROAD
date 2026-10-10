"use client";

import { useInstitution } from "@/components/institution-provider";
import { usePlatformSession } from "@/components/session-provider";
import { Panel, StatusPill } from "@/components/ui";
import { MODULE_LABELS, moduleEnabled } from "@/lib/institution-product";
import { sessionOrganizations, sessionMunicipalities } from "@/lib/platform-shell";

/** Installed product settings are reviewed in TOML; this view does not mutate access. */
export function InstitutionSetup() {
  const { config } = useInstitution();
  const { session } = usePlatformSession();
  const organizations = sessionOrganizations(session);
  const jurisdictions = sessionMunicipalities(session);
  return (
    <Panel title="Institution setup" detail="This installation uses a standard product core with institution-specific identity, workflows, and jurisdiction settings.">
      <dl className="detail-grid">
        <div><dt>Institution</dt><dd>{config.institution_name}</dd></div>
        <div><dt>Operating profile</dt><dd>{config.deployment?.profile.replaceAll("_", " ") ?? "Local development"}</dd></div>
        <div><dt>Country and language</dt><dd>{config.country_code} · {config.default_language.toUpperCase()}</dd></div>
        <div><dt>Measurement units</dt><dd>{config.units.distance} · {config.units.speed} · {config.units.currency}</dd></div>
        <div><dt>Configuration revision</dt><dd>{config.deployment?.revision ?? "Unversioned local configuration"}</dd></div>
        <div><dt>Your configured scope</dt><dd>{organizations.length} organizations · {jurisdictions.length} jurisdictions</dd></div>
      </dl>
      <ul className="institution-module-list" aria-label="Configured product modules">
        {Object.entries(MODULE_LABELS).map(([id, label]) => (
          <li key={id}><span>{label}</span><StatusPill label={moduleEnabled(config, id as keyof typeof MODULE_LABELS) ? "Enabled" : "Not enabled"} tone={moduleEnabled(config, id as keyof typeof MODULE_LABELS) ? "success" : "neutral"} /></li>
        ))}
      </ul>
      <p>To change the installation, have the platform administrator review and apply its institution configuration. Enabling a module does not grant user permissions or establish validated data coverage.</p>
    </Panel>
  );
}
