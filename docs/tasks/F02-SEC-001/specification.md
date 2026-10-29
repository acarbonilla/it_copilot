# F02-SEC-001 — Activation Token Exposure Remediation

**Status:** G1 approved; implementation authorized; G2 review requested  
**Feature:** F-02 Identity & Administration  
**Baseline:** `c5aca48438b7aaca3b67c3fbb4753c432d7631ae`  
**Updated:** 2026-10-29

## Scope

Replace path-token activation with a static `/activate#token=<secret>` flow. The browser must read and scrub the fragment before rendering the form; tokens must not enter SSR HTML, server request URLs, logs, storage, audit rows, or database plaintext. Remove `/activate/[token]` and reject legacy token paths with a fixed non-reflecting response.

Add durable invitation delivery provenance. Migration `accounts.0004` classifies all pre-existing rows as `LEGACY_PATH`; all subsequently created invitations are `FRAGMENT_V1`.

Provide a controlled command that is dry-run by default and requires both `--execute` and an explicitly identified active, activated App Admin actor. Under the shared lifecycle guard and row locks, it revalidates every candidate, revokes every unconsumed/unrevoked legacy invitation, reissues only unexpired invitations for genuinely pending inactive accounts, and never reissues expired or otherwise ineligible records.

## Acceptance criteria

1. Static fragment activation is CSRF-protected, single-use, expiring, digest-only, and returns bounded generic errors.
2. Legacy path requests return 404 without reflecting or logging the path token in Next.js development output.
3. Existing/new provenance is `LEGACY_PATH`/`FRAGMENT_V1` respectively.
4. Dry-run makes no changes; execution is actor-attributed, locked, revalidated, idempotent, and atomic per invitation.
5. Delivery, audit, or database-commit failure rolls back lifecycle state and removes any newly created artifact.
6. Expired legacy invitations are revoked without replacement.
7. Native MySQL, frontend, SSR/log scan, and real-browser evidence passes.

## Boundaries

No production remediation execution is authorized by this task. IC-024, permanent deletion, hosted delivery, ADR-001 changes, and feature/main merges remain excluded.
