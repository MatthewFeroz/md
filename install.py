#!/usr/bin/env python3
"""Restore the shared rulebook and three core skills to a Mac user directory."""

from __future__ import annotations

import argparse
from datetime import datetime
import os
from pathlib import Path
import shutil
import sys
import tempfile


REPO = Path(__file__).resolve().parent
SKILLS = ("unslop", "mock", "writing-for-agents")
REQUIRED_FILES = (
    "global/AGENTS.md",
    "global/CLAUDE.md",
    "skills/unslop/SKILL.md",
    "skills/mock/SKILL.md",
    "skills/mock/harness.html",
    "skills/writing-for-agents/SKILL.md",
    "skills/writing-for-agents/SKILL-MECHANICS.md",
    "skills/writing-for-agents/THIRD_PARTY_LICENSE_mattpocock.txt",
)
MANAGED_DIRS = (
    ".agents",
    ".agents/skills",
    ".agents/backups",
    ".codex",
    ".codex/skills",
    ".claude",
    ".claude/skills",
)


def same_copy(source: Path, target: Path) -> bool:
    """Compare all files and directory entries, including supporting resources."""
    if target.is_symlink():
        return False
    if source.is_file():
        return target.is_file() and source.read_bytes() == target.read_bytes()
    if not target.is_dir():
        return False
    source_entries = {p.relative_to(source) for p in source.rglob("*")}
    target_entries = {p.relative_to(target) for p in target.rglob("*")}
    if source_entries != target_entries:
        return False
    for relative in source_entries:
        left, right = source / relative, target / relative
        if left.is_symlink() or right.is_symlink():
            if not (left.is_symlink() and right.is_symlink()):
                return False
            if os.readlink(left) != os.readlink(right):
                return False
        elif left.is_dir() != right.is_dir():
            return False
        elif left.is_file() and left.read_bytes() != right.read_bytes():
            return False
    return True


class Installer:
    def __init__(self, home: Path, dry_run: bool):
        self.home = home
        self.dry_run = dry_run
        stamp = datetime.now().strftime("%Y%m%d-%H%M%S-%f")
        self.backup = home / ".agents/backups" / ("md-" + stamp)
        self.changed = 0
        self.backed_up = False

    def replace(self, target: Path, populate) -> None:
        relative = target.relative_to(self.home)
        exists = target.exists() or target.is_symlink()
        print(f"{'Would install' if self.dry_run else 'Install'} {relative}")
        self.changed += 1
        if self.dry_run:
            if exists:
                print(f"  Would preserve existing copy at {self.backup / relative}")
            return
        target.parent.mkdir(parents=True, exist_ok=True)
        # Prepare the replacement before moving any existing file or directory.
        with tempfile.TemporaryDirectory(prefix=".md-install-", dir=target.parent) as stage:
            prepared = Path(stage) / "replacement"
            populate(prepared)
            if exists:
                previous = self.backup / relative
                previous.parent.mkdir(parents=True, exist_ok=True)
                target.rename(previous)
                self.backed_up = True
                print(f"  Preserved existing copy at {previous}")
            try:
                prepared.rename(target)
            except OSError:
                if exists:
                    previous.rename(target)
                raise

    def copy(self, source: Path, target: Path) -> None:
        if same_copy(source, target):
            print(f"Keep {target.relative_to(self.home)}")
            return
        if source.is_dir():
            self.replace(target, lambda staged: shutil.copytree(source, staged, symlinks=True))
        else:
            self.replace(target, lambda staged: shutil.copy2(source, staged))

    def link(self, source: Path, target: Path) -> None:
        if target.is_symlink() and target.resolve() == source.resolve():
            print(f"Keep {target.relative_to(self.home)}")
            return
        relative_source = os.path.relpath(source, start=target.parent)
        self.replace(target, lambda staged: staged.symlink_to(relative_source))

    def run(self) -> None:
        for name in REQUIRED_FILES:
            if not (REPO / name).is_file():
                raise ValueError(f"Backup is incomplete: missing {name}")
        for name in MANAGED_DIRS:
            path = self.home / name
            if path.is_symlink() or (path.exists() and not path.is_dir()):
                raise ValueError(f"Expected a real directory at {path}; installation stopped")
        for name in SKILLS:
            source = REPO / "skills" / name
            target = self.home / ".agents/skills" / name
            if source == target or source in target.parents or target in source.parents:
                raise ValueError(f"Source and destination overlap: {source} and {target}")

        print(f"{'Previewing installation into' if self.dry_run else 'Installing into'} {self.home}")
        self.copy(REPO / "global/AGENTS.md", self.home / ".agents/AGENTS.md")
        self.copy(REPO / "global/CLAUDE.md", self.home / ".claude/CLAUDE.md")
        for name in SKILLS:
            self.copy(REPO / "skills" / name, self.home / ".agents/skills" / name)
        self.link(self.home / ".agents/AGENTS.md", self.home / ".codex/AGENTS.md")
        for tool in (".claude", ".codex"):
            for name in SKILLS:
                self.link(self.home / ".agents/skills" / name, self.home / tool / "skills" / name)

        if self.changed == 0:
            print("No changes needed; this setup already matches the backup.")
        elif self.dry_run:
            print("Preview complete; no files changed.")
        else:
            print("Installation complete. Start a fresh Claude Code or Codex session.")
        if self.backed_up:
            print(f"Previous copies: {self.backup}")


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--home", type=Path, default=Path.home(), help="Target user directory; defaults to your home")
    parser.add_argument("--dry-run", action="store_true", help="Show planned changes without writing files")
    args = parser.parse_args()
    home = args.home.expanduser().resolve()
    if home.exists() and not home.is_dir():
        parser.error(f"Target home is not a directory: {home}")
    installer = Installer(home, args.dry_run)
    try:
        installer.run()
    except (OSError, ValueError) as error:
        print(f"Installation stopped: {error}", file=sys.stderr)
        if installer.backed_up:
            print(f"Previous copies are preserved at {installer.backup}", file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())
