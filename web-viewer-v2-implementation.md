# AgentBenchKit Web Viewer V2 implementation

Status: local implementation and regression; cloud delivery pending final validation.

## Scope and preserved baseline

Owner authorized on 2026-11-09 an exception to the historical V0.2 branch rule in
AGENTS.md and docs/v0.2-implementation.md. Work is isolated in branch
`codex/web-viewer-v0.3`, worktree `.agentbenchkit/worktrees/web-viewer-v03`.
Original branch/workspace is not switched, reset, staged, or committed by this task.
No main merge or evaluation-core changes are part of the Viewer delivery.

Baseline `0619ef1` preserves existing Pi Harness, Runtime, CLI, FeatureBench cleanup,
SWE-bench change, tests and Pi documentation on parent `a5ce6ec`.
Before creating it, 181 files were copied and SHA256-verified in
`.agentbenchkit/viewer-baseline/20261109T020135`, with original binary diff and manifest.
Historical report and raw evidence ZIP are preserved outside Viewer commits.
CRLF-only copies in the isolated worktree were normalized to the identical Git content.
ABK package/runtime version stays 0.2.0; **Viewer V0.3** is a presentation release.

## Design and data compatibility

- Existing FastAPI/Jinja/CSS/JavaScript stack; no new framework or browser CDN.
- Viewer-local `presentation.py` reads existing manifest/sample/execution/verifier,
  candidate diff, JSONL and already-saved analysis. No required new evidence fields.
- SQLite is not used or migrated by Viewer. Files remain the source of truth.
- Unknown usage and absent verifier fields remain N/A, not zero or failure.
- Execution FINISHED, Agent outcome, official verifier and end-to-end success remain separate.
- Existing RCA is displayed with its rule version and uncertainty, never regenerated.
- Run metrics count logical samples with saved results, not every physical retry.
  Duration is observed Agent-process duration, not batch wall clock.
- Current sample metrics use the latest physical execution by started_at;
  all execution evidence remains accessible. No cross-attempt call-ID pairing.
- Explicit multiple read-only roots allow formal and Pilot results in one service
  without symlinks. Duplicate Run IDs are rejected. Cross-root Compare is not supported.

## 25-item delivery checklist

| # | Requirement | Status / evidence |
|---|---|---|
| 1 | P0 Outcome diagnosis | Implemented: independent status dimensions, next action, known RCA phase |
| 2 | P0 structured Verifier | Implemented: patch/apply/resolved, F2P/P2P counts and failed tests |
| 3 | P0 failed-log navigation | Implemented: safe references, missing reason, sample return |
| 4 | P0 exception summary | Implemented: structural Python/pytest frames and exception records; raw fallback |
| 5 | P0 trajectory timeline | Implemented: actual seq vs native Step, tool/assistant/model summaries, event fields |
| 6 | P0 search/filter | Implemented: whole-file streaming search, tool/type/error/change/test/call ID, pagination |
| 7 | P0 Diff reader | Implemented: file grouping/search, old/new lines, lexical highlighting, collapse, copy |
| 8 | P0 cross-evidence navigation | Real Packaging chain PASS; file-text trajectory associations labeled weak |
| 9 | P1 information architecture | Implemented: Outcome, Failure, Patch, Trajectory, RCA, Raw; prompt collapsed |
| 10 | P1 execution summary | Implemented: duration, steps, tools/failures, model calls, input/output/total usage |
| 11 | P1 key events | Implemented: visible shortcuts and error styling |
| 12 | P1 repeated calls | Implemented: identical tool/argument SHA256 groups and event positions; no loop verdict |
| 13 | P1 RCA explanation | Implemented: saved owner/score/observations/evidence/uncertainty; no probability claim |
| 14 | P1 log reader | Implemented: numbered bounded pages, search, highlight, copy, download; exception frames collapsed |
| 15 | P1 copy investigation | Implemented: Markdown IDs, verdict/tests/exception/location/patch/trajectory/RCA |
| 16 | P1 metric definitions | Implemented: scope/denominator/missing explanations and preserved Credits distinctions |
| 17 | P2 Run Overview | Implemented: official outcomes, terminal samples, timeout/execution/verifier errors, usage |
| 18 | P2 task matrix | Implemented: 50-task contract, multi-filter/search/sort, 25-row pages, saved client filters |
| 19 | P2 investigation queue | Implemented: finished+fail, timeout/error, verifier error, pass without E2E, missing usage |
| 20 | P2 distributions | Deferred: sortable individual duration/token values provided; no misleading incomplete histogram |
| 21 | P2 Compare enhancement | Existing comparison retained, paginated/searchable; no new causal claims or token-delta charts |
| 22 | Library and generic evidence UX | Implemented: 15-run server pages, 20-field structured record drilldown, bounded long text |
| 23 | Read-only/security/partial writes | Local regression: traversal/XSS/missing/truncation/bounded pages/unchanged hashes |
| 24 | Isolated cloud deployment | Pending; independent loopback service, source/environment and resource limits |
| 25 | Cloud acceptance and rollback | Pending; old service retained; final commands/receipts to be added |

## Evidence association rules

- Official failed test names are exact report entries. Searching log text is labeled a lookup,
  not proof that every matching log line belongs exclusively to that test.
- Exception type/message require a structural exception line. File/line require actual stack frames.
- Stack -> diff uses source path/new line; absence of a matching hunk must not invent code.
- File -> trajectory is literal text search, explicitly a weak association.
- Tool call/result association uses explicit native Call ID within one trajectory only.
- RCA references resolve against the authorized Run, or the sample-relative directory.
  Unresolvable/absolute/out-of-root references show missing/unsupported, never arbitrary access.

## Safety and bounded access

All artifact endpoints use one allowlist and reject traversal, symlinks/junctions,
Windows ADS, scratch work directories and unauthorized suffixes. HTML is autoescaped;
JavaScript highlighting uses text nodes, never innerHTML. CSP is self-only, no executable
model output. No POST writes, evaluator calls, model calls, task changes or automatic repairs.
JSON records have size limits. JSONL/log lines stream with a per-line bound; pages have
row and response budgets. Run metrics read small records and bounded trajectory tails.
No persisted Viewer cache is required. Search may scan a large file sequentially; it does
not hold the whole trajectory in memory. Original downloads stream without regeneration.

## Validation

- Baseline: 229 passed / 37 skipped; Ruff PASS; mypy PASS. Initial long Windows test
  paths failed; rerunning under a shorter isolated basetemp fixed this without core edits.
- Full implementation regression: 242 passed / 37 skipped; Ruff PASS; mypy PASS.
- Focused Viewer/Credits regression after implementation: 28 passed.
- Offline JS matrix contracts: pagination, keyword search, investigation filter, sorting,
  session-state persistence PASS. This is not browser visual acceptance.
- Historical Packaging `20261008T204911Z-86cd0772`: full diagnosis chain PASS;
  52 linked routes returned 200; all 38 original evidence SHA256 values unchanged.
- Historical Pi PASS `20261107T173812Z-e8667261`: loaded. The old trace lacks final usage;
  correctly displayed N/A instead of inventing token values.
- Browser visual/click acceptance: NOT RUN. Browser tool denied local origin access due
  to its saved permission policy, including after the user changed terminal access.
  No alternate browser surface or origin bypass was attempted.
- No paid Agent/Verifier runs are launched by this UI task. Synthetic fixtures are labeled
  and never counted as real evaluation acceptance.

## Known limits

Generic JSON records are readable field trees, not domain-specific renderers for every
possible third-party schema. Python/pytest exception extraction is conservative; other
formats retain searchable original logs. Highlighting is lightweight lexical coloring,
not a full language parser. Optional distribution/Compare charts are deferred.
Browser layout and actual clipboard interaction still require browser authority to verify.

## Deployment and rollback

To be completed after local regression. Intended new port 8766; old 8765 remains running.
Original evaluation Runtime/source/environment, containers and scheduler are out of scope.
