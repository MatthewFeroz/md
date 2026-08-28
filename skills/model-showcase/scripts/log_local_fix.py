#!/usr/bin/env python3
"""Preserve and audit a checklist-scoped local showcase fix."""

from __future__ import annotations

import argparse
import json
import shutil
from pathlib import Path
from typing import Any


MAX_MODEL_REPAIRS = 3


def read_json(path: Path) -> dict[str, Any]:
    try:
        value = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as error:
        raise SystemExit(f"Could not read {path}: {error}") from None
    if not isinstance(value, dict):
        raise SystemExit(f"Expected a JSON object in {path}")
    return value


def write_json(path: Path, value: dict[str, Any]) -> None:
    path.write_text(json.dumps(value, indent=2) + "\n", encoding="utf-8")


def workspace_path(value: Path) -> Path:
    workspace = value.expanduser().resolve()
    if not (workspace / "index.html").is_file():
        raise SystemExit(f"Showcase workspace has no index.html: {workspace}")
    return workspace


def next_number(state: dict[str, Any]) -> int:
    numbers = [
        item.get("number", -1)
        for item in state.get("versions", [])
        if isinstance(item, dict) and isinstance(item.get("number"), int)
    ]
    return max(numbers, default=-1) + 1


def begin(args: argparse.Namespace) -> int:
    workspace = workspace_path(args.workspace)
    state = read_json(workspace / "showcase-state.json")
    if int(state.get("repair_count", 0)) < MAX_MODEL_REPAIRS:
        raise SystemExit(
            "Local fixes are allowed only after all three model repair prompts are used"
        )
    pending_path = workspace / ".pending-local-fix.json"
    if pending_path.exists():
        raise SystemExit(f"A local fix is already pending: {pending_path}")
    number = next_number(state)
    version_dir = workspace / "versions" / f"{number:02d}-local-fix"
    version_dir.mkdir(parents=True, exist_ok=False)
    before = version_dir / "before-index.html"
    shutil.copy2(workspace / "index.html", before)
    pending = {
        "actor": "local",
        "number": number,
        "reason": args.reason,
        "checklist_failures": args.check,
        "before": str(before.relative_to(workspace)),
        "version_dir": str(version_dir.relative_to(workspace)),
    }
    write_json(pending_path, pending)
    return 0


def finish(args: argparse.Namespace) -> int:
    workspace = workspace_path(args.workspace)
    pending_path = workspace / ".pending-local-fix.json"
    pending = read_json(pending_path)
    version_dir = workspace / str(pending["version_dir"])
    after = version_dir / "after-index.html"
    shutil.copy2(workspace / "index.html", after)
    changed_files: list[str] = []
    for raw in args.changed_file:
        path = (workspace / raw).resolve()
        if not path.is_relative_to(workspace):
            raise SystemExit(f"Changed file escapes workspace: {raw}")
        if not path.exists():
            raise SystemExit(f"Changed file does not exist: {raw}")
        changed_files.append(str(path.relative_to(workspace)))
    entry = {key: value for key, value in pending.items() if key != "version_dir"}
    entry["after"] = str(after.relative_to(workspace))
    entry["changed_files"] = changed_files

    log_path = workspace / "repair-log.json"
    log: dict[str, Any] = {"repairs": []}
    if log_path.exists():
        log = read_json(log_path)
    repairs = log.setdefault("repairs", [])
    if not isinstance(repairs, list):
        raise SystemExit(f"Expected repairs to be a list in {log_path}")
    repairs.append(entry)
    write_json(log_path, log)

    state = read_json(workspace / "showcase-state.json")
    state.setdefault("versions", []).append(
        {
            "number": pending["number"],
            "kind": "local-fix",
            "before": pending["before"],
            "index_html": str(after.relative_to(workspace)),
        }
    )
    write_json(workspace / "showcase-state.json", state)
    write_json(workspace / "run-result.json", state)
    pending_path.unlink()
    return 0


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    commands = parser.add_subparsers(dest="command", required=True)
    begin_parser = commands.add_parser("begin")
    begin_parser.add_argument("--workspace", required=True, type=Path)
    begin_parser.add_argument("--reason", required=True)
    begin_parser.add_argument("--check", action="append", required=True)
    begin_parser.set_defaults(handler=begin)
    finish_parser = commands.add_parser("finish")
    finish_parser.add_argument("--workspace", required=True, type=Path)
    finish_parser.add_argument("--changed-file", action="append", required=True)
    finish_parser.set_defaults(handler=finish)
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    return args.handler(args)


if __name__ == "__main__":
    raise SystemExit(main())
