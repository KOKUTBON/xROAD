## Summary

Briefly describe the change and its rationale.

## Related Issues

Closes #

## Changes Made

- 
- 
- 

## Verification & Tests Performed

- [ ] Python unit & integration tests (`pytest -q`)
- [ ] Security release checks (`python tools/security_release_checks.py --summary`)
- [ ] Tracked file size guard (`python tools/check_tracked_file_sizes.py`)
- [ ] OpenAPI contract check (`python tools/export_openapi_contract.py`)
- [ ] Web frontend tests (`cd apps/web && npm test`)
- [ ] Web typecheck (`cd apps/web && npm run typecheck`)
- [ ] Web build (`cd apps/web && npm run build`)
- [ ] Staging / Compose verification (`docker compose config`)

## Security & Data Privacy

- [ ] No real secrets, tokens, or credentials are committed.
- [ ] No personal, proprietary, or operational crash records are committed.
- [ ] Only synthetic fixtures or documented schema examples are used in tests.
- [ ] Repository hygiene rules in `.gitignore` are observed.
