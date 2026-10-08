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


## V0.2 hardening: Agent view and canonical verifier

The reviewed `visibility.json` is an explicit per-task allowlist of support files.
Agent materialization includes only catalog solution files plus those reviewed
build/runtime/assets. Unknown paths default to hidden. This covers all 225 tasks:
`.meta`, `.docs`, `.approaches`, `.articles`, declared tests, reference solutions,
and 37 additional verifier-only files in 24 tasks are absent. The 11 tasks with
approaches/articles are covered by the real catalog contract test. Generic Catch,
Gradle/Jest configuration, required Java/Go helpers, grep text corpora and the
explicitly supplied `go--counter` implementations remain available. Test commands
in build configuration are not hidden assertions; C++'s official default test
build target still requires tests that are intentionally unavailable to the Agent.

Two reviewed files require embedded-test masking. Rules are selected by task,
path, pinned source hash and Rust syntax, not keyword detection:

- `rust--doubly-linked-list/src/pre_implemented.rs`: remove only the two doctest
  comment regions in the Agent copy. Preserve helper implementation and marker
  declarations. This helper is excluded from candidate scope. The verifier copies
  the pristine helper byte-for-byte, independent of any Agent edits.
- `rust--react/src/lib.rs`: mask the reviewed test-only documentation, retaining
  the public type requirement. Freeze the Agent-view implementation diff. In a
  pristine verifier, parse the candidate with tree-sitter and locate exactly one
  public top-level `ComputeCellId` struct. Replace its attached documentation with
  the complete original documentation bytes from the pinned source. Preserve all
  implementation bytes outside that documentation. Candidate comments cannot
  supply, remove, replace or wrap the official doctest block.

Restoration rejects missing/duplicate/nested/non-public anchors, crate attributes,
non-built-in derive/other anchor attributes, and syntax errors. A narrowly
identified tree-sitter 0.24 grammar error for the official reference's valid
lifetime-first `dyn 'a + Fn(...)` syntax is tolerated; no source rewriting occurs,
and rustc remains authoritative. Unknown structural changes fail closed. Deleting
react's test-host file is rejected. Cargo.toml already lies outside candidate
scope under the pinned Aider ignore rules, so canonical build/test configuration
is preserved regardless of Agent edits. These are documented limitations of
the protected candidate merge, not changes to official tests or official grading.
The declarations' fields, surrounding types and function implementations remain
editable. Other Rust files are not automatically masked or restricted.

Invariant: every reconstructed react anchor has exactly the pristine official
documentation bytes, regardless of candidate documentation. Preparation records
canonical-JSON policy hash (independent of host line endings), original/view
hashes and exact masking regions. Verification records
pristine/candidate/canonical hashes in immutable evidence. Candidate patches stay
in Agent-view coordinates, so hidden test text never enters those patches.
Canonical workspaces and upstream checkouts are never reconstructed from Agent
support/test files. The default official test command is unchanged. A separate
free control enables `advanced` for doubly-linked-list to exercise its optional
compile-fail checks; it does not redefine the official score.

`go--counter` is an upstream deprecated test-authoring exercise: its declared
solution is an empty `counter.go`, while `counter_test.go` is an empty test template.
ABK preserves the pinned scope and supplied test subjects. Discovery support is
not a claim that the upstream task defines a useful non-vacuous correctness test;
no local replacement grading or candidate expansion is introduced.

The Rust controls also found that Docker's non-root UID can use GID 0: granting
only `o+rx` on `/root` is insufficient. Rebuild the toolchain image with the current
builder (`a+rx` on that directory). This grants toolchain traversal, not host
filesystem access, and changes neither upstream sources nor evaluator commands.

Free controls (Linux, pinned checkouts and the rebuilt local image required):

```sh
ABK_TEST_POLYGLOT_DOCKER=1 ABK_POLYGLOT_IMAGE=your-rebuilt-image \
  uv run pytest tests/test_polyglot_docker.py --basetemp=/tmp/abk-new-control-directory
```

Use a fresh output directory to retain earlier control failures. These tests run
four tasks with starter/reference code, no models; they also check Agent-view
builds, canonical doctest execution and a deliberately invalid type relationship.
