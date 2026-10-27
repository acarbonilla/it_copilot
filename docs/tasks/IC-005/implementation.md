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
