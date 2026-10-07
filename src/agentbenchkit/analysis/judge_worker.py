"""Private HTTP worker; diagnostics are sanitized before crossing the process pipe."""

import json
import sys

from agentbenchkit.analysis.judge import http_judge
from agentbenchkit.analysis.judge_diagnostics import safe_error
from agentbenchkit.storage.artifacts import Redactor

if __name__ == "__main__":
    key = ""
    try:
        arguments = json.loads(sys.stdin.buffer.read())
        key = arguments.get("key", "")
        result = http_judge(**arguments)
        sys.stdout.write(json.dumps(Redactor((key,)).value(result)))
    except Exception as exc:
        sys.stdout.write(json.dumps({"error": safe_error(exc, key)}))
        sys.exit(1)
