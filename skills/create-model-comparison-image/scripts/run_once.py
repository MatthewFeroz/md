#!/usr/bin/env python3
"""Give one website brief to one model through Pi and Merge Gateway."""

from __future__ import annotations

import argparse
import json
import os
import shutil
import subprocess
from pathlib import Path
from typing import Any


PI_PROVIDER = "merge-gateway"
DEFAULT_GATEWAY_BASE_URL = "https://api-gateway.merge.dev/v1/openai"
FINAL_INSTRUCTION = """Execution contract:
- Build the complete website now and write it to index.html in the current workspace.
- Make index.html self-contained with inline CSS and JavaScript and no network requests.
- Do not ask questions or create plans, progress notes, screenshots, or extra files.
- Do not inspect, test, revise, repair, or refine the result after writing index.html.
- Stop immediately once index.html exists.
"""


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Run one fresh Pi job with one prompt and no harness loop."
    )
    parser.add_argument(
        "--model",
        required=True,
        help=(
            "Merge Gateway slug such as openai/gpt-5.6-luna. The optional "
            "merge-gateway/ prefix is accepted."
        ),
    )
    parser.add_argument("--label", required=True)
    parser.add_argument("--workspace", required=True, type=Path)
    parser.add_argument("--prompt-file", required=True, type=Path)
    parser.add_argument("--timeout-seconds", type=int, default=1800)
    parser.add_argument("--pi-bin", default="pi")
    parser.add_argument(
        "--sampling-params-json",
        default=None,
        help=(
            "Optional JSON object merged into Pi's model request. Use this for "
            "Gateway provider_options that must reach the selected vendor."
        ),
    )
    parser.add_argument(
        "--base-url",
        default=None,
        help=(
            "Merge Gateway OpenAI-compatible base URL. Defaults to "
            "MERGE_GATEWAY_BASE_URL or the production Gateway URL."
        ),
    )
    return parser.parse_args()


def gateway_model_id(model: str) -> str:
    model = model.strip()
    prefix = f"{PI_PROVIDER}/"
    if model.startswith(prefix):
        model = model[len(prefix) :]
    if "/" not in model or model.startswith("/") or model.endswith("/"):
        raise ValueError(f"Expected a Merge Gateway provider/model slug, got {model!r}")
    return model


def effective_prompt(brief: str) -> str:
    return f"{brief.strip()}\n\n{FINAL_INSTRUCTION.strip()}"


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


def build_command(*, pi_bin: str, model: str, prompt: str) -> list[str]:
    return [
        pi_bin,
        "--print",
        "--mode",
        "json",
        "--no-session",
        "--no-context-files",
        "--no-skills",
        "--no-prompt-templates",
        "--no-extensions",
        "--provider",
        PI_PROVIDER,
        "--model",
        gateway_model_id(model),
        prompt,
    ]


def write_result(path: Path, payload: dict[str, Any]) -> None:
    path.write_text(json.dumps(payload, indent=2) + "\n", encoding="utf-8")


def run_model(args: argparse.Namespace) -> int:
    prompt_file = args.prompt_file.expanduser().resolve()
    workspace = args.workspace.expanduser().resolve()
    result_file = workspace / "run-result.json"
    model_id = gateway_model_id(args.model)
    result: dict[str, Any] = {
        "model": args.model,
        "pi_provider": PI_PROVIDER,
        "pi_model": model_id,
        "prompt_count": 1,
        "pi_run_count": 0,
        "fresh_session": True,
        "retry_count": 0,
        "repair_count": 0,
        "status": "failed",
        "error": None,
    }

    workspace.mkdir(parents=True, exist_ok=True)
    if not prompt_file.is_file():
        result["error"] = f"Prompt file does not exist: {prompt_file}"
        write_result(result_file, result)
        return 1
    if (workspace / "index.html").exists():
        result["error"] = "Refusing to reuse a workspace that already has index.html"
        write_result(result_file, result)
        return 1
    if shutil.which(args.pi_bin) is None:
        result["error"] = f"Pi executable not found: {args.pi_bin}"
        write_result(result_file, result)
        return 1
    if not os.environ.get("MERGE_GATEWAY_API_KEY"):
        result["error"] = "MERGE_GATEWAY_API_KEY is not set"
        write_result(result_file, result)
        return 1

    try:
        sampling_params = parse_sampling_params(args.sampling_params_json)
    except (json.JSONDecodeError, ValueError) as error:
        result["error"] = f"Invalid sampling parameters: {error}"
        write_result(result_file, result)
        return 1

    config_dir = workspace / ".pi-agent"
    if config_dir.exists():
        result["error"] = f"Refusing to reuse Pi config directory: {config_dir}"
        write_result(result_file, result)
        return 1

    prompt = effective_prompt(prompt_file.read_text(encoding="utf-8"))
    (workspace / "effective-prompt.txt").write_text(prompt + "\n", encoding="utf-8")
    base_url = (
        args.base_url
        or os.environ.get("MERGE_GATEWAY_BASE_URL")
        or DEFAULT_GATEWAY_BASE_URL
    )
    write_pi_config(
        config_dir,
        model=args.model,
        label=args.label,
        base_url=base_url,
        sampling_params=sampling_params,
    )
    command = build_command(pi_bin=args.pi_bin, model=args.model, prompt=prompt)
    env = os.environ.copy()
    env["PI_CODING_AGENT_DIR"] = str(config_dir)

    result["pi_run_count"] = 1
    try:
        with (
            (workspace / "pi-events.jsonl").open("w", encoding="utf-8") as stdout,
            (workspace / "pi-stderr.log").open("w", encoding="utf-8") as stderr,
        ):
            completed = subprocess.run(
                command,
                cwd=workspace,
                env=env,
                stdin=subprocess.DEVNULL,
                stdout=stdout,
                stderr=stderr,
                text=True,
                timeout=args.timeout_seconds,
                check=False,
            )
    except subprocess.TimeoutExpired:
        result["error"] = f"Pi exceeded {args.timeout_seconds} seconds"
        write_result(result_file, result)
        return 1

    if completed.returncode != 0:
        result["error"] = f"Pi exited with status {completed.returncode}"
        write_result(result_file, result)
        return 1
    if not (workspace / "index.html").is_file():
        result["error"] = "Pi exited successfully without creating index.html"
        write_result(result_file, result)
        return 1

    result["status"] = "complete"
    write_result(result_file, result)
    return 0


def main() -> int:
    args = parse_args()
    if args.timeout_seconds < 1:
        raise SystemExit("--timeout-seconds must be positive")
    return run_model(args)


if __name__ == "__main__":
    raise SystemExit(main())
