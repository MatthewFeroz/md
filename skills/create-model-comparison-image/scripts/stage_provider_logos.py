#!/usr/bin/env python3
"""Stage canonical provider symbols for a model-comparison run."""

from __future__ import annotations

import argparse
import json
import re
import shutil
from pathlib import Path
from typing import Any


ASSET_DIR = Path(__file__).resolve().parents[1] / "assets" / "provider-logos"
REQUIRED_SUFFIXES = (".svg", ".png", "-wordmark.svg", "-wordmark.png")
PROVIDER_PATTERN = re.compile(r"^[a-z0-9][a-z0-9-]*$")


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Copy bundled provider symbols to logo-a.svg and/or logo-b.svg."
    )
    parser.add_argument("--folder", required=True, type=Path)
    parser.add_argument("--model-a")
    parser.add_argument("--model-b")
    parser.add_argument("--asset-dir", type=Path, default=ASSET_DIR, help=argparse.SUPPRESS)
    args = parser.parse_args()
    if not args.model_a and not args.model_b:
        parser.error("at least one of --model-a or --model-b is required")
    return args


def provider_from_model(model: str) -> str:
    value = model.strip()
    prefix = "merge-gateway/"
    if value.startswith(prefix):
        value = value[len(prefix) :]
    parts = value.split("/", 1)
    if len(parts) != 2 or not parts[1] or not PROVIDER_PATTERN.fullmatch(parts[0]):
        raise ValueError(
            "Expected <provider>/<model> or merge-gateway/<provider>/<model>; "
            f"got {model!r}"
        )
    return parts[0]


def load_catalog(asset_dir: Path) -> dict[str, dict[str, Any]]:
    manifest_path = asset_dir / "manifest.json"
    try:
        manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as error:
        raise ValueError(f"Could not load provider manifest {manifest_path}: {error}") from error

    entries = manifest.get("assets")
    if not isinstance(entries, list) or not entries:
        raise ValueError(f"Provider manifest has no assets: {manifest_path}")

    catalog: dict[str, dict[str, Any]] = {}
    for entry in entries:
        if not isinstance(entry, dict):
            raise ValueError(f"Invalid provider entry in {manifest_path}")
        provider = entry.get("provider")
        if not isinstance(provider, str) or not PROVIDER_PATTERN.fullmatch(provider):
            raise ValueError(f"Invalid provider name in {manifest_path}: {provider!r}")
        if provider in catalog:
            raise ValueError(f"Duplicate provider in {manifest_path}: {provider}")
        expected_paths = {
            "logo_only": f"{provider}.svg",
            "name_and_logo": f"{provider}-wordmark.svg",
        }
        for key, expected in expected_paths.items():
            if entry.get(key) != expected:
                raise ValueError(
                    f"Invalid {key} path for {provider!r} in {manifest_path}; "
                    f"expected {expected!r}"
                )
        catalog[provider] = entry

    missing = [
        asset_dir / f"{provider}{suffix}"
        for provider in catalog
        for suffix in REQUIRED_SUFFIXES
        if not (asset_dir / f"{provider}{suffix}").is_file()
    ]
    if missing:
        names = ", ".join(path.name for path in missing)
        raise ValueError(f"Provider catalog is incomplete; missing: {names}")
    return catalog


def stage_logos(
    *,
    folder: Path,
    models: dict[str, str],
    asset_dir: Path = ASSET_DIR,
) -> dict[str, dict[str, str]]:
    catalog = load_catalog(asset_dir)
    resolved: dict[str, tuple[str, str, Path, Path]] = {}
    for side, model in models.items():
        if side not in {"a", "b"}:
            raise ValueError(f"Invalid comparison side: {side!r}")
        provider = provider_from_model(model)
        if provider not in catalog:
            raise ValueError(
                f"No bundled logo for provider {provider!r}; add it to "
                f"{asset_dir} and manifest.json or supply a custom symbol"
            )
        source = asset_dir / f"{provider}.svg"
        target = folder / f"logo-{side}.svg"
        if target.exists():
            raise FileExistsError(f"Refusing to overwrite existing logo: {target}")
        resolved[side] = (model, provider, source, target)

    folder.mkdir(parents=True, exist_ok=True)
    result: dict[str, dict[str, str]] = {}
    for side, (model, provider, source, target) in resolved.items():
        shutil.copy2(source, target)
        result[side] = {
            "model": model,
            "provider": provider,
            "source": str(source),
            "target": str(target),
        }
    return result


def main() -> int:
    args = parse_args()
    models = {
        side: model
        for side, model in (("a", args.model_a), ("b", args.model_b))
        if model
    }
    try:
        result = stage_logos(
            folder=args.folder.expanduser().resolve(),
            models=models,
            asset_dir=args.asset_dir.expanduser().resolve(),
        )
    except (FileExistsError, ValueError) as error:
        raise SystemExit(str(error)) from None
    print(json.dumps(result, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
