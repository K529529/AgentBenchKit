"""Small TOML serializer for validated native adapter output, never raw credentials."""

import json
from typing import Any


def toml_config(sections: dict[str, Any]) -> str:
    lines = []

    def emit(values: dict[str, Any], prefix: str = "") -> None:
        for key, value in values.items():
            if not isinstance(value, dict) and value is not None:
                lines.append(f"{key} = {json.dumps(value, ensure_ascii=False)}")
        for key, value in values.items():
            if isinstance(value, dict):
                name = f"{prefix}.{key}" if prefix else key
                lines.extend(["", f"[{name}]"])
                emit(value, name)

    emit(sections)
    return "\n".join(lines) + "\n"
