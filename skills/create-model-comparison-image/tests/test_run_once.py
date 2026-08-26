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


SCRIPT = Path(__file__).resolve().parents[1] / "scripts" / "run_once.py"


def load_runner():
    spec = importlib.util.spec_from_file_location("model_comparison_run_once", SCRIPT)
    if spec is None or spec.loader is None:
        raise RuntimeError(f"Could not load {SCRIPT}")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


class PiRunnerTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.runner = load_runner()

    def args(self, root: Path, **overrides):
        values = {
            "model": "openai/gpt-5.6-luna",
            "label": "GPT-5.6 Luna",
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
            self.runner.gateway_model_id("deepseek/deepseek-v4-flash"),
            "deepseek/deepseek-v4-flash",
        )
        self.assertEqual(
            self.runner.gateway_model_id("merge-gateway/openai/gpt-5.6-luna"),
            "openai/gpt-5.6-luna",
        )

    def test_isolated_config_uses_env_reference_instead_of_secret(self) -> None:
        config = self.runner.pi_config(
            model="xai/grok-4.6",
            label="Grok 4.6",
            base_url="https://gateway.example/v1/openai",
        )
        provider = config["providers"]["merge-gateway"]

        self.assertEqual(provider["apiKey"], "$MERGE_GATEWAY_API_KEY")
        self.assertEqual(provider["models"][0]["id"], "xai/grok-4.6")
        self.assertEqual(provider["baseUrl"], "https://gateway.example/v1/openai")

    def test_isolated_config_uses_bounded_output_budget(self) -> None:
        config = self.runner.pi_config(
            model="zai/glm-5.3",
            label="GLM-5.3",
            base_url="https://gateway.example/v1/openai",
        )
        model = config["providers"]["merge-gateway"]["models"][0]

        self.assertEqual(model["maxTokens"], 16384)
        self.assertLessEqual(model["maxTokens"], 131072)

    def test_isolated_config_preserves_gateway_provider_options(self) -> None:
        sampling_params = {
            "provider_options": {"qwen": {"thinking": {"type": "disabled"}}}
        }
        config = self.runner.pi_config(
            model="qwen/qwen3.8-max",
            label="Qwen3.8 Max",
            base_url="https://gateway.example/v1/openai",
            sampling_params=sampling_params,
        )
        model = config["providers"]["merge-gateway"]["models"][0]

        self.assertEqual(model["samplingParams"], sampling_params)

    def test_sampling_params_must_be_a_json_object(self) -> None:
        self.assertEqual(
            self.runner.parse_sampling_params('{"temperature": 0.2}'),
            {"temperature": 0.2},
        )
        with self.assertRaisesRegex(ValueError, "must decode to a JSON object"):
            self.runner.parse_sampling_params("[]")

    def test_command_is_one_fresh_pi_run_with_one_prompt(self) -> None:
        command = self.runner.build_command(
            pi_bin="pi",
            model="deepseek/deepseek-v4-flash",
            prompt="ONE SHARED PROMPT",
        )

        self.assertEqual(command[0], "pi")
        self.assertIn("--print", command)
        self.assertIn("--no-session", command)
        self.assertIn("--no-context-files", command)
        self.assertIn("--no-skills", command)
        self.assertIn("--no-extensions", command)
        self.assertEqual(command[command.index("--provider") + 1], "merge-gateway")
        self.assertEqual(
            command[command.index("--model") + 1],
            "deepseek/deepseek-v4-flash",
        )
        self.assertEqual(command.count("ONE SHARED PROMPT"), 1)
        self.assertNotIn("--continue", command)
        self.assertNotIn("--resume", command)
        self.assertNotIn("--fork", command)

    def test_exact_prompt_does_not_append_the_default_build_contract(self) -> None:
        brief = "Build a Three.js kart demo with normal coding tools."

        self.assertEqual(
            self.runner.effective_prompt(brief, exact=True),
            brief,
        )
        self.assertIn(
            self.runner.FINAL_INSTRUCTION.strip(),
            self.runner.effective_prompt(brief),
        )

    def test_missing_gateway_key_fails_before_pi_runs(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            root.joinpath("brief.txt").write_text(
                "Build a racing site.", encoding="utf-8"
            )
            args = self.args(root)
            with (
                mock.patch.dict(os.environ, {}, clear=True),
                mock.patch.object(self.runner.subprocess, "run") as invoke,
                mock.patch.object(self.runner.shutil, "which", return_value="/bin/pi"),
            ):
                returncode = self.runner.run_model(args)

            result = json.loads(
                (args.workspace / "run-result.json").read_text(encoding="utf-8")
            )

        self.assertEqual(returncode, 1)
        self.assertEqual(result["error"], "MERGE_GATEWAY_API_KEY is not set")
        invoke.assert_not_called()

    def test_failed_run_is_not_retried_or_repaired(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            root.joinpath("brief.txt").write_text(
                "Build a racing site.", encoding="utf-8"
            )
            args = self.args(root)
            failed = subprocess.CompletedProcess([], 1)
            with (
                mock.patch.dict(os.environ, {"MERGE_GATEWAY_API_KEY": "test-key"}),
                mock.patch.object(self.runner.shutil, "which", return_value="/bin/pi"),
                mock.patch.object(
                    self.runner.subprocess, "run", return_value=failed
                ) as invoke,
            ):
                returncode = self.runner.run_model(args)

        self.assertEqual(returncode, 1)
        invoke.assert_called_once()

    def test_successful_run_writes_the_single_run_audit(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            workspace = root / "site-a"
            root.joinpath("brief.txt").write_text(
                "Build a racing site.", encoding="utf-8"
            )
            args = self.args(root, workspace=workspace)

            def complete_once(*_args, **kwargs):
                workspace.joinpath("index.html").write_text(
                    "<!doctype html><html><body>done</body></html>",
                    encoding="utf-8",
                )
                self.assertEqual(
                    kwargs["env"]["PI_CODING_AGENT_DIR"],
                    str(workspace.resolve() / ".pi-agent"),
                )
                self.assertIs(kwargs["stdin"], subprocess.DEVNULL)
                return subprocess.CompletedProcess([], 0)

            with (
                mock.patch.dict(os.environ, {"MERGE_GATEWAY_API_KEY": "test-key"}),
                mock.patch.object(self.runner.shutil, "which", return_value="/bin/pi"),
                mock.patch.object(
                    self.runner.subprocess, "run", side_effect=complete_once
                ) as invoke,
            ):
                returncode = self.runner.run_model(args)

            result = json.loads(
                (workspace / "run-result.json").read_text(encoding="utf-8")
            )
            config = json.loads(
                (workspace / ".pi-agent" / "models.json").read_text(encoding="utf-8")
            )

        self.assertEqual(returncode, 0)
        invoke.assert_called_once()
        self.assertEqual(result["prompt_count"], 1)
        self.assertEqual(result["pi_run_count"], 1)
        self.assertEqual(result["retry_count"], 0)
        self.assertEqual(result["repair_count"], 0)
        self.assertTrue(result["fresh_session"])
        self.assertEqual(
            config["providers"]["merge-gateway"]["apiKey"],
            "$MERGE_GATEWAY_API_KEY",
        )


if __name__ == "__main__":
    unittest.main()
