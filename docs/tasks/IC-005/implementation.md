# IC-005 implementation record

## Implemented scope

- Initialized `apps/web` with Next.js 16 App Router, React 19, TypeScript,
  Tailwind CSS, ESLint, shadcn/ui-style primitives, Vitest, Testing Library, and
  Playwright using npm.
- Added `/`, `/login`, and `/dashboard`. The root resolves the Django session;
  the dashboard withholds protected UI until `/auth/me` succeeds.
- Added responsive semantic navigation, authenticated identity, logout, visible
  focus states, labeled inputs, live status/error messaging, and reduced motion.
- Added placeholders for Shared IT Documentation, Private Web Documentation,
  My Credentials, Copilot, and App-Admin-only Administration. Every unavailable
  module is explicitly labeled `Coming soon` and `Not yet available`.

## Authentication and security

The API client uses the IC-004 routes unchanged, an environment-configurable
API origin defaulting to `http://localhost:8000`, and credentialed fetches. It
bootstraps CSRF before unsafe requests and again after successful login to
account for rotation. CSRF state is held only in module memory; passwords,
sessions, and authentication tokens are never written to browser storage. No
JWT or mock production authentication was introduced.

Invalid credentials receive generic UX while network failures are distinct.
Duplicate submissions are disabled. UI role visibility is only a convenience;
backend policy remains authoritative and App Admin does not imply an IT role.

## Dependency decision

No frontend package or lockfile existed. The initial Next.js 14 candidate
produced critical production advisories, so the implementation uses the
then-current Next.js 16.4.3 and React 19.3.1. Vitest was upgraded to 5.0.5 to
remove development-tool advisories; the final full `npm audit` reported zero
vulnerabilities. The generated version-specific `AGENTS.md`
is tracked as recommended by Next.js 16.

## Native browser verification

A temporary ordinary active user was created in the approved native MySQL
database, exercised only by Playwright through installed Microsoft Edge against
the live Next.js and Django servers, and removed immediately afterward. No
credential was committed or recorded in task documentation.

## Pull request

- PR: [#8](https://github.com/acarbonilla/it_copilot/pull/8)
- Target: `feature/core-platform`
- Merge remains prohibited pending SOL review of the exact head.

## IC-005-REV-01 — cross-tab CSRF recovery

`unsafeRequest` now retries at most once and only when the first mutation fails
with the structured HTTP 403 code `csrf_failed`. It fetches a current token from
the CSRF bootstrap endpoint before the one retry. Invalid credentials, network
errors, unrelated 403 responses, and every other failure are returned without
retry. A second `csrf_failed` is returned directly, preventing an unbounded loop
or repeated unintended mutation. All attempts retain `credentials: "include"`.

The successful-login CSRF refresh remains in place, so subsequent mutations use
the post-login rotated secret. Unit tests cover stale-token login and logout,
non-retry boundaries, and retry exhaustion. The browser test now uses two pages
in one browser context to reproduce Django cookie rotation across tabs.
