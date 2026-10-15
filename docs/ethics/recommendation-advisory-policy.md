# Infrastructure Recommendation Advisory and Oversight Policy

## Status and intended use

Infrastructure recommendations are decision-support outputs, not engineering
designs, authorisations, procurement instructions, or automated municipal
decisions. They may be shown outside the analyst environment only after a named
engineer has reviewed the site, evidence, uncertainty, feasibility, and
countermeasure applicability and an authorised decision-maker has approved the
record.

Every proposal starts in `proposed`, then moves to `engineer_reviewed`, and only
then to `approved` or `rejected`. The API export is fail-closed: an `approved`
label without the recorded engineer-review event is not publishable. Rejections
use controlled reason codes and become negative training signals; free text is
supporting context, not a substitute for the reason code.

## EU AI Act posture

The current system is positioned as an advisory road-safety planning tool. It
does not make decisions about people, determine access to an essential service,
perform law enforcement, or operate road infrastructure in real time. On that
intended-use basis it is not treated as a high-risk system under Annex III.
This is a product-positioning assessment, not legal advice. Classification must
be reassessed before any material change in purpose, autonomous operation,
procurement context, affected population, or integration with enforcement.

The implementation nevertheless applies high-risk-style controls: traceable
model and data versions, human oversight, accuracy and calibration reporting,
executable safety constraints, event-level audit history, and post-deployment
feedback.

## Municipal responsibility and liability

The municipality and its appointed licensed professionals retain responsibility
for site inspection, standards compliance, detailed design, consultation,
environmental and accessibility assessment, procurement, construction, and
ongoing monitoring. Model outputs must not override binding Italian or EU law,
road-authority standards, local plans, or professional engineering judgement.

Before implementation, the municipality must independently validate traffic
counts, geometry, utilities, land ownership, emergency access, vulnerable-road-
user impacts, and current crash evidence. Predicted crash reduction and
benefit-cost values are uncertain planning estimates and must not be presented
as guarantees.

## Required evidence and audit record

Each reviewed recommendation stores the immutable proposal payload, model
version, data-lineage hash, reviewer identity, review note, decision, controlled
rejection reason where applicable, and timestamped state-transition events.
Calibration must report predicted versus observed crash reduction overall and
by treatment category. Benchmark releases must include iRAP directional checks,
historical-intervention retrodiction, and executable sanity constraints.

## Operational stop conditions

Do not approve or publish a recommendation when required evidence is missing,
the uncertainty interval or economics are invalid, a sanity constraint fails,
the location has materially changed since the data snapshot, or the reviewer
cannot establish countermeasure applicability. Such proposals must be rejected
or held for corrected data and a new model run; audit history must not be
rewritten.
