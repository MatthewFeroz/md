from __future__ import annotations

import importlib.util
import sys
import unittest
from pathlib import Path


SKILL_DIR = Path(__file__).resolve().parents[1]
SCRIPT_DIR = SKILL_DIR / "scripts"
SCRIPT = SCRIPT_DIR / "render_video.py"
def load_renderer():
    sys.path.insert(0, str(SCRIPT_DIR))
    try:
        spec = importlib.util.spec_from_file_location("render_video", SCRIPT)
        if spec is None or spec.loader is None:
            raise RuntimeError(f"Could not load {SCRIPT}")
        module = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(module)
        return module
    finally:
        sys.path.remove(str(SCRIPT_DIR))


class ComparisonVideoRenderTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.renderer = load_renderer()

    def test_video_panels_use_locked_comparison_geometry(self) -> None:
        panels = self.renderer.panel_layouts()

        self.assertEqual(
            {key: panels["a"][key] for key in ("x", "y", "width", "height")},
            {"x": 53, "y": 277, "width": 855, "height": 615},
        )
        self.assertEqual(
            {key: panels["b"][key] for key in ("x", "y", "width", "height")},
            {"x": 1013, "y": 277, "width": 853, "height": 615},
        )

    def test_default_output_uses_smooth_60_fps_motion(self) -> None:
        self.assertEqual(self.renderer.DEFAULT_FPS, 60)

    def test_panel_masks_preserve_figma_corner_radius(self) -> None:
        html = self.renderer.panel_mask_html(855, 615, 8.152)

        self.assertIn("background: transparent", html)
        self.assertIn("width: 855px; height: 615px", html)
        self.assertIn("border-radius: 8.152px", html)

    def test_publishable_video_composites_both_models_into_comparison_panels(self) -> None:
        command = self.renderer.build_ffmpeg_command(
            "ffmpeg",
            Path("comparison.png"),
            Path("qwen.mp4"),
            Path("deepseek.mp4"),
            Path("mask-a.png"),
            Path("mask-b.png"),
            Path("comparison.mp4"),
            duration=8.0,
            preset="medium",
            crf=18,
        )

        self.assertIn("comparison.png", command)
        self.assertIn("qwen.mp4", command)
        self.assertIn("deepseek.mp4", command)
        filter_graph = command[command.index("-filter_complex") + 1]
        self.assertIn("[1:v:0]", filter_graph)
        self.assertIn("[2:v:0]", filter_graph)
        self.assertIn("overlay=53:277", filter_graph)
        self.assertIn("overlay=1013:277", filter_graph)
        self.assertIn("alphamerge[a-rounded]", filter_graph)
        self.assertIn("alphamerge[b-rounded]", filter_graph)
        self.assertIn("-an", command)
        self.assertEqual(command[-1], "comparison.mp4")

    def test_default_duration_keeps_both_panels_moving(self) -> None:
        probe_a = {"format": {"duration": "8.000000"}}
        probe_b = {"format": {"duration": "6.500000"}}

        self.assertEqual(self.renderer.comparison_duration(probe_a, probe_b, None), 6.5)
        with self.assertRaisesRegex(SystemExit, "both comparison panels must remain moving"):
            self.renderer.comparison_duration(probe_a, probe_b, 7.0)

    def test_skill_publishes_only_the_two_panel_comparison_video(self) -> None:
        instructions = (SKILL_DIR / "SKILL.md").read_text(encoding="utf-8")

        self.assertIn("--comparison", instructions)
        self.assertIn("--video-a", instructions)
        self.assertIn("--video-b", instructions)
        self.assertIn("The only publishable video is the combined", instructions)
        self.assertNotIn('--input "<output-folder>/<video-stem>-raw.mp4"', instructions)


if __name__ == "__main__":
    unittest.main()
