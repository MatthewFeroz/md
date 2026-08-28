from __future__ import annotations

import hashlib
import importlib.util
import tempfile
import unittest
from pathlib import Path


SKILL_DIR = Path(__file__).resolve().parents[1]
SCRIPT = SKILL_DIR / "scripts" / "render_showcase.py"
ASSET_DIR = SKILL_DIR / "assets" / "merge-badge"
TEMPLATE = SKILL_DIR / "template.html"


def load_renderer():
    spec = importlib.util.spec_from_file_location("render_showcase", SCRIPT)
    if spec is None or spec.loader is None:
        raise RuntimeError(f"Could not load {SCRIPT}")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


class MergeBadgeRenderTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.renderer = load_renderer()

    def test_figma_exports_are_byte_exact(self) -> None:
        for name, expected_hash in self.renderer.MERGE_BADGE_FILES.items():
            actual_hash = hashlib.sha256((ASSET_DIR / name).read_bytes()).hexdigest()
            self.assertEqual(actual_hash, expected_hash)

    def test_stager_copies_the_locked_badge_assets(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            output = Path(temp)
            mark, wordmark = self.renderer.stage_merge_badge(SKILL_DIR, output)

            self.assertEqual(
                mark.read_bytes(), (ASSET_DIR / "merge-mark.svg").read_bytes()
            )
            self.assertEqual(
                wordmark.read_bytes(),
                (ASSET_DIR / "merge-wordmark.svg").read_bytes(),
            )

    def test_png_template_uses_exact_figma_geometry(self) -> None:
        template = TEMPLATE.read_text(encoding="utf-8")

        self.assertIn('data-node-id="3:2660"', template)
        self.assertIn("left: 770px; top: 930.5px", template)
        self.assertIn("width: 378.0297546386719px; height: 111px", template)
        self.assertIn("background: #FAF8F5", template)
        self.assertIn("border: 3px solid #D9D9D9", template)
        self.assertIn('src="merge-badge/merge-mark.svg"', template)
        self.assertIn('src="merge-badge/merge-wordmark.svg"', template)

    def test_reference_layout_keeps_visual_space_above_badge(self) -> None:
        panel_bottom = self.renderer.SHOT_Y + self.renderer.SHOT_HEIGHT
        badge_gap = self.renderer.MERGE_BADGE_Y - panel_bottom

        self.assertEqual(self.renderer.FIGMA_LAYOUT_NODE_ID, "3:2614")
        self.assertEqual(self.renderer.HEADER_HEIGHT, 187)
        self.assertEqual(self.renderer.DIVIDER_WIDTH, 2)
        self.assertEqual(self.renderer.LOGO_BOXES, {"a": 108, "b": 96})
        self.assertEqual(self.renderer.HEADER_MAX_WIDTHS, {"a": 683, "b": 801})
        self.assertEqual(self.renderer.SHOT_A_X, 52.7010498046875)
        self.assertEqual(self.renderer.SHOT_A_WIDTH, 854.5978393554688)
        self.assertEqual(self.renderer.SHOT_B_X, 1013.369140625)
        self.assertEqual(self.renderer.SHOT_B_WIDTH, 853.2615966796875)
        self.assertEqual(self.renderer.SHOT_Y, 277)
        self.assertEqual(self.renderer.SHOT_HEIGHT, 615)
        self.assertEqual(badge_gap, 38.5)
        self.assertIn("crosshair-dot", TEMPLATE.read_text(encoding="utf-8"))

    def test_website_panels_keep_the_subtle_shadow(self) -> None:
        template = TEMPLATE.read_text(encoding="utf-8")

        self.assertIn("0 12px 24px rgba(0, 0, 0, 0.12)", template)
        self.assertIn("0 2px 6px rgba(0, 0, 0, 0.08)", template)
        self.assertEqual(
            self.renderer.PANEL_SHADOW,
            {
                "primary": {
                    "dx": 0,
                    "dy": 12,
                    "std_deviation": 12,
                    "opacity": 0.12,
                },
                "contact": {
                    "dx": 0,
                    "dy": 2,
                    "std_deviation": 3,
                    "opacity": 0.08,
                },
            },
        )

        script = SCRIPT.read_text(encoding="utf-8")
        self.assertIn('id="panel-shadow"', script)
        self.assertEqual(script.count('filter="url(#panel-shadow)"'), 2)

    def test_svg_badge_is_exact_and_self_contained(self) -> None:
        svg = self.renderer.merge_badge_svg(
            ASSET_DIR / "merge-mark.svg",
            ASSET_DIR / "merge-wordmark.svg",
        )

        self.assertIn('data-figma-node-id="3:2660"', svg)
        self.assertIn('transform="translate(770.0 930.5)"', svg)
        self.assertIn('width="375.0297546386719" height="108.0"', svg)
        self.assertIn('rx="96.0" fill="#FAF8F5" stroke="#D9D9D9"', svg)
        self.assertIn('width="46.18862533569336"', svg)
        self.assertIn('width="200.4523162841797"', svg)
        self.assertEqual(svg.count("data:image/svg+xml;base64,"), 2)


if __name__ == "__main__":
    unittest.main()
