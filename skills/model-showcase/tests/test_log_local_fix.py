from __future__ import annotations

import importlib.util
import json
import tempfile
import types
import unittest
from pathlib import Path


SCRIPT = Path(__file__).resolve().parents[1] / "scripts" / "log_local_fix.py"


def load_script():
    spec = importlib.util.spec_from_file_location("log_local_fix", SCRIPT)
    if spec is None or spec.loader is None:
        raise RuntimeError(f"Could not load {SCRIPT}")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


class LocalFixTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.script = load_script()

    def prepare(self, root: Path, repair_count: int) -> None:
        root.joinpath("index.html").write_text("before", encoding="utf-8")
        state = {
            "repair_count": repair_count,
            "versions": [{"number": number} for number in range(repair_count + 1)],
        }
        root.joinpath("showcase-state.json").write_text(
            json.dumps(state), encoding="utf-8"
        )

    def test_local_fix_requires_three_model_repairs(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            self.prepare(root, 2)
            args = types.SimpleNamespace(
                workspace=root, reason="wheel detached", check=["subject integrity"]
            )
            with self.assertRaisesRegex(SystemExit, "three model repair prompts"):
                self.script.begin(args)

    def test_local_fix_preserves_before_and_after_and_logs_scope(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            self.prepare(root, 3)
            begin_args = types.SimpleNamespace(
                workspace=root,
                reason="kart floats above road",
                check=["subject remains grounded"],
            )
            self.assertEqual(self.script.begin(begin_args), 0)
            root.joinpath("index.html").write_text("after", encoding="utf-8")
            finish_args = types.SimpleNamespace(
                workspace=root, changed_file=["index.html"]
            )
            self.assertEqual(self.script.finish(finish_args), 0)
            log = json.loads((root / "repair-log.json").read_text())
            entry = log["repairs"][0]
            self.assertEqual(entry["actor"], "local")
            self.assertEqual(entry["checklist_failures"], ["subject remains grounded"])
            self.assertEqual((root / entry["before"]).read_text(), "before")
            self.assertEqual((root / entry["after"]).read_text(), "after")


if __name__ == "__main__":
    unittest.main()
