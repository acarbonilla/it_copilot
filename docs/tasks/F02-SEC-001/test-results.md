# F02-SEC-001 — Test Results

**Environment:** Windows 11 / PowerShell; Django 5.2.7; native MySQL; Next.js 16.4.3; installed Google Chrome  
**Date:** 2026-10-29

| Command | Result |
| --- | --- |
| `python manage.py check --database default` | PASS — 0 issues |
| `python manage.py migrate` | PASS — native MySQL applied both `0004` migrations |
| `python manage.py makemigrations --check --dry-run` | PASS — no changes |
| `python manage.py showmigrations accounts security_audit` | PASS — both apps through `0004` |
| `python manage.py test -v 1` | PASS — 122 tests in 179.786s on native MySQL |
| focused invitation/remediation/migration tests | PASS — 44 tests, then 13 focused tests; includes native concurrency and failure injection |
| `npm test -- --run` | PASS — 7 files / 32 tests |
| `npm run typecheck` | PASS |
| `npm run lint` | PASS after removal of one unused suppression; final rerun recorded with delivery |
| `npm run build` | PASS — `/activate` static, no dynamic activation route, Proxy present |
| production SSR synthetic-token scan | PASS — token absent from `/activate` HTML and fixed legacy 404 body; status 404 |
| Next.js development output scan | PASS — post-fix capture contains token-free `/activate`; legacy path is ignored by configured incoming-request logging |
| Next.js production output scan | PASS — no request/token output produced by tested activation requests |
| `npx playwright test e2e/activation.spec.ts --reporter=line` | PASS — 1 real-Chrome invitation/fragment scrub/activation/legacy-rejection test in 9.3s |

## Security acceptance matrix

| Control | Evidence | Result |
| --- | --- | --- |
| Fragment read and immediate scrub | bootstrap unit tests plus real browser URL/hash assertions | PASS |
| No SSR/log/storage/audit token exposure | SSR/log scans, bounded audit assertions, source review | PASS |
| Legacy route rejection/non-reflection | route table, fixed Proxy 404, browser body assertion | PASS |
| Existing/new provenance | migration-operation test and invitation service assertion | PASS |
| Dry-run and actor qualification | command tests | PASS |
| Expired revoke/no reissue | remediation service test | PASS |
| Idempotence and concurrency | repeat execution plus native two-thread MySQL test | PASS |
| Rollback/artifact recovery | delivery, audit, and database commit failure tests | PASS |
| CSRF/single use/expiry/generic errors/fresh login | full backend and frontend regression suites | PASS |

The first browser run intentionally caught Next.js development 404 reflection of the legacy synthetic token. `proxy.ts` and scoped development log suppression corrected it; the unchanged scenario then passed. No live remediation command execution occurred against non-test data.
