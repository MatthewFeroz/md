#!/usr/bin/env python3
"""Validate the deterministic structure of a create-event-kit package."""

from __future__ import annotations

import argparse
import re
import sys
from pathlib import Path


EXPECTED_ENTRIES = {
    "event-brief.md",
    "luma-event-poster",
    "socials-description.md",
}
LOGO_EXTENSIONS = {".svg", ".png", ".jpg", ".jpeg", ".webp"}
LOGO_NAME = re.compile(r"^[a-z0-9]+(?:-[a-z0-9]+)*-logo\.(?:svg|png|jpe?g|webp)$")
SOCIALS_PATTERN = re.compile(
    r"\A# Socials / Description[ \t]*\n\s*\n"
    r"## Main theme[ \t]*\n\s*\n(?P<theme>.+?)\n\s*\n"
    r"## Main idea[ \t]*\n\s*\n(?P<idea>.+?)\n\s*\n"
    r"## Social description[ \t]*\n\s*\n(?P<description>.+?)\s*\Z",
    re.DOTALL,
)


def word_count(text: str) -> int:
    return len(re.findall(r"\b[\w’'-]+\b", text))


def prose_blocks(markdown: str) -> list[str]:
    blocks = re.split(r"\n\s*\n", markdown.strip())
    return [
        block.strip()
        for block in blocks
        if block.strip() and not block.lstrip().startswith(("#", "- ", "* ", ">", "```"))
    ]


def looks_like_image(path: Path) -> bool:
    data = path.read_bytes()
    if not data:
        return False
    suffix = path.suffix.lower()
    if suffix == ".svg":
        return b"<svg" in data[:4096].lower()
    if suffix == ".png":
        return data.startswith(b"\x89PNG\r\n\x1a\n")
    if suffix in {".jpg", ".jpeg"}:
        return data.startswith(b"\xff\xd8\xff")
    if suffix == ".webp":
        return len(data) >= 12 and data[:4] == b"RIFF" and data[8:12] == b"WEBP"
    return False


def validate(root: Path) -> list[str]:
    errors: list[str] = []
    if not root.is_dir():
        return [f"Event folder does not exist or is not a directory: {root}"]

    entries = {item.name for item in root.iterdir()}
    missing = EXPECTED_ENTRIES - entries
    extra = entries - EXPECTED_ENTRIES
    if missing:
        errors.append(f"Missing package entries: {', '.join(sorted(missing))}")
    if extra:
        errors.append(f"Unexpected package entries: {', '.join(sorted(extra))}")

    brief_path = root / "event-brief.md"
    if brief_path.is_file():
        brief = brief_path.read_text(encoding="utf-8")
        if not re.match(r"\A# [^#\n]+(?:\n|\Z)", brief):
            errors.append("event-brief.md must begin with an H1 event title")
        if len(re.findall(r"(?m)^#{1,6} ", brief)) != 1:
            errors.append("event-brief.md must contain only its H1 title heading")
        paragraphs = prose_blocks(brief)
        if not 2 <= len(paragraphs) <= 3:
            errors.append("event-brief.md must contain two or three prose paragraphs")
        brief_words = word_count(" ".join(paragraphs))
        if not 80 <= brief_words <= 240:
            errors.append(f"event-brief.md must contain 80–240 prose words; found {brief_words}")
    elif brief_path.exists():
        errors.append("event-brief.md must be a file")

    logos_path = root / "luma-event-poster"
    if logos_path.is_dir():
        logos = list(logos_path.iterdir())
        if not logos:
            errors.append("luma-event-poster must contain at least one logo")
        for logo in logos:
            if not logo.is_file():
                errors.append(f"Logo folder contains a non-file entry: {logo.name}")
                continue
            if logo.suffix.lower() not in LOGO_EXTENSIONS:
                errors.append(f"Unsupported logo extension: {logo.name}")
                continue
            if not LOGO_NAME.fullmatch(logo.name):
                errors.append(f"Invalid logo filename: {logo.name}")
            if not looks_like_image(logo):
                errors.append(f"Logo is empty or does not match its extension: {logo.name}")
    elif logos_path.exists():
        errors.append("luma-event-poster must be a directory")

    socials_path = root / "socials-description.md"
    if socials_path.is_file():
        socials = socials_path.read_text(encoding="utf-8")
        match = SOCIALS_PATTERN.fullmatch(socials)
        if not match:
            errors.append("socials-description.md must use the exact required heading and paragraph structure")
        else:
            limits = {
                "theme": (1, 30, "Main theme"),
                "idea": (50, 100, "Main idea"),
                "description": (70, 140, "Social description"),
            }
            for key, (minimum, maximum, label) in limits.items():
                count = word_count(match.group(key))
                if not minimum <= count <= maximum:
                    errors.append(f"{label} must contain {minimum}–{maximum} words; found {count}")
    elif socials_path.exists():
        errors.append("socials-description.md must be a file")

    return errors


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("event_folder", type=Path)
    args = parser.parse_args()

    errors = validate(args.event_folder.resolve())
    if errors:
        print("Event kit validation failed:", file=sys.stderr)
        for error in errors:
            print(f"- {error}", file=sys.stderr)
        return 1

    print(f"Event kit validation passed: {args.event_folder.resolve()}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
