# Current limitations (V0.2 development)

- The internal benchmark has eight small Python tasks. It is integration evidence,
  not a broad coding-capability ranking or official SWE-bench result.
- Nexus v0.2.0 and Codex 0.155.1 use public CLI interfaces. Agent source is unchanged.
  Model inputs are unavailable; model outputs are partial; missing measurements
  remain null. No pinned pricing table means cost is null, never zero.
- Common ModelSpec does not imply equivalent model transports or controllable
  generation parameters. Nexus uses Chat Completions; Codex API uses Responses.
  Unsupported explicit fields are rejected. ChatGPT login runs are smoke only.
  Real Codex API-provider inference is NOT RUN. Real optional Judge acceptance is
  COMPLETED; its four quality scores do not replace the deterministic verifier.
- `model` in schema v2 records the configuration generated for the Agent, not a
  proof of the provider's server-side model version, routing or defaults. Old run
  manifests remain untouched and have incomplete comparability information.
- Docker is required for ChatGPT auth-cache injection and isolated acceptance.
  Host execution is trusted local development only. Docker uses network bridge
  for the Agent; micro_swe verification uses network none. Public adapters record
  their verifier conditions separately; this is not an egress allowlist.
- An Agent necessarily sees its own inference credentials. V0 does not defend
  against credential exfiltration by a malicious Agent. Secret redaction protects
  known literal credential values; it is not general data-loss prevention.
- micro_swe candidates are UTF-8 text only, bounded to 20 MB, without symlinks
  or binary files. Public Git-patch collection supports binary changes, deletions
  and safe repository symlinks with a 50 MB per-file bound; Polyglot narrows this
  to regular official solution files. POSIX executable modes can be preserved on native
  Linux; Windows bind mounts cannot prove those permissions.
- Candidate collection is synchronous and size-bounded; its elapsed budget is
  checked after collection. A pathological filesystem stall is not hard-preempted.
- Rule-based suspected ownership is heuristic with evidence and confidence, not
  a causal proof or a model-quality verdict. Single-run changes are stochastic.
- Viewer is loopback-only, read-only, caps pages/artifacts at 1 MB and shows the
  newest 200 runs. Full local evidence stays available on disk.
- A non-fatal Starlette TestClient warning recommends httpx2. Production Viewer
  does not depend on httpx; tests currently use the locked httpx version.
- Public adapters discover all 100 FeatureBench Fast, 300 SWE-bench Lite and
  225 Polyglot tasks. Full-suite execution is NOT RUN. The implementation status
  records exact real smoke evidence; Qoder acceptance is pending configuration.
- Polyglot uses one Agent execution with hidden tests and official test semantics;
  it is not directly comparable with Aider two-round scores. Its verifier permits
  network access for language dependencies and writes into a fresh disposable
  workspace. Official tests and references are never taken from the Agent workspace.
- Public benchmark execution requires Linux/WSL with ext4 workspaces. Windows
  Docker/pytest temporary-directory ACL failures reproduce on V0 as well.
- No distributed execution,
  PostgreSQL, Redis, queues or automatic production publication is included.

- Harness discovery is source-level only. A new Agent may require reviewed extensions
  to TOML configuration, authentication or the limited wire_api enum; there is no
  general plugin system. Repeated-tool analysis recognizes only verified Nexus/Codex
  public input shapes. See [adding a Harness](adding-a-harness.md).
- Stagnation detection is deferred because complete per-step workspace mutation
  evidence is unavailable. Repeated tool inputs alone are not proof of stagnation.
