from __future__ import annotations

import importlib.util
import json
import tempfile
import unittest
from pathlib import Path


SCRIPT = Path(__file__).resolve().parents[1] / "scripts" / "stage_provider_logos.py"


def load_stager():
    spec = importlib.util.spec_from_file_location("stage_provider_logos", SCRIPT)
    if spec is None or spec.loader is None:
        raise RuntimeError(f"Could not load {SCRIPT}")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def write_catalog(root: Path, providers: tuple[str, ...]) -> None:
    (root / "manifest.json").write_text(
        json.dumps(
            {
                "assets": [
                    {
                        "provider": provider,
                        "logo_only": f"{provider}.svg",
                        "name_and_logo": f"{provider}-wordmark.svg",
                    }
                    for provider in providers
                ]
            }
        ),
        encoding="utf-8",
    )
    for provider in providers:
        for suffix in (".svg", ".png", "-wordmark.svg", "-wordmark.png"):
            (root / f"{provider}{suffix}").write_bytes(f"{provider}{suffix}".encode())


class ProviderLogoStagerTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.stager = load_stager()

    def test_provider_is_derived_from_gateway_slug(self) -> None:
        self.assertEqual(
            self.stager.provider_from_model("merge-gateway/qwen/qwen3.7-max"),
            "qwen",
        )
        self.assertEqual(
            self.stager.provider_from_model("deepseek/deepseek-v4-flash"),
            "deepseek",
        )

    def test_stages_each_requested_provider_symbol(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            assets = root / "assets"
            output = root / "run"
            assets.mkdir()
            write_catalog(assets, ("qwen", "deepseek"))

            result = self.stager.stage_logos(
                folder=output,
                models={
                    "a": "merge-gateway/qwen/qwen3.7-max",
                    "b": "deepseek/deepseek-v4-flash",
                },
                asset_dir=assets,
            )

            self.assertEqual((output / "logo-a.svg").read_bytes(), b"qwen.svg")
            self.assertEqual((output / "logo-b.svg").read_bytes(), b"deepseek.svg")
            self.assertEqual(result["a"]["provider"], "qwen")
            self.assertEqual(result["b"]["provider"], "deepseek")

    def test_unknown_provider_fails_without_staging_any_logo(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            assets = root / "assets"
            output = root / "run"
            assets.mkdir()
            write_catalog(assets, ("qwen",))

            with self.assertRaisesRegex(ValueError, "No bundled logo"):
                self.stager.stage_logos(
                    folder=output,
                    models={"a": "future/new-model"},
                    asset_dir=assets,
                )

            self.assertFalse(output.exists())

    def test_incomplete_catalog_fails_before_copying(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            assets = root / "assets"
            output = root / "run"
            assets.mkdir()
            write_catalog(assets, ("qwen",))
            (assets / "qwen-wordmark.png").unlink()

            with self.assertRaisesRegex(ValueError, "catalog is incomplete"):
                self.stager.stage_logos(
                    folder=output,
                    models={"a": "qwen/qwen3.7-max"},
                    asset_dir=assets,
                )

            self.assertFalse(output.exists())

    def test_existing_target_is_not_overwritten(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            assets = root / "assets"
            output = root / "run"
            assets.mkdir()
            output.mkdir()
            write_catalog(assets, ("qwen",))
            target = output / "logo-a.svg"
            target.write_bytes(b"custom")

            with self.assertRaises(FileExistsError):
                self.stager.stage_logos(
                    folder=output,
                    models={"a": "qwen/qwen3.7-max"},
                    asset_dir=assets,
                )

            self.assertEqual(target.read_bytes(), b"custom")


if __name__ == "__main__":
    unittest.main()
