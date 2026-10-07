# Judge diagnostics and retest

The user reported `judge_status=ERROR` for run
`20261007T085706Z-6489516b`, sample `sample-clamp-1`, at
`2026-10-07T09:16:24Z`. The old worker discarded the underlying exception;
its 31.859-second duration and generic error cannot identify the Provider failure.
That historical record is preserved, and its root cause remains **UNCONFIRMED**.

## Verified evidence

One minimal live diagnostic request used the same endpoint/model and original
request settings, with synthetic empty evidence (no project artifacts). It returned
parseable final JSON in 12.42 seconds: 247 prompt tokens, 751 completion tokens,
including 484 reported reasoning tokens. This confirms that this endpoint accepts
`qwen3.8-flash`, `response_format={"type":"json_object"}` and
`max_completion_tokens=2000` for that request. It does not establish success of the
real sample's rubric or explain the historical failure.

That initial diagnostics-only fix did not run the real sample. The later strict-schema
fix passed the full live acceptance below. No Provider-specific fallback or automatic
retry is used.

## Diagnostic contract

- Each failure keeps CLI exit code 2 and `judge_status=ERROR`, now with safe
  `error_details` in stderr and the new versioned Judge artifact.
- Diagnostics allowlist HTTP status, exception type, phase, Provider error
  message/code/type/parameter, and final-output token/finish metadata when available.
- HTTP error bodies are read up to 8 KiB plus an overflow byte. Non-JSON or oversized
  bodies are omitted. Individual text fields are redacted before truncating to 800
  characters; the worker diagnostic envelope is capped at 64 KiB by the parent.
- The configured key (including URL/JSON-escaped forms), bearer tokens and common
  `sk-` key patterns are redacted. Headers, raw bodies, private reasoning, worker
  stderr and Pydantic input/context dumps are not included in diagnostics.
- `finish_reason=length`, empty final content, invalid response JSON and invalid
  rubric schema remain errors; they never receive manufactured quality scores.
- Existing four-dimensional rubric, evidence-reference validation, time budget,
  correctness verdicts and historical analyses remain unchanged.

## Canonical model output and framework metadata

The model emits exactly one object with exactly one key, `dimensions`, whose value
is an array of four objects. Every dimension appears exactly once; every object
requires exactly `dimension`, `score`, `reason`, and `evidence_refs`:

```json
{
  "dimensions": [
    {
      "dimension": "test_quality",
      "score": null,
      "reason": "Not observable in supplied evidence.",
      "evidence_refs": []
    },
    {
      "dimension": "tool_use_quality",
      "score": null,
      "reason": "Not observable in supplied evidence.",
      "evidence_refs": []
    },
    {
      "dimension": "solution_quality",
      "score": null,
      "reason": "Not observable in supplied evidence.",
      "evidence_refs": []
    },
    {
      "dimension": "efficiency",
      "score": null,
      "reason": "Not observable in supplied evidence.",
      "evidence_refs": []
    }
  ]
}
```

`score` is a finite JSON number in [0, 4] or null, never a string or boolean.
`reason` is a string of 1-4000 characters. `evidence_refs` is an array of strings
that must match supplied artifact paths exactly. Non-null scores require evidence.
`JudgeOutput` is the single strict wire contract; its generated JSON Schema and a
complete structural example are embedded in the system prompt. Unknown fields,
missing fields, mappings in place of arrays and duplicate dimensions are rejected.
There is **no Provider shape normalization or silent field removal**.

After validation, the framework constructs persisted `RubricScores`, injecting
`judge_version=quality-v1` into each dimension. The enclosing artifact retains
framework-owned `analysis_version=quality-v1` (unchanged quality rubric), and records
`output_schema_version=judge-output-v1` and `prompt_version=quality-json-v2`.
Model-supplied version fields at any level are errors. Historical artifacts are
not reparsed or migrated when a new Judge artifact is written.

## Confirmed failure causes

Three historical ERROR artifacts are preserved:

- `ef25c327da2f4c09ad31804544f4efab.json`: exception swallowed by old worker;
  its specific cause remains unknown.
- `adbffb0e2e3548f0be3a8226c11aac77.json`: HTTP 200 with `finish_reason=length`,
  1998 completion tokens / 1960 reasoning tokens, only 126 final content characters.
  This request exhausted the old 2000-token budget; this is now evidence, not a guess.
- `195e2cb361514e00a3a620a8f80bb9f9.json`: 8192 tokens / low reasoning returned
  HTTP 200, `stop`, but validation reported `dimensions: tuple_type` and top-level
  `judge_version: extra_forbidden`. The old prose prompt failed to specify an array
  and the version field's location. The raw shape was not retained, so a mapping
  is a representative regression fixture, not a claimed copy of that response.

The fix removes prompt/schema ambiguity and separates model output from framework
metadata. It does not relax the Pydantic contract to accept arbitrary JSON.

## Full live acceptance: PASS

Run `20261007T085706Z-6489516b`, sample `sample-clamp-1`, model `qwen3.8-flash`,
endpoint `https://maas.qianwenaiapi.com/compatible-mode/v1`, credential reference
`DASHSCOPE_API_KEY`, max completion tokens 8192, reasoning effort low.
One full request after this schema fix passed; no fallback or retry was needed.

- CLI exit 0; HTTP 200; `finish_reason=stop`; `judge_status=COMPLETED`.
- Duration 21047 ms; prompt tokens 11301; completion tokens 1330, including
  825 reasoning tokens; total tokens 12631. No private reasoning retained.
- All four dimensions parsed under the strict wire schema; persisted rubric also
  passed strict JSON validation. Scores: test/tool-use/solution/efficiency = 3/3/3/3.
- New artifact: `judge/f0f559a29ce744fda95aed0f40842c17.json` within the run.
- Artifact SHA-256: `da479c543f89ad099c7ab040ca4454e7263abdf22c0f930c3bde799f7bce1bb9`.
- SHA-256 snapshots confirm all 23 pre-existing run files are unchanged, including
  all 3 historical ERROR Judge artifacts.
- Correctness remains `verifier_status=PASS`, `candidate_pass=true`, `sample_success=true`.
- Local audit: `.agentbenchkit/judge-schema-acceptance-20261007T100017Z.json`.
  Runtime artifacts/audit stay local and are not committed.

## Owner acceptance command

From `D:\WorkSpace\AgentBenchKit`, with the credential already set in the environment:

```powershell
uv run agent-bench judge 20261007T085706Z-6489516b sample-clamp-1 --model qwen3.8-flash --endpoint https://maas.qianwenaiapi.com/compatible-mode/v1 --key-env DASHSCOPE_API_KEY --max-completion-tokens 8192 --reasoning-effort low
```

Every invocation creates a new Judge artifact. The generic CLI defaults remain
2000 tokens / omitted reasoning effort; use the explicit settings above to repeat
this accepted configuration. The owner's independent acceptance is still pending.

## Automated verification

18 additional strict-schema regression cases cover the recorded error types,
canonical prompt/schema agreement, framework versions, unknown/missing fields,
array shape, duplicate/missing dimensions, numeric bounds, forbidden coercions,
and preservation of run evidence and historical Judge artifacts across errors and
success. Full suite: **175 passed / 7 Docker skipped**; Ruff and strict mypy for
Windows and Linux pass. Previous HTTP/deadline/redaction checks remain in place.
