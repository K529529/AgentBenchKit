# Phase 5: second Agent and shared model contract

PASS: external Codex 0.155.1, with its complete official Linux package, ran the same
clamp/stable_unique tasks with the same fresh verifier, without Agent source edits.

| Run | Configuration | Result |
| --- | --- | --- |
| 20261006T203835Z-bad81bb9 | Initial minimal Codex binary image | 0/2; helper missing, Agent COMPLETED but verifier FAIL; retained |
| 20261006T204304Z-993e7d4f | Complete package, ChatGPT login, gpt-6-astra low | 2/2 PASS |
| 20261006T205812Z-7ddbff60 | Shared ModelSpec, isolated CODEX_HOME, tmpfs auth, same two tasks | 2/2 PASS |
| 20261006T205831Z-a0484cfc | Shared ModelSpec, Nexus qwen3.8-flash, clamp | 1/1 PASS |

Codex subscription login is authorized smoke evidence only, not a controlled
same-provider/model comparison with Nexus. Explicit API ModelSpec translation and
unsupported-field rejection are tested; real Codex API-provider execution is NOT RUN.

ModelSpec is public and typed; CLI/runtime use common AgentSettings. Nexus native
config import is a compatibility adapter. Neither Harness modifies Agent source.
See model-contract.md for requested/effective conditions and adapter limitations.

Validation: 119 tests PASS in the combined working tree, including 7 real Docker
tests; Ruff, Windows mypy and Linux-target mypy PASS. Later analysis/viewer tests
are committed in their own phases. The known TestClient dependency deprecation
warning does not affect results and will be handled with the viewer dependencies.

Native model inputs are unavailable and model outputs partial for both adapters;
unobserved capabilities are not represented as zero. Original failed runs remain
intact. Secrets and login files are excluded from all committed artifacts.
