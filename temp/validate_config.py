"""Validate gauges.conf.json at startup using JSON Schema."""
import json, sys, pathlib
from jsonschema import validate, ValidationError

SCHEMA_PATH = pathlib.Path(__file__).with_name("gauges.schema.json")

def validate_config(config_path: str) -> None:
    schema = json.loads(SCHEMA_PATH.read_text())
    data = json.loads(pathlib.Path(config_path).read_text())
    try:
        validate(instance=data, schema=schema)
    except ValidationError as e:
        print(f"[config] Invalid gauges config: {e.message}")
        sys.exit(2)
