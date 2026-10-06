# Phase 3 evidence

Runtime now persists the logical sample plan before scheduling and updates summaries
against that fixed denominator. Bounded asyncio concurrency is configurable.
Startup infrastructure retries produce unique physical execution IDs; once RUNNING
begins there is no full-Agent retry. Setup/prepare, Agent, verification and cleanup
have deadlines; collection has bounded artifact sizes and elapsed-budget validation.
An optional overall deadline reduces the remaining execution/verification budgets.

Fault injection verifies startup retry/exhaustion, no hidden post-start retry,
concurrency bounds, prepare timeout, cancellation with queued samples, and cleanup
failure preserving the original successful verdict. Real Docker cancellation confirms
that the container is stopped before candidate collection. Total suite: 86 PASS
with ABK_TEST_DOCKER=1; six Docker tests otherwise explicitly skip.

OS-held leases distinguish live from abandoned runs. `agent-bench recover` (also
called before new runs) marks abandoned incomplete records INTERRUPTED without
fabricating Agent outcomes. Recovery stops Docker resources bound by a unique name
and matching workspace ownership label. Windows Job Objects end descendants when
the runner dies; Linux recovery checks process start identity before killing a
recorded process group. Historical finished evidence is not rewritten.

Recovery is not checkpoint resume. Cleanup failures retain work and diagnostic
records. Local filesystem operations on bounded V0 text artifacts are synchronous;
collection reports exceeded budgets after finishing the bounded freeze operation,
so it never leaves a background copier racing verification or cleanup.
