from __future__ import annotations

import subprocess
import unittest
from pathlib import Path


SKILL_DIR = Path(__file__).resolve().parents[1]
SCRIPT = SKILL_DIR / "scripts" / "record_site.mjs"


class LiveSiteRecorderTests(unittest.TestCase):
    def test_recorder_is_valid_javascript(self) -> None:
        result = subprocess.run(
            ["node", "--check", str(SCRIPT)],
            text=True,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            check=False,
        )
        self.assertEqual(result.returncode, 0, result.stderr)

    def test_help_describes_a_continuous_live_recording(self) -> None:
        result = subprocess.run(
            ["node", str(SCRIPT), "--help"],
            text=True,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            check=False,
        )
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertIn("one continuous live Chrome page session", result.stdout)
        self.assertIn("FFmpeg's native screen capture", result.stdout)

    def test_ffmpeg_is_the_live_capture_source(self) -> None:
        source = SCRIPT.read_text(encoding="utf-8")

        self.assertIn('"avfoundation"', source)
        self.assertIn('ffmpeg_is_capture_source: true', source)
        self.assertIn('direct_realtime_capture: true', source)
        self.assertIn('continuous_page_session: true', source)
        self.assertNotIn('Page.startScreencast', source)
        self.assertNotIn('"image2pipe"', source)

    def test_scroll_capture_uses_a_slow_recorder_owned_motion_profile(self) -> None:
        source = SCRIPT.read_text(encoding="utf-8")

        self.assertIn("const DEFAULT_DURATION = 14;", source)
        self.assertIn("const DEFAULT_FPS = 60;", source)
        self.assertIn('setProperty("scroll-behavior", "auto", "important")', source)
        self.assertIn('behavior: "instant"', source)
        self.assertIn("buffered_capture: false", source)
        self.assertIn("scroll_traces:", source)
        self.assertNotIn("1500,", source)
        self.assertNotIn("1300,", source)

    def test_recorder_activates_generic_demo_controls(self) -> None:
        source = SCRIPT.read_text(encoding="utf-8")

        self.assertIn('name: "activate_primary_control"', source)
        self.assertIn("start|play|run|launch|begin|race", source)
        self.assertIn('name: "activate_replay_control"', source)
        self.assertNotIn('name: "select_alternate_mission"', source)
        self.assertNotIn('name: "open_reservation"', source)

    def test_skill_routes_raw_video_capture_through_live_recorder(self) -> None:
        instructions = (SKILL_DIR / "SKILL.md").read_text(encoding="utf-8")

        self.assertIn("scripts/record_site.mjs", instructions)
        self.assertIn("one continuous live Chrome session", instructions)
        self.assertIn("native screen-capture input as the recorder", instructions)


if __name__ == "__main__":
    unittest.main()
