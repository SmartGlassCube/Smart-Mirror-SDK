import json
from pathlib import Path

JSON_CONFIG_DIR = Path(__file__).resolve().parent / "json_config"
DEFAULT_GESTURE_CONFIG_FILE = JSON_CONFIG_DIR / "default_gesture_config.json"
DEFAULT_WIDGET_BINDINGS_FILE = JSON_CONFIG_DIR / "default_widget_event_bindings.json"


def load_json_config(file_path):
    try:
        with open(file_path, "r", encoding="utf-8") as stream:
            loaded = json.load(stream)
    except OSError as error:
        raise FileNotFoundError(f"Required config file not found: {file_path}") from error
    except json.JSONDecodeError as error:
        raise ValueError(f"Invalid JSON in config file: {file_path}") from error

    if not isinstance(loaded, dict):
        raise ValueError(f"Config file must contain a JSON object: {file_path}")

    return loaded
