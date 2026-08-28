#!/usr/bin/env python3
"""Build and repair one model showcase through Pi and Merge Gateway."""

from __future__ import annotations

import argparse
import json
import os
import shutil
import subprocess
import uuid
from pathlib import Path
from typing import Any


PI_PROVIDER = "merge-gateway"
DEFAULT_GATEWAY_BASE_URL = "https://api-gateway.merge.dev/v1/openai"
MAX_MODEL_REPAIRS = 3
BUILD_INSTRUCTION = """Execution requirements:
- Build the complete browser demo now in the current workspace and write it to index.html.
- Use your normal coding tools and workflow. Do not ask questions.
- Keep the scope tight, test the result, fix issues you find, and finish the demo.
"""
REPAIR_INSTRUCTION = """Repair requirements:
- Inspect the current index.html and fix only the listed publishability problems.
- Keep the requested technology, visual concept, and working parts intact.
- Test the repaired demo, write the finished result to index.html, and do not ask questions.
"""
PRECHECK_PROMPT = """Use your write tool exactly once to create gateway-tool-precheck.txt in the
current workspace with the exact contents READY, then stop. Do not answer without using the tool.
"""


def gateway_model_id(model: str) -> str:
    model = model.strip()
    prefix = f"{PI_PROVIDER}/"
    if model.startswith(prefix):
        model = model[len(prefix) :]
    if "/" not in model or model.startswith("/") or model.endswith("/"):
        raise ValueError(f"Expected a Merge Gateway provider/model slug, got {model!r}")
    return model


def effective_prompt(brief: str, *, exact: bool = False, repair: bool = False) -> str:
    brief = brief.strip()
    if exact:
        return brief
    instruction = REPAIR_INSTRUCTION if repair else BUILD_INSTRUCTION
    return f"{brief}\n\n{instruction.strip()}"


def parse_sampling_params(raw: str | None) -> dict[str, Any] | None:
    if raw is None:
        return None
    value = json.loads(raw)
    if not isinstance(value, dict):
        raise ValueError("--sampling-params-json must decode to a JSON object")
    return value


def pi_config(
    *,
    model: str,
    label: str,
    base_url: str,
    sampling_params: dict[str, Any] | None = None,
) -> dict[str, Any]:
    model_id = gateway_model_id(model)
    model_config: dict[str, Any] = {
        "id": model_id,
        "name": label,
        "reasoning": True,
        "input": ["text"],
        "contextWindow": 500000,
        "maxTokens": 16384,
    }
    if sampling_params:
        model_config["samplingParams"] = sampling_params
    return {
        "providers": {
            PI_PROVIDER: {
                "name": "Merge Gateway",
                "baseUrl": base_url,
                "api": "openai-completions",
                "apiKey": "$MERGE_GATEWAY_API_KEY",
                "compat": {"supportsReasoningEffort": False},
                "models": [model_config],
            }
        }
    }


def write_pi_config(
    config_dir: Path,
    *,
    model: str,
    label: str,
    base_url: str,
    sampling_params: dict[str, Any] | None = None,
) -> Path:
    config_dir.mkdir(parents=True, exist_ok=False)
    config_file = config_dir / "models.json"
    config_file.write_text(
        json.dumps(
            pi_config(
                model=model,
                label=label,
                base_url=base_url,
                sampling_params=sampling_params,
            ),
            indent=2,
        )
        + "\n",
        encoding="utf-8",
    )
    return config_file


def build_command(
    *,
    pi_bin: str,
    model: str,
    prompt: str,
    session_dir: Path | None = None,
    session_id: str | None = None,
) -> list[str]:
    command = [
        pi_bin,
        "--print",
        "--mode",
        "json",
        "--no-context-files",
        "--no-skills",
        "--no-prompt-templates",
        "--no-extensions",
        "--provider",
        PI_PROVIDER,
        "--model",
        gateway_model_id(model),
    ]
    if session_dir is None or session_id is None:
        command.append("--no-session")
    else:
        command.extend(["--session-dir", str(session_dir), "--session-id", session_id])
    command.append(prompt)
    return command


def write_json(path: Path, payload: dict[str, Any]) -> None:
    path.write_text(json.dumps(payload, indent=2) + "\n", encoding="utf-8")


def read_json(path: Path) -> dict[str, Any]:
    try:
        value = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as error:
        raise ValueError(f"Could not read {path}: {error}") from error
    if not isinstance(value, dict):
        raise ValueError(f"Expected a JSON object in {path}")
    return value


def require_runtime(pi_bin: str) -> str | None:
    if shutil.which(pi_bin) is None:
        return f"Pi executable not found: {pi_bin}"
    if not os.environ.get("MERGE_GATEWAY_API_KEY"):
        return "MERGE_GATEWAY_API_KEY is not set"
    return None


def invoke_pi(
    *,
    workspace: Path,
    config_dir: Path,
    command: list[str],
    timeout_seconds: int,
    log_stem: str,
) -> tuple[int, str | None]:
    env = os.environ.copy()
    env["PI_CODING_AGENT_DIR"] = str(config_dir)
    try:
        with (
            (workspace / f"{log_stem}-events.jsonl").open(
                "w", encoding="utf-8"
            ) as stdout,
            (workspace / f"{log_stem}-stderr.log").open(
                "w", encoding="utf-8"
            ) as stderr,
        ):
            completed = subprocess.run(
                command,
                cwd=workspace,
                env=env,
                stdin=subprocess.DEVNULL,
                stdout=stdout,
                stderr=stderr,
                text=True,
                timeout=timeout_seconds,
                check=False,
            )
    except subprocess.TimeoutExpired:
        return 1, f"Pi exceeded {timeout_seconds} seconds"
    if completed.returncode != 0:
        return 1, f"Pi exited with status {completed.returncode}"
    return 0, None


def archive_version(
    workspace: Path,
    *,
    number: int,
    kind: str,
    prompt: str,
) -> dict[str, Any]:
    source = workspace / "index.html"
    if not source.is_file():
        raise ValueError("Pi exited successfully without creating index.html")
    version_dir = workspace / "versions" / f"{number:02d}-{kind}"
    version_dir.mkdir(parents=True, exist_ok=False)
    shutil.copy2(source, version_dir / "index.html")
    (version_dir / "prompt.txt").write_text(prompt + "\n", encoding="utf-8")
    return {
        "number": number,
        "kind": kind,
        "index_html": str((version_dir / "index.html").relative_to(workspace)),
        "prompt": str((version_dir / "prompt.txt").relative_to(workspace)),
    }


def state_paths(workspace: Path) -> tuple[Path, Path]:
    return workspace / "showcase-state.json", workspace / "run-result.json"


def save_state(workspace: Path, state: dict[str, Any]) -> None:
    for path in state_paths(workspace):
        write_json(path, state)


def append_repair_log(workspace: Path, entry: dict[str, Any]) -> None:
    path = workspace / "repair-log.json"
    payload: dict[str, Any] = {"repairs": []}
    if path.exists():
        payload = read_json(path)
    repairs = payload.setdefault("repairs", [])
    if not isinstance(repairs, list):
        raise ValueError(f"Expected repairs to be a list in {path}")
    repairs.append(entry)
    write_json(path, payload)


def start(args: argparse.Namespace) -> int:
    prompt_file = args.prompt_file.expanduser().resolve()
    workspace = args.workspace.expanduser().resolve()
    workspace.mkdir(parents=True, exist_ok=True)
    state: dict[str, Any] = {
        "model": args.model,
        "label": args.label,
        "pi_provider": PI_PROVIDER,
        "pi_model": gateway_model_id(args.model),
        "session_id": str(uuid.uuid4()),
        "fresh_session": True,
        "prompt_count": 1,
        "pi_run_count": 0,
        "repair_count": 0,
        "max_model_repairs": MAX_MODEL_REPAIRS,
        "status": "failed",
        "error": None,
        "versions": [],
    }
    if not prompt_file.is_file():
        state["error"] = f"Prompt file does not exist: {prompt_file}"
        save_state(workspace, state)
        return 1
    if (workspace / "index.html").exists() or (workspace / ".pi-agent").exists():
        state["error"] = "Refusing to reuse a started showcase workspace"
        save_state(workspace, state)
        return 1
    if error := require_runtime(args.pi_bin):
        state["error"] = error
        save_state(workspace, state)
        return 1
    try:
        sampling_params = parse_sampling_params(args.sampling_params_json)
    except (json.JSONDecodeError, ValueError) as error:
        state["error"] = f"Invalid sampling parameters: {error}"
        save_state(workspace, state)
        return 1

    prompt = effective_prompt(
        prompt_file.read_text(encoding="utf-8"), exact=args.exact_prompt
    )
    base_url = (
        args.base_url
        or os.environ.get("MERGE_GATEWAY_BASE_URL")
        or DEFAULT_GATEWAY_BASE_URL
    )
    config_dir = workspace / ".pi-agent"
    write_pi_config(
        config_dir,
        model=args.model,
        label=args.label,
        base_url=base_url,
        sampling_params=sampling_params,
    )
    session_dir = workspace / ".pi-sessions"
    command = build_command(
        pi_bin=args.pi_bin,
        model=args.model,
        prompt=prompt,
        session_dir=session_dir,
        session_id=state["session_id"],
    )
    state["pi_run_count"] = 1
    returncode, error = invoke_pi(
        workspace=workspace,
        config_dir=config_dir,
        command=command,
        timeout_seconds=args.timeout_seconds,
        log_stem="pi-00-initial",
    )
    if error:
        state["error"] = error
        save_state(workspace, state)
        return returncode
    try:
        state["versions"].append(
            archive_version(workspace, number=0, kind="initial", prompt=prompt)
        )
    except ValueError as error:
        state["error"] = str(error)
        save_state(workspace, state)
        return 1
    state["status"] = "complete"
    save_state(workspace, state)
    return 0


def repair(args: argparse.Namespace) -> int:
    workspace = args.workspace.expanduser().resolve()
    prompt_file = args.prompt_file.expanduser().resolve()
    state_file, _ = state_paths(workspace)
    try:
        state = read_json(state_file)
    except ValueError as error:
        raise SystemExit(str(error)) from None
    if not prompt_file.is_file():
        raise SystemExit(f"Prompt file does not exist: {prompt_file}")
    repair_count = int(state.get("repair_count", 0))
    if repair_count >= MAX_MODEL_REPAIRS:
        raise SystemExit(
            f"Model repair limit reached ({MAX_MODEL_REPAIRS}); use a logged local fix"
        )
    if not (workspace / "index.html").is_file():
        raise SystemExit("Showcase workspace has no index.html to repair")
    pi_bin = args.pi_bin
    if error := require_runtime(pi_bin):
        raise SystemExit(error)

    prompt = effective_prompt(prompt_file.read_text(encoding="utf-8"), repair=True)
    next_number = repair_count + 1
    command = build_command(
        pi_bin=pi_bin,
        model=str(state["model"]),
        prompt=prompt,
        session_dir=workspace / ".pi-sessions",
        session_id=str(state["session_id"]),
    )
    state["prompt_count"] = int(state.get("prompt_count", 1)) + 1
    state["pi_run_count"] = int(state.get("pi_run_count", 1)) + 1
    state["repair_count"] = next_number
    state["status"] = "failed"
    state["error"] = None
    returncode, error = invoke_pi(
        workspace=workspace,
        config_dir=workspace / ".pi-agent",
        command=command,
        timeout_seconds=args.timeout_seconds,
        log_stem=f"pi-{next_number:02d}-repair",
    )
    if error:
        state["error"] = error
        save_state(workspace, state)
        return returncode
    try:
        version = archive_version(
            workspace,
            number=next_number,
            kind="model-repair",
            prompt=prompt,
        )
        state.setdefault("versions", []).append(version)
        append_repair_log(
            workspace,
            {
                "actor": "model",
                "number": next_number,
                "prompt": version["prompt"],
                "result": version["index_html"],
            },
        )
    except ValueError as error:
        state["error"] = str(error)
        save_state(workspace, state)
        return 1
    state["status"] = "complete"
    save_state(workspace, state)
    return 0


def precheck(args: argparse.Namespace) -> int:
    workspace = args.workspace.expanduser().resolve()
    workspace.mkdir(parents=True, exist_ok=True)
    result_path = workspace / "precheck-result.json"
    result: dict[str, Any] = {
        "model": args.model,
        "tool_path_verified": False,
        "status": "failed",
        "error": None,
    }
    if any(workspace.iterdir()):
        result["error"] = "Refusing to reuse a non-empty precheck workspace"
        write_json(result_path, result)
        return 1
    if error := require_runtime(args.pi_bin):
        result["error"] = error
        write_json(result_path, result)
        return 1
    try:
        sampling_params = parse_sampling_params(args.sampling_params_json)
    except (json.JSONDecodeError, ValueError) as error:
        result["error"] = f"Invalid sampling parameters: {error}"
        write_json(result_path, result)
        return 1
    base_url = (
        args.base_url
        or os.environ.get("MERGE_GATEWAY_BASE_URL")
        or DEFAULT_GATEWAY_BASE_URL
    )
    config_dir = workspace / ".pi-agent"
    write_pi_config(
        config_dir,
        model=args.model,
        label=args.label,
        base_url=base_url,
        sampling_params=sampling_params,
    )
    command = build_command(
        pi_bin=args.pi_bin, model=args.model, prompt=PRECHECK_PROMPT
    )
    returncode, error = invoke_pi(
        workspace=workspace,
        config_dir=config_dir,
        command=command,
        timeout_seconds=args.timeout_seconds,
        log_stem="pi-precheck",
    )
    output = workspace / "gateway-tool-precheck.txt"
    verified = (
        output.is_file() and output.read_text(encoding="utf-8").strip() == "READY"
    )
    if error:
        result["error"] = error
    elif not verified:
        result["error"] = "Model completed without the required write tool result"
        returncode = 1
    else:
        result["tool_path_verified"] = True
        result["status"] = "complete"
    write_json(result_path, result)
    return returncode


def common_model_args(parser: argparse.ArgumentParser) -> None:
    parser.add_argument("--model", required=True)
    parser.add_argument("--label", required=True)
    parser.add_argument("--workspace", required=True, type=Path)
    parser.add_argument("--timeout-seconds", type=int, default=1800)
    parser.add_argument("--pi-bin", default="pi")
    parser.add_argument("--sampling-params-json")
    parser.add_argument("--base-url")


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    commands = parser.add_subparsers(dest="command", required=True)
    precheck_parser = commands.add_parser(
        "precheck", help="Verify the model's Pi tool path"
    )
    common_model_args(precheck_parser)
    precheck_parser.set_defaults(handler=precheck)

    start_parser = commands.add_parser("start", help="Start a fresh showcase session")
    common_model_args(start_parser)
    start_parser.add_argument("--prompt-file", required=True, type=Path)
    start_parser.add_argument("--exact-prompt", action="store_true")
    start_parser.set_defaults(handler=start)

    repair_parser = commands.add_parser(
        "repair", help="Repair in the existing Pi session"
    )
    repair_parser.add_argument("--workspace", required=True, type=Path)
    repair_parser.add_argument("--prompt-file", required=True, type=Path)
    repair_parser.add_argument("--timeout-seconds", type=int, default=1800)
    repair_parser.add_argument("--pi-bin", default="pi")
    repair_parser.set_defaults(handler=repair)
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    if args.timeout_seconds < 1:
        raise SystemExit("--timeout-seconds must be positive")
    return args.handler(args)


if __name__ == "__main__":
    raise SystemExit(main())
