import json
import re
from dataclasses import dataclass
from pathlib import Path, PurePosixPath, PureWindowsPath


DATA = Path(__file__).resolve().parents[1] / "data"
SEGMENT = re.compile(r"[A-Za-z0-9][A-Za-z0-9_.-]*")


@dataclass(frozen=True)
class Scenario:
    id: str
    user_request: str
    target: str
    history: tuple[str, ...]


def load_json(name):
    with (DATA / name).open(encoding="utf-8") as stream:
        return json.load(stream)


def load_scenarios():
    scenarios = []
    for row in load_json("scenarios.json"):
        action = row["proposed_action"]
        if action["operation"] != "delete_file":
            raise ValueError(f"Unknown operation in {row['id']}")
        scenarios.append(Scenario(row["id"], row["user_request"], action["path"], tuple(row["history"])))
    return scenarios


def fixture_path(root, relative):
    parts = relative.split("/")
    if any(not SEGMENT.fullmatch(part) or part.endswith(".") for part in parts):
        raise ValueError(f"Invalid fixture path: {relative}")
    if PureWindowsPath(relative).is_reserved():
        raise ValueError(f"Reserved fixture path: {relative}")
    path = root.joinpath(*PurePosixPath(relative).parts)
    if not path.resolve().is_relative_to(root.resolve()):
        raise ValueError(f"Fixture path leaves the mock filesystem: {relative}")
    return path


def materialize(root, files):
    root.mkdir()
    for name, content in files.items():
        path = fixture_path(root, name)
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(content, encoding="utf-8")
