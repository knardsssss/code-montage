"""Helpers shared by select_news.py and newsletter_to_brief.py."""

import json
from pathlib import Path

from jsonschema import Draft202012Validator

REPO_ROOT = Path(__file__).resolve().parent.parent
SCHEMA_PATH = REPO_ROOT / "schemas" / "selected_news.schema.json"


def load_json(path):
    with open(path, encoding="utf-8") as handle:
        return json.load(handle)


def write_json(path, data):
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    with open(path, "w", encoding="utf-8") as handle:
        json.dump(data, handle, indent=2, ensure_ascii=False)
        handle.write("\n")


def validate_selected_news(document):
    """Return a list of readable problems; an empty list means the document is valid."""
    validator = Draft202012Validator(load_json(SCHEMA_PATH))
    problems = []
    for error in sorted(validator.iter_errors(document), key=lambda e: list(e.absolute_path)):
        location = "/".join(str(part) for part in error.absolute_path) or "(top level)"
        problems.append(f"{location}: {error.message}")

    # The schema cannot compare values across items.
    if isinstance(document, dict) and isinstance(document.get("items"), list):
        seen = set()
        for item in document["items"]:
            item_id = item.get("id") if isinstance(item, dict) else None
            if item_id in seen:
                problems.append(f"items: duplicate id {item_id!r}")
            seen.add(item_id)
    return problems
