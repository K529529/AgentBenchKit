# Aider Polyglot: one Agent execution, hidden tests

All 225 tasks are available for discovery/selection/config generation: C++ 26,
Go 39, Java 47, JavaScript 49, Python 34 and Rust 30. Discovery needs no model,
Docker or downloaded exercise repositories.

Pinned upstream sources:

- Dataset https://github.com/Aider-AI/polyglot-benchmark at
  `7e0611e77b54e2dea774cdc0aa00cf9f7ed6144f`.
- Official harness https://github.com/Aider-AI/aider at
  `5dc9490bb35f9729ef2c95d00a19ccd30c26339c`.

## Evaluation protocol

The owner selected **one autonomous Agent execution plus official tests**, with
**official test files hidden during that execution**. The prompt concatenates
upstream introduction/instructions/append text and instructions_addendum. The
Agent gets starter solution files and necessary build files, without official
tests, examples or .meta reference solutions. No framework-managed repair round
is added after independent test feedback.

Candidate scope is upstream config.json's solution list, minus the same ignored
files as the official harness (including Cargo.toml and CMakeLists.txt). Changes
to build or test files cannot replace the independent verifier's originals.
The frozen candidate contains the allowed solution delta, including deletions.
The Agent's trajectory remains separate evidence of its physical execution.

A fresh verifier workspace reconstructs the official exercise, excludes reference
solutions and restores official tests. It executes the original AST bodies of
run_unit_tests and cleanup_test_output from the pinned official source, without
rewriting them or importing Aider's model clients. The diagnostic dump dependency
is print. Commands, test restoration, Java annotation handling, JavaScript script,
C++ script and 180-second test timeout are upstream-owned. ABK uses the same
truthiness-of-errors single-round outcome as upstream run_test_real, including its
test-timeout failure outcome. Missing/failed verifier execution remains ERROR.

The image supplies all six language toolchains. The verifier may use network
access for language dependency resolution, as official builds/runners do; it
receives no Agent/provider credentials. Its disposable workspace is writable for
compilers. Exact image ID and source fingerprints are recorded.

**Results are not directly comparable with official Aider two-round scores.**
This label is part of each task's manifest and official test report.

## Commands (Linux/WSL)

```sh
agent-bench tasks aider-polyglot
agent-bench make-config aider-polyglot --all-tasks --output polyglot-plan.json
python -m agentbenchkit.benchmarks.polyglot.build --help
agent-bench make-config aider-polyglot \
  --task python--affine-cipher --task javascript--affine-cipher \
  --dataset /absolute/polyglot-benchmark --official-source /absolute/aider \
  --agent-image abk-polyglot-nexus:v0.2.0 --output two-polyglot.json
agent-bench run aider-polyglot nexus --env docker \
  --benchmark-config two-polyglot.json --model-config nexus-model.json \
  --output /tmp/abk-polyglot-results --prepare-timeout 180 --agent-timeout 600 \
  --verify-timeout 300 --max-steps 30 --startup-retries 0 --concurrency 1
```

Use clean LF source checkouts at the pinned commits and an ext4 output/workspace.
The image builder starts with upstream's benchmark Dockerfile, adds a separate
unchanged Nexus environment and makes its installed Rust toolchain accessible to
the non-root runtime. Node 20 and the official test commands are retained; npm 10.9.9 replaces the
stalled 10.8.2 installer. Network diagnostics/timeouts affect installation only.
Dataset contents are checked against the bundled file hashes before execution.
The upstream dataset and Exercism language repositories retain their licenses;
the official Aider source is Apache-2.0. No reference code is bundled into ABK.

Real acceptance status is recorded in implementation-status.md. Full-suite model
execution is never required to discover or generate configuration for all tasks.

## Upstream Jest dependency correction (owner approved 2026-10-08)

The pinned Aider Dockerfile installs unversioned `jest`, which resolved to 30.5.2.
The pinned Polyglot JavaScript package.json requires `^29.7.0` and its tests use
`toThrowError`, removed in Jest 30. The official affine-cipher reference solution
therefore passed 14/16 tests and failed two on the missing assertion method.
These failed control artifacts are preserved; they are not model outcomes.

The derived image explicitly installs Jest **29.7.0** and checks its reported
version. It labels the pin, which the adapter requires before execution. Official
test files, npm-test.sh, run_unit_tests and grading logic remain unchanged.
Reference and starter controls must be repeated before real Nexus smoke.


Revalidation completed: both Python and JavaScript starter solutions FAIL and
reference solutions PASS with Jest 29.7.0. Real Nexus smoke then completed exactly
two tasks, one in each language: Python PASS (16/16), JavaScript FAIL (14/16,
exception-message mismatch). Both candidates were frozen and cleanup completed.
See implementation-status.md for run IDs and evidence fingerprints. No model
retry or official-test change was used to turn the JavaScript result into a pass.
