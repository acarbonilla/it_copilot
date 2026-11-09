# IC-020 — Copilot UI, Integrated Security and F-04 Acceptance

**Status:** Local implementation complete; pending SOL G2 review
**Branch:** `feature/f04-copilot-ui`
**Baseline:** `main` at `cac14f1246315f1e394b85ffa3635964ececbcbd`
**Provider state:** Disabled; no synthesis, provider network call, or private-document transfer

## Objective and dependency baseline

IC-020 adds the authenticated Next.js Copilot workspace over the accepted IC-018 retrieval and IC-019 conversation APIs. The implementation began from the exact PR #24 merge commit. It changes no Django models, migrations, provider configuration, retrieval rules, or document authorization behavior.

## UI architecture and component structure

- `app/copilot/page.tsx` exposes the authenticated workspace route.
- `components/copilot-workspace.tsx` owns presentation and local request state while using the shared API client for every server operation.
- `lib/api.ts` defines typed conversation, message, and citation contracts and CSRF-protected mutation helpers.
- `components/dashboard-shell.tsx` makes Copilot available through existing authenticated navigation.

The workspace uses a desktop two-column layout and an off-canvas conversation sidebar on smaller screens. It provides new, select, refresh, delete, history, composer, empty, loading, failure, reference, and insufficient-evidence states.

## API integration and lifecycle

The client consumes only the versioned IC-019 endpoints:

- `POST` and `GET /api/v1/copilot/conversations`
- `GET` and `DELETE /api/v1/copilot/conversations/{id}`
- `POST /api/v1/copilot/conversations/{id}/messages`

Mutations use the existing CSRF bootstrap/retry flow and include session credentials. The browser never accesses persistence directly. Server responses are authoritative. A failed or timed-out submission triggers a detail refresh before a retry is offered because persistence may have completed before the transport failed. The typed question remains available for review. Generic 404 responses for expired or deleted conversations clear the unsafe selection and refresh the owned list.

## Grounding and citation display contract

For `references`, the UI renders the server-returned citation label and version sequence and states that relevant authorized documents were found. It does not render empty assistant content, source text, IDs, paths, keys, download links, or a synthesized answer. It explicitly states that references are not proof of a specific answer.

For `insufficient`, the UI states that authorized documentation is insufficient and returns no generic troubleshooting advice. Provider-disabled status is continuously visible. No generated response is simulated.

## Security boundaries

- The route restores the current session before loading protected API data and redirects authentication failures to login.
- Ownership, role, deactivation, expiry, citation validation, and document authorization remain enforced by the accepted backend.
- CSRF tokens protect create, submit, and delete actions; credentials are sent through the shared client.
- Citations remain inert metadata and cannot be converted into download URLs by this UI.
- React text rendering is used; no untrusted raw HTML, document text, or sensitive location is logged.
- The provider adapter and private-transfer gate are unchanged and disabled.

## Accessibility and responsive behavior

The workspace uses labelled navigation and message regions, semantic forms and controls, visible focus styles, status/alert announcements, keyboard-operable submission, confirmation before destructive deletion, selected-conversation `aria-current`, text wrapping, title truncation, and a labelled mobile sidebar. Shift+Enter inserts a newline; Enter submits once while duplicate submission is disabled.

## Test evidence

Commands were run from `apps/web` unless noted:

- `npx vitest run components/copilot-workspace.test.tsx lib/api.test.ts components/dashboard-shell.test.tsx` — 19 passed.
- `npm test` — 43 passed across 9 files. An earlier concurrent run had one unrelated activation timeout; isolated rerun passed 5/5 and the final full run passed.
- `npm run typecheck` — passed.
- `npm run lint` — passed with zero warnings.
- `npm run build` — passed; `/copilot` was generated successfully.
- From `apps/api`, with `DJANGO_SETTINGS_MODULE=config.settings.test`: `python manage.py test copilot.tests.test_conversations accounts.tests documents.tests.test_api --noinput` — 101 run, 18 skipped, 83 passed; system check reported no issues.
- `python manage.py makemigrations --check --dry-run` — no changes detected.
- `python manage.py check` — no issues identified.

No browser end-to-end run or screenshot is claimed. Component tests use jsdom. Native MySQL behavior was not changed by IC-020; accepted IC-019 native concurrency evidence remains the dependency evidence. A post-implementation attempt to run `python manage.py test copilot.tests.test_conversation_mysql copilot.tests.test_mysql --noinput` discovered 16 tests but could not create the test database because the execution environment supplied no MySQL password (`OperationalError 1045`, `using password: NO`). No test assertion ran, credentials were not guessed, and this environmental failure is not represented as a passing rerun.

## Acceptance evidence

| Criterion | Evidence | Result |
| --- | --- | --- |
| AC-01 | Session restoration and protected `/copilot` route | PASS |
| AC-02 | Responsive persistent/off-canvas sidebar | PASS |
| AC-03 | Create, list, and selected state | PASS |
| AC-04 | Bounded server history rendered safely | PASS |
| AC-05 | Trimmed non-empty input, 2,000-character limit, count and pending lock | PASS |
| AC-06 | CSRF client, server-authoritative result, uncertain-request refresh | PASS |
| AC-07 | Label/version-only references and integrity disclaimer | PASS |
| AC-08 | Explicit insufficient-evidence state without advice | PASS |
| AC-09 | Persistent provider-disabled messaging; no synthesis | PASS |
| AC-10 | Confirmed deletion and generic expired/deleted recovery | PASS |
| AC-11 | Existing credential/CSRF/session conventions; backend regressions pass | PASS |
| AC-12 | Semantic controls, keyboard flow, announcements, responsive classes | PASS (component evidence) |
| AC-13 | 43 frontend and 101 backend tests run; build/type/lint pass | PASS |
| AC-14 | This record and feature record updated | PASS |
| AC-15 | No provider, cloud, queue, vector, migration, or backend source change | PASS |

## Known limitations

Provider synthesis remains intentionally disabled, so the UI provides references rather than answers. Citations are intentionally non-clickable because no separately approved citation-to-document resolution interface exists. The list consumes the first bounded 25-conversation page because the MVP backend pagination contract is unchanged; additional page navigation is not yet exposed. Accessibility is component-tested but has not received a real-browser screen-reader or viewport audit. The dependency installation reported eight moderate npm audit findings; no unapproved dependency upgrade or automatic audit fix was applied.

## Review boundary

This record requests SOL G2 verification of IC-020 and consolidated F-04 acceptance. It does not authorize provider activation, private-data transmission, a merge, or deployment.
