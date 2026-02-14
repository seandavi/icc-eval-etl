import json
from pathlib import Path
from typing import Any

from pydantic import BaseModel


class JSONLWriter:
    def __init__(self, output_dir: Path, extra_fields: dict[str, Any] | None = None):
        self.output_dir = output_dir
        self.extra_fields = extra_fields or {}
        self.output_dir.mkdir(parents=True, exist_ok=True)

    def write(self, filename: str, records: list[BaseModel]) -> Path:
        path = self.output_dir / filename
        with open(path, "w") as f:
            for record in records:
                data = record.model_dump(mode="json")
                data.update(self.extra_fields)
                f.write(json.dumps(data) + "\n")
        return path
