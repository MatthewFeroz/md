"""Exercise restoration through the same CLI used on a new machine."""

from pathlib import Path
import shutil
import subprocess
import sys
import tempfile
import unittest


REPO = Path(__file__).resolve().parents[1]


class InstallTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory(prefix="md-restore-test-")
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name).resolve()
        self.home = self.root / "Matthew home"
        self.home.mkdir()

    def install(self, *args, repo=REPO):
        return subprocess.run(
            [sys.executable, str(repo / "install.py"), "--home", str(self.home), *args],
            text=True, capture_output=True,
        )

    def write(self, relative, content):
        path = self.home / relative
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(content)
        return path

    def assert_restored(self):
        self.assertEqual((self.home / ".agents/AGENTS.md").read_bytes(), (REPO / "global/AGENTS.md").read_bytes())
        self.assertEqual((self.home / ".claude/CLAUDE.md").read_bytes(), (REPO / "global/CLAUDE.md").read_bytes())
        self.assertTrue((self.home / ".codex/AGENTS.md").is_symlink())
        self.assertEqual((self.home / ".codex/AGENTS.md").resolve(), self.home / ".agents/AGENTS.md")
        for name in ("unslop", "mock", "writing-for-agents"):
            source = REPO / "skills" / name
            target = self.home / ".agents/skills" / name
            self.assertEqual({p.relative_to(source) for p in source.rglob("*")}, {p.relative_to(target) for p in target.rglob("*")})
            for file in source.rglob("*"):
                if file.is_file():
                    self.assertEqual(file.read_bytes(), (target / file.relative_to(source)).read_bytes())
            for tool in (".claude", ".codex"):
                link = self.home / tool / "skills" / name
                self.assertTrue(link.is_symlink())
                self.assertEqual(link.resolve(), target)
                self.assertEqual((link / "SKILL.md").read_bytes(), (source / "SKILL.md").read_bytes())
        self.assertEqual((self.home / ".claude/CLAUDE.md").read_text().splitlines()[0], "@~/.agents/AGENTS.md")

    def test_fresh_install_and_repeat(self):
        first = self.install()
        self.assertEqual(first.returncode, 0, first.stderr)
        self.assert_restored()
        second = self.install()
        self.assertEqual(second.returncode, 0, second.stderr)
        self.assertIn("No changes needed", second.stdout)
        self.assertFalse((self.home / ".agents/backups").exists())

    def test_existing_copies_are_preserved_and_unrelated_files_stay(self):
        old_files = {
            ".agents/AGENTS.md": "Old shared rules\n",
            ".claude/CLAUDE.md": "Old Claude rules\n",
            ".agents/skills/mock/old.html": "My old mock\n",
            ".codex/skills/mock/SKILL.md": "My old Codex mock\n",
            ".claude/skills/unslop": "Old unslop file\n",
        }
        for path, content in old_files.items():
            self.write(path, content)
        config = self.write(".codex/config.toml", 'model = "my-existing-model"\n')
        content_skill = self.write(".claude/skills/clean-edit/SKILL.md", "Keep my video skill\n")
        external = self.root / "External rules.md"
        external.write_text("Keep this symlink target\n")
        link = self.home / ".codex/AGENTS.md"
        link.symlink_to(external)
        result = self.install()
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assert_restored()
        backups = list((self.home / ".agents/backups").iterdir())
        self.assertEqual(len(backups), 1)
        for path, content in old_files.items():
            self.assertEqual((backups[0] / path).read_text(), content)
        preserved_link = backups[0] / ".codex/AGENTS.md"
        self.assertTrue(preserved_link.is_symlink())
        self.assertEqual(preserved_link.resolve(), external)
        self.assertEqual(external.read_text(), "Keep this symlink target\n")
        self.assertEqual(config.read_text(), 'model = "my-existing-model"\n')
        self.assertEqual(content_skill.read_text(), "Keep my video skill\n")
        self.assertEqual(self.install().returncode, 0)
        self.assertEqual(len(list((self.home / ".agents/backups").iterdir())), 1)

    def test_dry_run_writes_nothing(self):
        result = self.install("--dry-run")
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertEqual(list(self.home.iterdir()), [])
        old = self.write(".agents/AGENTS.md", "Old rules\n")
        before = set(self.home.rglob("*"))
        result = self.install("--dry-run")
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertEqual(set(self.home.rglob("*")), before)
        self.assertEqual(old.read_text(), "Old rules\n")

    def test_parent_symlink_stops_before_writing(self):
        external = self.root / "External Claude folder"
        external.mkdir()
        (self.home / ".claude").symlink_to(external)
        result = self.install()
        self.assertNotEqual(result.returncode, 0)
        self.assertIn("Expected a real directory", result.stderr)
        self.assertEqual(list(external.iterdir()), [])
        self.assertFalse((self.home / ".agents").exists())

    def test_missing_supporting_file_stops_before_writing(self):
        incomplete = self.root / "Incomplete backup"
        incomplete.mkdir()
        shutil.copy2(REPO / "install.py", incomplete / "install.py")
        shutil.copytree(REPO / "global", incomplete / "global")
        for name in ("unslop", "mock", "writing-for-agents"):
            shutil.copytree(REPO / "skills" / name, incomplete / "skills" / name)
        (incomplete / "skills/mock/harness.html").unlink()
        result = self.install(repo=incomplete)
        self.assertNotEqual(result.returncode, 0)
        self.assertIn("skills/mock/harness.html", result.stderr)
        self.assertEqual(list(self.home.iterdir()), [])


if __name__ == "__main__":
    unittest.main()
