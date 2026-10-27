# IC-005 — Next.js Shell and Login

**Project:** IT Support Copilot V1.0 MVP  
**Feature:** F-01 Core Platform  
**Method:** TTDM-WA-001  
**Status:** SOL specification and UI/security design draft — Product Owner decision pending  
**Dependencies:** IC-001, IC-004 (both integrated)  
**Priority:** P0

## Authoritative baseline from TTDM Development Specification

> Objective: Provide a usable first browser workflow.
>
> Implementation scope: Next.js App Router, Tailwind CSS, shadcn/ui components, login, protected dashboard shell, module navigation placeholders, API client.
>
> Acceptance criteria: User can log in, refresh, see own identity, log out; unauthenticated users are redirected; placeholders are not presented as working modules.
>
> Verification: Typecheck, lint, UI tests, browser login/logout test.
>
> Dependencies: IC-001, IC-004. Risk: Client-side guards must not substitute for backend checks.

The technical decisions below are SOL proposals for implementation, **not verbatim additional requirements from the baseline**.

## Proposed UI architecture

- Build on the existing IC-001 frontend package and lockfile; inspect the repository before choosing or changing versions. Use Next.js App Router, TypeScript, Tailwind CSS, and shadcn/ui primitives.
- Create a coherent, accessible first-run UI: login page, protected dashboard shell, persistent navigation/header, authenticated identity display, logout action, loading/error/empty states, and clear inactive module placeholders.
- Suggested routes: `/login` (public), `/dashboard` (authenticated), and `/` redirecting according to authentication state. Do not implement actual module features in IC-005.
- Suggested navigation placeholders: Shared IT Documentation, Private Web Documentation, My Credentials, Copilot, and Administration (visible according to the appropriate role/flag where useful). All placeholders must visibly say **Coming soon** or **Not yet available**, and must not imply operational capability. Do not link to working-looking dead ends.
- Accessibility: semantic landmarks, labels, keyboard navigation, focus visibility, error announcement, sensible responsive layout and reduced-motion-friendly behavior.

## Proposed technical/security decisions — PO approval required

### U-01 — Frontend stack and route boundaries

- Reuse the existing IC-001 Next.js App Router foundation and its package manager. Introduce only necessary Tailwind/shadcn/ui dependencies.
- Render a public login page and an authenticated dashboard shell. Protected-route redirect is a UX control only; Django backend remains the authorization boundary.
- Avoid using cached role data or a client-side flag as proof of authorization. The dashboard must establish current identity through `GET /api/v1/auth/me` after load/refresh.

### U-02 — API client and session cookies

- Use IC-004's established endpoints unchanged: `GET /api/v1/auth/csrf`, `POST /api/v1/auth/login`, `POST /api/v1/auth/logout`, `GET /api/v1/auth/me`.
- Browser fetches use `credentials: "include"` against `http://localhost:8000` from the approved `http://localhost:3000` frontend.
- Bootstrap CSRF before unsafe calls; read the browser-accessible CSRF cookie and send `X-CSRFToken` on login/logout. Account for CSRF secret rotation at successful login: obtain the refreshed token before logout.
- Never store session IDs, passwords, or CSRF secrets in localStorage/sessionStorage. Do not log passwords, cookies, session IDs or sensitive server responses.
- Use explicit environment-configured API base URL, safe defaults for local development, no embedded production secrets, and no wildcard credentialed CORS changes.

### U-03 — Authentication flow and redirect behavior

- Successful login navigates to `/dashboard`; refresh preserves authenticated UX by re-fetching `/auth/me`.
- Anonymous or inactive `/auth/me` (401) redirects to `/login`; do not show protected dashboard data while session status is unresolved.
- Logout sends CSRF-protected POST, clears client-held identity state, and redirects to login; replay/refresh must not reenter the dashboard without a valid server session.
- Display generic login errors for invalid credentials/inactive users to avoid account enumeration. Distinguish network/API unavailable errors from bad credentials without exposing internals.
- Disable duplicate login submissions and provide accessible pending/error feedback.

### U-04 — UI navigation and privilege presentation

- Display identity from the `/auth/me` response only; no hardcoded identity or mock authentication in production code.
- Label unavailable modules as placeholders. Administration navigation visibility may be based on `is_app_admin` for UX, but actual administrative endpoints must enforce server authorization in later tasks.
- No self-registration, password reset, invitation, account administration, documentation CRUD, vault CRUD or Copilot chat implementation in IC-005.
- Use the IC-003 role separation: App Admin is not automatically an IT documentation administrator.

### U-05 — Test and delivery gates

- Typecheck and lint must pass using the repository's actual package manager scripts.
- UI tests cover login form validation, successful/failed login, redirect on 401, refresh identity restoration, logout, loading/errors, module placeholder labels, and keyboard-accessible form behavior.
- Browser E2E test must run against the **actual local Next.js frontend and Django/MySQL API** using the approved `localhost:3000` / `localhost:8000` pair. Verify cookie persistence, CSRF bootstrap/rotation, refresh, logout, and anonymous redirect. If no graphical browser automation is available, record the limitation explicitly and do not claim browser E2E passed.
- Rerun backend IC-002/IC-003/IC-004 regression suite and confirm no backend security contract regressions.
- Maintain all four TTDM task records, setup instructions, screenshots if genuinely captured, and F-01 feature tracking.

## Suggested acceptance checks

1. Public login page loads and is accessible.
2. Valid existing user can log in through Django session authentication and sees dashboard identity.
3. Browser refresh retains identity through the server session, without token storage.
4. Anonymous/deactivated users cannot access authenticated dashboard content and are redirected.
5. Logout invalidates session and subsequent refresh remains logged out.
6. Login/logout CSRF works with the real local two-port topology.
7. Module navigation clearly identifies unimplemented functionality.
8. Typecheck, lint, UI tests and real-browser login/logout verification are recorded with exact commands/results.
9. IC-002/IC-003/IC-004 backend regressions remain green.

## TTDM execution guardrails

- Implementation task branch proposed: `task/IC-005-nextjs-shell-login`, based on current `feature/core-platform`.
- Create task implementation and test records, and submit PR into `feature/core-platform`; do not merge without SOL review at exact head SHA.
- Do not merge F-01 into `main` without separate PO feature-release approval.
- This is local Windows 10 native MySQL development only; no Docker, cloud deployment or hosting scope.

## Product Owner decision gate

The Product Owner has approved **proceeding to IC-005 as the next task**. This document proposes U-01 through U-05, the route structure, placeholder behavior and browser test strategy for explicit approval before implementation handoff. No implementation is authorized by this draft alone.
