# IC-012 Specification - Database-Backed Processing Job Lifecycle

**Feature:** F-03 Documentation Management
**Batch:** C
**Baseline:** `ea47fe4f0d6a4555cb9ac449654910afc61ae318`

## Contract

- States are `PENDING`, `RUNNING`, `SUCCEEDED`, `RETRY_WAIT`, `FAILED`, and `CANCELLED`. Database constraints bind terminal states to a null nonterminal slot and completion timestamp, and bind lease fields exclusively to `RUNNING`.
- Claiming uses native MySQL transactions and row locks with deterministic `(available_at, created_at, id)` selection. If an earlier eligible job's document row is locked, the claimant skips that document and continues to the next ordered eligible job instead of reporting an empty queue. The canonical lock order is document, version, job.
- Each claim increments the attempt number, records a UUID worker identity, and grants a 60-second lease. The worker refreshes the lease every 20 seconds while isolated parsing is active.
- At most three attempts are allowed. Retry delays are five seconds after attempt one and 30 seconds after attempt two. Invalid/unsupported/corrupt content is terminal; bounded resource and infrastructure interruption may retry.
- Completion and heartbeat require the exact job, worker UUID, attempt number, `RUNNING` state, and unexpired lease. A reclaimed attempt fences every earlier worker.
- Archive or deletion transactionally cancels nonterminal jobs and versions. Critical lifecycle-audit failure rolls cancellation back with the document mutation.
- Publication is accepted only while the document is active, the version still belongs to it and remains its candidate, the job is not cancelled, and the exact lease remains valid.

No public processing endpoint or operator retry action is introduced in Batch C.
