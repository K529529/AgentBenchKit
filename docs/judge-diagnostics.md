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

No final real-sample Judge acceptance was performed during this fix. The owner
will rerun it. There is no speculative Provider-specific fallback or automatic retry.

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

## Rerun with original settings first

From `D:\WorkSpace\AgentBenchKit`, with the credential already set in the environment:

```powershell
uv run agent-bench judge 20261007T085706Z-6489516b sample-clamp-1 --model qwen3.8-flash --endpoint https://maas.qianwenaiapi.com/compatible-mode/v1 --key-env DASHSCOPE_API_KEY
```

`--max-completion-tokens` (default 2000) and `--reasoning-effort` (default omitted)
are now explicit and recorded in every new Judge result. Provider support for a
requested value is required. If the new diagnostic confirms output truncation,
rerun with `--max-completion-tokens 8192 --reasoning-effort low`; this increases the
allowed output budget and changes the request configuration, so keep the previous
record for comparison. These options have controlled HTTP coverage; the modified
configuration has not been used for a live acceptance test.

## Verification

Controlled tests cover HTTP errors/redaction, non-JSON/oversized/incomplete error
bodies, truncated/empty/malformed successful HTTP responses, rubric failures,
request controls, CLI exit/status reporting and invalid worker output. They check
that all original run files and previous Judge artifacts remain byte-identical
through error and success paths. Final real-sample acceptance: **NOT RUN by Codex;
owner retest pending**.
