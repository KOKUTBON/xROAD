# Security Policy

## Supported versions

Security fixes are applied to the current default branch. Tagged releases may receive fixes when they are still actively maintained; older research snapshots and generated artifacts should not be assumed to receive security updates.

## Report a vulnerability privately

Use GitHub's **Report a vulnerability** feature in the repository Security tab when it is available. If private vulnerability reporting is unavailable, contact the repository owner privately through the contact method listed on the owner's GitHub profile.

Do not open a public issue for vulnerabilities, leaked credentials, authentication bypasses, sensitive-data exposure, or a working exploit.

Include:

- the affected version, commit, route, component, or deployment mode;
- clear reproduction steps or a minimal proof of concept;
- the expected security impact and required access level;
- any affected data or users;
- a safe mitigation, if known.

The maintainer will acknowledge the report, assess severity and scope, coordinate a fix, and agree on a responsible disclosure timeline. Please avoid accessing data that is not yours, disrupting services, or broadening testing beyond what is necessary to demonstrate the issue.

## Sensitive road-safety data

Do not commit raw crash records, personal information, health-related data, precise restricted locations, production uploads, private camera or telematics feeds, credentials, tokens, signing material, or customer data. Keep them in access-controlled storage and publish only governance-approved aggregates.

`.gitignore` reduces accidental additions but does not remove tracked content or Git history. If sensitive material is committed, rotate affected secrets immediately and report the incident privately. Follow the [data-governance guide](docs/data-governance.md), [privacy guidance](docs/ethics/privacy-by-design.md), and [incident-response runbook](docs/incident-response.md).

## Deployment security

Docker and environment examples use local development defaults, including disabled authentication and predictable service credentials. They are not production settings. Production deployments must use unique secrets, enabled identity and authorization checks, restricted network exposure, TLS, supported dependency versions, backup and restore procedures, audit logging, and deployment-specific monitoring.

Run the repository security check and dependency audits before release:

```bash
python3 tools/security_release_checks.py --summary
cd apps/web && npm audit --audit-level=high
```

## Private reporting contact

Email [kokutbon@gmail.com](mailto:kokutbon@gmail.com) with subject `[xROAD] Security report`. Include affected version/commit, reproduction using synthetic data, preconditions and impact. Do not include live credentials or personal data. This mailbox is the fallback while the repository is private or GitHub's reporting form is unavailable.

After publication, prefer [GitHub private vulnerability reporting](https://github.com/KOKUTBON/xROAD/security/advisories/new) when enabled. Acknowledgment and remediation depend on maintainer availability; no response deadline is guaranteed. Coordinate disclosure and fixes privately.
