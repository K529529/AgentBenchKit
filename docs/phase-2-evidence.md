# Phase 2 evidence

Real Nexus Docker run: `20261006T201551Z-18e0d730`.
Both clamp and stable_unique: FINISHED / COMPLETED / PASS, sample_success=true.
The same benchmark assets and verifier were used as the HostProcess run.
Resolved image identity is saved in the run manifest. All managed containers and
run work directories were removed; the saved-artifact credential scan found zero matches.

Five real Docker integration checks prove stdin-only credential injection does not
appear in Docker inspect metadata, timeout stops further writes, baseline candidates
fail and reference candidates pass in fresh containers, and evaluator-owned files
are read-only with no model key and network disabled. Offline + Docker suite: 77 PASS.
The image includes Nexus v0.2.0 from the pinned original commit without source edits.

Resource policy: 1 CPU, 512 MiB, 128 PIDs, read-only root filesystem, dropped
capabilities, no-new-privileges. Agent network is bridge; verifier network is none.
Only the ephemeral workspace and isolated home are mounted into the Agent container.
The verifier receives fresh reconstructed code and evaluator-owned protected checks.

V0 supports UTF-8 text candidates; binary files and links are rejected explicitly.
Windows bind mounts cannot serve as evidence of Unix executable-bit changes; the
current Python benchmark does not depend on these bits. Native Linux preserves them.
Runtime crash recovery, startup retries and broader lifecycle injection follow in phase 3.
