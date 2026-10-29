# IC-012 Implementation Record

**Batch C implementation commit:** Pending commit creation

## Implementation

- `documents.jobs` owns claim, heartbeat, retry/failure, cancellation, and fenced publication services.
- `ProcessingJob` gains controlled failure code and completion timestamp fields. Forward migrations add these fields and lease/completion state constraints.
- Claim candidates are ordered deterministically and revalidated after acquiring the document/version/job lock chain.
- Attempt identity is the tuple `(job UUID, worker UUID, attempt_count)`. Lease expiry or any tuple mismatch rejects heartbeat, failure, and publication.
- Retry remains on the same unique job row, preserving the one-nonterminal-job constraint and preventing duplicate usable attempts.
- Document archive/delete calls job cancellation inside the existing lifecycle/audit transaction.

## Recovery behavior

An expired lease may be reclaimed until the third attempt. Database publication failure leaves the prior state intact and the worker moves the job to bounded retry where its lease is still valid. A process crash can leave only a private, unreferenced staging artifact; IC-016 reconciliation owns detection and quarantine of crash orphans.
