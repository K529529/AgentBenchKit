# AgentBenchKit Web Viewer V2 implementation

Status: core Viewer deployed at cloud commit `414d7c1`; local follow-up refinements validated.
After the owner requested minimal cloud work during the active evaluation, no further
bulk cloud checks or deployment replacements are performed. Follow-up refinements remain
local for optional integration after the evaluation finishes.

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
| 6 | P0 search/filter | Implemented: whole-file streaming search, tool/type/error/change/test/call ID, exact native Step/seq, pagination |
| 7 | P0 Diff reader | Implemented: file grouping/search, old/new lines, lexical highlighting, collapse, per-file page-fragment copy |
| 8 | P0 cross-evidence navigation | Real Packaging chain PASS; file-text trajectory associations labeled weak |
| 9 | P1 information architecture | Implemented: Outcome, Failure, Patch, Trajectory, RCA, Raw; prompt collapsed |
| 10 | P1 execution summary | Implemented: duration, steps, tools/failures, model calls, input/output/total usage |
| 11 | P1 key events | Implemented: visible shortcuts and error styling |
| 12 | P1 repeated calls | Implemented: identical tool/argument SHA256 groups, explicit-ID result summaries and event positions; no loop verdict |
| 13 | P1 RCA explanation | Implemented: saved owner/score/observations/evidence/uncertainty; no probability claim |
| 14 | P1 log reader | Implemented: numbered bounded pages, search, highlight, copy, download; complete Python stacks and summary frames collapsed |
| 15 | P1 copy investigation | Implemented: Markdown IDs, verdict/tests/exception/location/patch/trajectory/RCA |
| 16 | P1 metric definitions | Implemented: scope/denominator/missing explanations and preserved Credits distinctions |
| 17 | P2 Run Overview | Implemented: official outcomes, terminal samples, timeout/execution/verifier errors, usage |
| 18 | P2 task matrix | Implemented: 50-task contract, multi-filter/search/sort, 25-row pages, saved client filters |
| 19 | P2 investigation queue | Implemented: finished+fail, timeout/error, verifier error, pass without E2E, missing usage, missing terminal-event investigation hint |
| 20 | P2 distributions | Implemented locally: duration/token/saved-tool distributions, coverage, median/P90, top-10 and IQR investigation hints |
| 21 | P2 Compare enhancement | Implemented locally: regression/improvement filters, one-to-one signed duration/token deltas, coverage and comparability warnings |
| 22 | Library and generic evidence UX | Implemented: 15-run server pages, 20-field structured record drilldown, bounded long text |
| 23 | Read-only/security/partial writes | Local regression: traversal/XSS/missing/truncation/bounded pages/unchanged hashes |
| 24 | Isolated cloud deployment | PASS: `abk-viewer-v03.service`, loopback 8766, dedicated venv/source, locked dependencies, CPU/memory limits |
| 25 | Cloud acceptance and rollback | PASS for backend HTTP/integrity: 1,265 checks, 605 frozen evidence files unchanged; old Viewer retained |

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
- Full implementation regression: 243 passed / 37 skipped; Ruff PASS; mypy PASS.
- Focused Viewer/Credits regression after implementation: 28 passed.
- Offline JS matrix contracts: pagination, keyword search, investigation filter, sorting,
  session-state persistence PASS. This is not browser visual acceptance.
- Historical Packaging `20261008T204911Z-86cd0772`: full diagnosis chain PASS;
  52 linked routes returned 200; all 38 original evidence SHA256 values unchanged.
- Historical Pi PASS `20261107T173812Z-e8667261`: loaded. The old trace lacks final usage;
  correctly displayed N/A instead of inventing token values.
- Browser visual/click acceptance: NOT RUN. Browser tool denied local origin access due
  to its saved permission policy, including after the user changed terminal access.
  User-authorized Chrome retry also failed; no policy bypass was attempted.
- No paid Agent/Verifier runs are launched by this UI task. Synthetic fixtures are labeled
  and never counted as real evaluation acceptance.

## Known limits

Generic JSON records are readable field trees, not domain-specific renderers for every
possible third-party schema. Python/pytest exception extraction is conservative; other
formats retain searchable original logs. Highlighting is lightweight lexical coloring,
not a full language parser. Tool-call distributions require already-saved analysis; missing analysis stays N/A.
Histograms cover only saved samples, not the whole planned task set or unrecorded executions.
Browser layout and actual clipboard interaction still require browser authority to verify.

## Deployment and rollback

Deployed revision: `414d7c1`. New service: `abk-viewer-v03.service`.
Listen: `127.0.0.1:8766`. Old service `abk-formal50-viewer.service` on 8765 is unchanged.
Source: `/data/abk/viewer-v03/releases/414d7c1`; venv: `/data/abk/viewer-v03/venv`.
Dependency installation was corrected to `uv sync --frozen --no-dev` against the committed
lockfile before acceptance. The initial unconstrained dependency install was superseded.
Formal root: `/data/abk/formal50/output/runs`; Pilot root: `/data/abk/pilot/runs`.
Backup: `/data/abk/viewer-v03/backups/20261108T182831Z` (UTC, November 9 local time).
Backup contains old Viewer files/config/overlay, source manifest, safe SQLite backup
receipts (or recorded absence) and frozen-evidence hashes. Cloud source has no `.git`;
its exact identity is preserved by source manifest and 106 actual source-file hashes.
No full formal experiment directory was copied or rewritten.

Resource controls: CPUQuota=25% of one CPU, MemoryMax=384M, TasksMax=32, Nice=10,
IOWeight=10; ProtectSystem=strict, explicit read-only roots, no privilege escalation,
no capabilities, secrets/Docker storage inaccessible, loopback-only network.
No background evidence polling, model/verifier work or scheduled index refresh occurs.
Requests do perform read/parse work, so repeated investigation during evaluation can
still consume the limited quota. The owner requested no further bulk cloud checks.

Cloud backend acceptance: 1,265 HTTP requests all returned 200 across the formal
50-task matrix and real Pilot samples/evidence. At that snapshot five formal samples
were complete; this is **not** a final experiment score. All 605 preselected frozen
evidence files and 106 source files retained SHA256. Formal Worker and old Viewer
PIDs were unchanged. New Viewer memory was 57,974,784 bytes (~55.3 MiB), NRestarts=0.
New-service restart for locked-dependency activation did not change those PIDs.
This proves the checked interval, not a guarantee of zero resource contention.

Windows: run the local `open-viewer.ps1` in `.agentbenchkit/viewer-delivery`, leave
its terminal open, then open `http://127.0.0.1:8766/`. It uses the existing authorized
SSH key and verified known_hosts file; no credentials are embedded or copied.
Select the formal Run from the library (the report has 50 tasks); Pilot runs remain
separate records. New finished samples appear after manual refresh, including final
results without upgrading Runtime or rerunning a task.

Service operations (on ECS):

```sh
journalctl -u abk-viewer-v03.service -n 100 --no-pager
sudo systemctl stop abk-viewer-v03.service
sudo systemctl restart abk-viewer-v03.service
```

Rollback: stop **only** `abk-viewer-v03.service`, keep using the original 8765 tunnel
and Viewer. No restoration of Runtime/data is needed because they were never replaced.
Do not restore an old SQLite snapshot over a live formal index merely to roll back UI.

### Follow-up revision deliberately not redeployed during formal evaluation

After the first deployment, local review added explicit custom stdout/stderr reference
links, bounded evidence-directory pagination, a short task-description preview,
null-native-event tolerance and preservation of zero-millisecond durations.
These pass local tests and remain a separate follow-up commit. The cloud service is
intentionally still `414d7c1` per the owner's latest resource-contention instruction.
Distribution and Compare enhancements are now implemented and validated locally. Browser visual
acceptance remains NOT RUN; the owner explicitly deferred this on 2026-11-09.

Detailed local receipts are in `.agentbenchkit/viewer-delivery/acceptance.json`,
`deployment.json`, and `.agentbenchkit/viewer-acceptance/packaging.json`; these are
local runtime records, not committed experimental artifacts.


## Final local completion — 2026-11-09 (after browser acceptance was deferred)

- Completed all remaining P2 presentation enhancements without new dependencies: three
  coverage-aware distributions, median/P90/max, top-10 drilldown and Q3 + 1.5 IQR
  outlier investigation links. Missing values do not become zero. Histograms require
  complete coverage of the observed saved samples; known-subset statistics are labeled.
- Compare now includes regression/improvement/inconclusive filters and signed B-minus-A
  Agent-duration/token differences. Only one-to-one, known sample pairs qualify;
  zero baseline has no percentage. Condition warnings stay visible; no causal claims.
- Compare filter memory is scoped to the selected run pair. Existing matrix pagination,
  filtering, sorting and sample navigation remain in place.
- Missing terminal events are an explicit investigation hint (possibly still running),
  not a failure verdict. Null native event metadata is tolerated. Deleted diff files
  preserve their actual source filename; quoted paths with spaces support navigation.
- Final full local regression PASS: **247 passed, 37 skipped**. Ruff PASS; mypy PASS
  (91 source files); offline Node interaction contracts PASS. The only pytest warning
  is the existing Starlette/httpx TestClient deprecation, not an application failure.
- Added tests cover incomplete/invalid measurements, zero values, percentiles and
  outliers, ambiguous multi-sample pairing, null/partial traces, read-only comparison,
  and deleted/quoted diff files. Synthetic checks are not real-agent acceptance.
- Rechecked local historical Packaging library/run/sample routes: all 200, NameError
  evidence present; all 10 files in that local run retained SHA256. This is a separate
  smaller checkpoint from earlier detailed acceptance receipts, not a replacement claim.
- Original workspace: all 181 baseline manifest entries unchanged (zero hash drift).
  Existing Pi/CLI/Runtime content and unrelated historical report remain untouched.
- Browser visual, real clicks, responsive rendering and actual clipboard acceptance:
  **NOT RUN**. Both browser surfaces reported saved-policy denial; restart also briefly
  produced a browser-control process error. User explicitly authorized completing local
  work without further browser troubleshooting. Backend/DOM contracts are not visual QA.
- **No cloud access, deployment, restart or acceptance requests in this final phase.**
  Cloud remains on 414d7c1. New local commits require separate integration after the
  active evaluation; do not mistake local completion for deployment of these additions.


## Requirement re-audit after owner challenged premature completion

The earlier statement that all remaining work was complete was too broad. A second
code-level review found actual gaps beyond deferred visual QA. The following were
corrected locally rather than silently retaining the earlier checklist wording:

| Requirement | Gap found | Correction and evidence |
|---|---|---|
| P0-6 Step/event navigation | Only physical-line positioning existed | Separate exact native Step and seq filters; HTTP tests distinguish seq 40, physical line 3 and Step 50, plus empty results |
| P0-7 copy snippet | Only whole-page copy | Per-file current-page fragment copy; log/diff copying joins code lines with newlines, excludes line-number gutters |
| P1-4 repeated call results | Repeat groups linked starts but omitted result summaries | Explicit Call ID result summaries and result-line links; absent IDs/results labeled unknown, no inferred pairing |
| P1-6 stack folding | Only sample exception frames collapsed | Complete Python Traceback blocks collapse in the log reader; partial/page-split stacks remain visible; offline DOM test checks both |
| P2-1 missing results | No separate count | Count tasks lacking saved sample results; explicitly not labeled not-executed or failed |
| P2-2 missing-result filter | Placeholder rows omitted state attributes | NO_RESULT filter targets rows without sample records |
| P2-5 comparison entry | Dropdown limited to current library page | Editable Run IDs with current-page suggestions permit cross-page choices; existing authorized-root checks remain |

Audit surfaces: library/compare launch, run matrix and task map, sample section
navigation, failed-test disclosures/log links, patch file and line views, timeline
search/detail/Call ID links, repeated-call results, RCA references, generic field
reader, file directory, raw/download and error return paths. This is source and
HTTP/DOM-contract inspection, **not** a claim that every control was visually clicked.

Remaining precise limits (do not label these visually accepted):
- Actual browser rendering, responsive layout, keyboard behavior and clipboard writes
  remain NOT RUN by explicit owner waiver. CSS presence does not prove usability.
- Stack grouping recognizes complete standard Python tracebacks within a loaded page;
  pytest frames have the sample-level structural summary, other formats stay readable raw.
- Diff syntax coloring is lexical, not a language-aware editor. Copy is the loaded
  file fragment, not unshown file contents. Original full-file download is retained.
- JSON unknown schemas use a paginated field tree, not a custom renderer per provider.
- Tool-call distributions use saved analysis; no analysis means N/A, not an implicit replay.
- A missing terminal marker in the bounded trajectory tail is an investigation hint,
  not proof of corruption. Missing samples cannot distinguish not-started from in-flight.
- Latest enhancements are not cloud deployed. The previous 414d7c1 service remains;
  no new cloud operations were performed during this audit.

This supersedes any interpretation of the earlier 25-item table as full browser or
latest-cloud acceptance. Implemented, locally verified, visually verified and deployed
are separate statuses.


### Product review round 2
After round-1 commit, found unbounded visible failed-test and repeat-group lists.
Added independent search + 10-row pagination for F2P/P2P and repeated groups,
collapsed each group, bounded the nested call list, and added previous-page
navigation to structured records. Corrected invalid paragraph/details nesting.
Focused Viewer tests 25 passed; offline Node tests verify independent list state
and paging. Actual browser rendering remains NOT RUN.


### Product review round 3
Post-commit review found absent PREPARING/COLLECTING filters, no single reset
control, and default framework JSON for invalid query/unknown routes. Added these
filters, reset buttons, a concise status glossary, HTML error recovery and a home
fallback when browser history is empty. Focused Viewer regression 26 passed;
Ruff/mypy/offline Node contracts PASS. Rendering and real clicks remain NOT RUN.

### Product review round 4 — resumed in browser-enabled chat
Preserved the pending filtered-reader backtracking and long-text progress changes.
Added bounded page-start trails for previous/next navigation and physical line ranges;
structured long strings show character ranges and previous segments.
PASS: 19 tests in test_viewer_workbench.py and test_viewer.py; Ruff; mypy (91 files);
offline Node interactions. Chrome live historical Packaging log pagination visited
1–60, then 61–75, then returned to 1–60. Broader browser review continues in round 5.
No cloud operations; the deployed version remains 414d7c1.

### Product review round 5 — browser-led layout revision (2026-11-09)
The owner rejected the previous layout after seeing it live, and then authorized
additional review/commit/push cycles beyond the initial five-round ceiling.
Reworked actual rendered pages: padded content panels, compact sample identity,
consistent outcome cards, readable boolean labels, seconds/token formatting,
two-column test groups, single empty states, responsive controls, and bounded
long identifiers. Timeline common search is separate from expandable precise
Step/seq/Call ID controls. Raw/download remains under evidence-source disclosure.
Added return-to-timeline for complete events and clamped out-of-range record/text
pages rather than showing impossible ranges.

PASS: full local pytest **250 passed / 37 skipped**; Ruff; mypy (91 source files);
Node interaction contracts. Synthetic fixtures are UI tests, not Agent acceptance.
Chrome live checks: historical Packaging failure test -> log -> metadata.py:367
patch -> explicit Step 50 apply_patch (physical line 380) -> Call ID result (382);
log next/back; actual summary and diff-fragment clipboard paste; complete event
field reader; RCA disclosure. Separate localhost:8877 synthetic 50-task fixture:
25-row pagination, page restoration after sample return, FAIL filter (12/50),
search, token sorting, 23-test list search/pagination, missing evidence, and Python
stack folding. IAB 390px responsive sample rendering inspected, no document-level
horizontal overflow. Chrome remains the primary final user surface.

These checks supersede earlier NOT RUN statements only for the cases explicitly
listed here. Compare, remaining raw-directory navigation and final post-commit
review continue next. Screenshots are local in .agentbenchkit/viewer-browser-review.
No cloud access/deployment, no real Agent/Verifier invocation, no main merge.

### Product review round 6 — 2026-11-09

Corrected comparison defaults to choose two runs from the same evidence source.
Compare now displays the same recorded process duration as sample detail, preserving
N/A when unavailable. Synthetic sample pages retain the preview warning; missing
logs no longer suggest nonexistent reader links. Run outcome cards now precede the
compact operational snapshot, with detailed counting notes collapsed.

Validation: full local pytest 251 passed / 37 skipped, Ruff, mypy (91 files), Node
interactions PASS. Chrome verified default selection, comparison durations, missing
values and the real Pi run layout. No deployment or evaluation execution performed.
