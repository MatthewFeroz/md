from __future__ import annotations

import importlib.util
import json
import os
import subprocess
import tempfile
import types
import unittest
from pathlib import Path
from unittest import mock


SCRIPT = Path(__file__).resolve().parents[1] / "scripts" / "run_showcase.py"


def load_runner():
    spec = importlib.util.spec_from_file_location("model_showcase_runner", SCRIPT)
    if spec is None or spec.loader is None:
        raise RuntimeError(f"Could not load {SCRIPT}")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


class PiRunnerTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.runner = load_runner()

    def start_args(self, root: Path, **overrides):
        values = {
            "model": "zai/glm-5.3-flash",
            "label": "GLM-5.3 Flash",
            "workspace": root / "site-a",
            "prompt_file": root / "brief.txt",
            "timeout_seconds": 30,
            "pi_bin": "pi",
            "exact_prompt": False,
            "base_url": None,
            "sampling_params_json": None,
        }
        values.update(overrides)
        return types.SimpleNamespace(**values)

    def test_gateway_slug_maps_to_pi_model_id(self) -> None:
        self.assertEqual(
            self.runner.gateway_model_id("merge-gateway/zai/glm-5.3-flash"),
            "zai/glm-5.3-flash",
        )

    def test_config_references_key_and_preserves_provider_options(self) -> None:
        sampling = {"provider_options": {"qwen": {"thinking": {"type": "disabled"}}}}
        config = self.runner.pi_config(
            model="qwen/qwen3.8-max",
            label="Qwen3.8 Max",
            base_url="https://gateway.example/v1/openai",
            sampling_params=sampling,
        )
        provider = config["providers"]["merge-gateway"]
        self.assertEqual(provider["apiKey"], "$MERGE_GATEWAY_API_KEY")
        self.assertEqual(provider["models"][0]["samplingParams"], sampling)
        self.assertEqual(provider["models"][0]["maxTokens"], 16384)

    def test_start_command_creates_a_named_session(self) -> None:
        command = self.runner.build_command(
            pi_bin="pi",
            model="zai/glm-5.3-flash",
            prompt="BUILD",
            session_dir=Path("sessions"),
            session_id="session-123",
        )
        self.assertIn("--session-dir", command)
        self.assertIn("--session-id", command)
        self.assertNotIn("--no-session", command)
        self.assertEqual(command[-1], "BUILD")

    def test_precheck_is_ephemeral_and_requires_a_write_tool(self) -> None:
        command = self.runner.build_command(
            pi_bin="pi",
            model="zai/glm-5.3-flash",
            prompt=self.runner.PRECHECK_PROMPT,
        )
        self.assertIn("--no-session", command)
        self.assertIn("write tool exactly once", self.runner.PRECHECK_PROMPT)

    def test_missing_gateway_key_fails_before_pi_runs(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            root.joinpath("brief.txt").write_text("Build a demo.", encoding="utf-8")
            args = self.start_args(root)
            with (
                mock.patch.dict(os.environ, {}, clear=True),
                mock.patch.object(self.runner.shutil, "which", return_value="/bin/pi"),
                mock.patch.object(self.runner.subprocess, "run") as invoke,
            ):
                returncode = self.runner.start(args)
            result = json.loads((args.workspace / "run-result.json").read_text())
        self.assertEqual(returncode, 1)
        self.assertEqual(result["error"], "MERGE_GATEWAY_API_KEY is not set")
        invoke.assert_not_called()

    def test_initial_and_repairs_share_one_session_and_archive_versions(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            prompt = root / "brief.txt"
            prompt.write_text("Build a Three.js kart demo.", encoding="utf-8")
            workspace = root / "site-a"
            start_args = self.start_args(root, workspace=workspace)
            commands: list[list[str]] = []

            def run_pi(command, **kwargs):
                commands.append(command)
                workspace.joinpath("index.html").write_text(
                    f"<html>version {len(commands)}</html>", encoding="utf-8"
                )
                self.assertEqual(
                    Path(kwargs["env"]["PI_CODING_AGENT_DIR"]),
                    workspace.resolve() / ".pi-agent",
                )
                self.assertIs(kwargs["stdin"], subprocess.DEVNULL)
                return subprocess.CompletedProcess(command, 0)

            with (
                mock.patch.dict(os.environ, {"MERGE_GATEWAY_API_KEY": "test-key"}),
                mock.patch.object(self.runner.shutil, "which", return_value="/bin/pi"),
                mock.patch.object(self.runner.subprocess, "run", side_effect=run_pi),
            ):
                self.assertEqual(self.runner.start(start_args), 0)
                repair_prompt = root / "repair.txt"
                repair_prompt.write_text("Keep the kart on the road.", encoding="utf-8")
                repair_args = types.SimpleNamespace(
                    workspace=workspace,
                    prompt_file=repair_prompt,
                    timeout_seconds=30,
                    pi_bin="pi",
                )
                self.assertEqual(self.runner.repair(repair_args), 0)

            state = json.loads((workspace / "showcase-state.json").read_text())
            self.assertEqual(state["repair_count"], 1)
            self.assertEqual(state["pi_run_count"], 2)
            self.assertEqual(len(state["versions"]), 2)
            self.assertTrue((workspace / "versions/00-initial/index.html").is_file())
            self.assertTrue(
                (workspace / "versions/01-model-repair/index.html").is_file()
            )
            session_ids = [
                command[command.index("--session-id") + 1] for command in commands
            ]
            self.assertEqual(len(set(session_ids)), 1)
            repair_log = json.loads((workspace / "repair-log.json").read_text())
            self.assertEqual(repair_log["repairs"][0]["actor"], "model")

    def test_fourth_model_repair_is_rejected(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            workspace = Path(temp)
            workspace.joinpath("index.html").write_text("done", encoding="utf-8")
            workspace.joinpath("repair.txt").write_text("fix", encoding="utf-8")
            workspace.joinpath("showcase-state.json").write_text(
                json.dumps({"repair_count": 3}), encoding="utf-8"
            )
            args = types.SimpleNamespace(
                workspace=workspace,
                prompt_file=workspace / "repair.txt",
                timeout_seconds=30,
                pi_bin="pi",
            )
            with self.assertRaisesRegex(SystemExit, "repair limit reached"):
                self.runner.repair(args)


if __name__ == "__main__":
    unittest.main()
