from __future__ import annotations

import importlib.util
import unittest
from pathlib import Path


SCRIPT = Path(__file__).resolve().parents[1] / "scripts" / "add_music.py"


def load_script():
    spec = importlib.util.spec_from_file_location("add_music", SCRIPT)
    if spec is None or spec.loader is None:
        raise RuntimeError(f"Could not load {SCRIPT}")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


class MusicTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.script = load_script()

    def test_music_defaults_match_the_approved_internal_mix(self) -> None:
        self.assertEqual(self.script.DEFAULT_VOLUME_DB, -14.0)
        self.assertEqual(self.script.DEFAULT_FADE_IN, 0.5)
        self.assertEqual(self.script.DEFAULT_FADE_OUT, 0.8)

    def test_command_loops_music_and_copies_video(self) -> None:
        command = self.script.build_command(
            "ffmpeg",
            Path("silent.mp4"),
            Path("music.mp4"),
            Path("with-music.mp4"),
            video_duration=14.0,
        )
        self.assertIn("-stream_loop", command)
        self.assertIn("volume=-14dB", command[command.index("-filter_complex") + 1])
        self.assertIn(
            "afade=t=in:st=0:d=0.5", command[command.index("-filter_complex") + 1]
        )
        self.assertIn(
            "afade=t=out:st=13.120:d=0.8", command[command.index("-filter_complex") + 1]
        )
        self.assertEqual(command[command.index("-c:v") + 1], "copy")
        self.assertEqual(command[command.index("-b:a") + 1], "192k")


if __name__ == "__main__":
    unittest.main()
