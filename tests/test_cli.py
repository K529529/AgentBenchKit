from typer.testing import CliRunner

from agentbenchkit.cli import app


def test_help() -> None:
    result = CliRunner().invoke(app, ["--help"])
    assert result.exit_code == 0
    assert "AgentBenchKit" in result.output or "version" in result.output
