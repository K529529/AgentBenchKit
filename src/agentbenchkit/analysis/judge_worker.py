"""Private HTTP worker; credentials arrive over stdin and are never logged."""

import json
import sys

from agentbenchkit.analysis.judge import http_judge

if __name__ == "__main__":
    try:
        result = http_judge(**json.loads(sys.stdin.buffer.read()))
        sys.stdout.write(json.dumps(result))
    except Exception:
        sys.exit(1)
