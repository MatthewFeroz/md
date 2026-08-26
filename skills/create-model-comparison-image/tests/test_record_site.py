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

    def test_recorder_uses_screencast_instead_of_screenshot_reload_frames(self) -> None:
        source = SCRIPT.read_text(encoding="utf-8")

        self.assertIn('Page.startScreencast', source)
        self.assertIn('continuous_page_session: true', source)
        self.assertNotIn('--screenshot=', source)

    def test_scroll_capture_uses_a_slow_recorder_owned_motion_profile(self) -> None:
        source = SCRIPT.read_text(encoding="utf-8")

        self.assertIn("const DEFAULT_DURATION = 14;", source)
        self.assertIn("const DEFAULT_FPS = 60;", source)
        self.assertIn('setProperty("scroll-behavior", "auto", "important")', source)
        self.assertIn('behavior: "instant"', source)
        self.assertIn("buffered_capture: true", source)
        self.assertIn("scroll_traces:", source)
        self.assertNotIn("1500,", source)
        self.assertNotIn("1300,", source)

    def test_skill_routes_raw_video_capture_through_live_recorder(self) -> None:
        instructions = (SKILL_DIR / "SKILL.md").read_text(encoding="utf-8")

        self.assertIn("scripts/record_site.mjs", instructions)
        self.assertIn("one continuous page session", instructions)


if __name__ == "__main__":
    unittest.main()
