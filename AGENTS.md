# AgentBenchKit

The frozen V0 contract is `docs/architecture-v0.3.1.md`.
Work on `feature/v0-implementation`. The user authorized a tested, coherent commit
and push after each completed phase. Never force-push or rewrite pushed history.

Keep evaluated agents external and unchanged. Use public CLI/SDK interfaces.
Keep execution, candidate correctness, analysis and cleanup separate.
Preserve all physical executions and immutable, redacted evidence.
Do not add infrastructure or abstractions without a concrete V0 need.

Run `uv run pytest`, `uv run ruff check .`, `uv run mypy`, and relevant real
integration checks. Record PASS / FAIL / NOT RUN honestly in
`docs/implementation-status.md`; fake-agent tests are not real-agent acceptance.
Do not commit credentials, local runtime artifacts, or IDE settings.
