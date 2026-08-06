#!/usr/bin/env python3
"""Render a self-contained, responsive Luma-style planning preview for an event kit."""

from __future__ import annotations

import argparse
import base64
import html
import mimetypes
import re
from pathlib import Path


LOGO_EXTENSIONS = {".svg", ".png", ".jpg", ".jpeg", ".webp"}
MONTHS = (
    "January",
    "February",
    "March",
    "April",
    "May",
    "June",
    "July",
    "August",
    "September",
    "October",
    "November",
    "December",
)


def parse_markdown_blocks(path: Path) -> list[str]:
    return [block.strip() for block in re.split(r"\n\s*\n", path.read_text(encoding="utf-8").strip())]


def read_brief(path: Path) -> tuple[str, list[str]]:
    blocks = parse_markdown_blocks(path)
    if not blocks or not blocks[0].startswith("# "):
        raise ValueError("event-brief.md must begin with an H1 title")
    title = blocks[0][2:].strip()
    paragraphs = [block for block in blocks[1:] if not block.startswith("#")]
    if not paragraphs:
        raise ValueError("event-brief.md must include prose after its title")
    return title, paragraphs


def read_theme(path: Path) -> str:
    text = path.read_text(encoding="utf-8")
    match = re.search(r"(?ms)^## Main theme\s*\n\s*(.+?)(?=\n\s*\n## |\Z)", text)
    if not match:
        raise ValueError("socials-description.md must include a Main theme section")
    return " ".join(match.group(1).split())


def data_uri(path: Path) -> str:
    mime = mimetypes.guess_type(path.name)[0]
    if path.suffix.lower() == ".svg":
        mime = "image/svg+xml"
    if not mime:
        raise ValueError(f"Cannot determine image type for {path.name}")
    encoded = base64.b64encode(path.read_bytes()).decode("ascii")
    return f"data:{mime};base64,{encoded}"


def company_name(path: Path) -> str:
    slug = re.sub(r"-logo$", "", path.stem)
    words = slug.split("-")
    aliases = {"ai": "AI", "api": "API", "aws": "AWS", "ibm": "IBM", "posthog": "PostHog"}
    return " ".join(aliases.get(word, word.capitalize()) for word in words)


def logo_assets(folder: Path) -> list[tuple[str, str]]:
    paths = sorted(
        path for path in folder.iterdir() if path.is_file() and path.suffix.lower() in LOGO_EXTENSIONS
    )
    if not paths:
        raise ValueError("luma-event-poster must contain at least one supported logo")
    return [(company_name(path), data_uri(path)) for path in paths]


def logo_chips(logos: list[tuple[str, str]]) -> str:
    return "\n".join(
        '<span class="logo-chip">'
        f'<img src="{uri}" alt="{html.escape(name, quote=True)} logo">'
        "</span>"
        for name, uri in logos
    )


def side_panel(presented_by: str, theme: str, hosts: list[str], logos: list[tuple[str, str]]) -> str:
    logo_by_name = {name.casefold(): uri for name, uri in logos}
    first_uri = logos[0][1]
    host_items: list[str] = []
    for host in hosts:
        uri = logo_by_name.get(host.casefold(), first_uri)
        host_items.append(
            "<li>"
            f'<span class="host-mark"><img src="{uri}" alt=""></span>'
            f"<span>{html.escape(host)}</span>"
            "</li>"
        )
    return (
        '<div class="side-panel">'
        '<div class="side-label">Presented by</div>'
        '<div class="presented-row">'
        f'<span class="org-mark"><img src="{first_uri}" alt=""></span>'
        f"<span>{html.escape(presented_by)}</span>"
        "</div>"
        f'<p class="side-copy">{html.escape(theme)}</p>'
        '<section class="host-section">'
        '<div class="side-label">Hosted By</div>'
        f'<ul class="host-list">{"".join(host_items)}</ul>'
        "</section>"
        "</div>"
    )


def cover_media(
    cover_path: Path | None,
    title: str,
    theme: str,
    logos: list[tuple[str, str]],
) -> str:
    if cover_path:
        if not cover_path.is_file():
            raise ValueError(f"Cover image does not exist: {cover_path}")
        return f'<img src="{data_uri(cover_path)}" alt="{html.escape(title, quote=True)} event cover">'
    return (
        '<div class="generated-cover">'
        f'<div class="cover-kicker">{html.escape(theme)}</div>'
        f'<div class="cover-title">{html.escape(title)}</div>'
        f'<div class="cover-logos">{logo_chips(logos)}</div>'
        "</div>"
    )


def calendar_tile(date_label: str) -> tuple[str, str]:
    month_match = re.search(rf"\b({'|'.join(MONTHS)})\b", date_label, re.IGNORECASE)
    day_match = re.search(r"\b([1-9]|[12]\d|3[01])(?:st|nd|rd|th)?\b", date_label, re.IGNORECASE)
    month = month_match.group(1)[:3].upper() if month_match else "TBA"
    day = day_match.group(1) if day_match else "—"
    return month, day


def render(args: argparse.Namespace) -> Path:
    root = args.event_folder.resolve()
    brief_path = root / "event-brief.md"
    socials_path = root / "socials-description.md"
    logos_path = root / "luma-event-poster"
    for required in (brief_path, socials_path, logos_path):
        if not required.exists():
            raise ValueError(f"Missing required event-kit entry: {required.name}")

    title, paragraphs = read_brief(brief_path)
    theme = args.theme_label or read_theme(socials_path)
    logos = logo_assets(logos_path)
    company_names = [name for name, _ in logos]
    presented_by = args.presented_by or " × ".join(company_names)
    hosts = args.host or company_names
    month, day = calendar_tile(args.date)

    template_path = Path(__file__).resolve().parent.parent / "assets" / "luma-preview-template.html"
    template = template_path.read_text(encoding="utf-8")
    replacements = {
        "TITLE": html.escape(title),
        "THEME_LABEL": html.escape(theme),
        "MONTH": html.escape(month),
        "DAY": html.escape(day),
        "DATE": html.escape(args.date),
        "TIME": html.escape(args.time),
        "LOCATION": html.escape(args.location),
        "REGISTRATION_NOTE": html.escape(args.registration_note),
        "CTA": html.escape(args.cta),
        "ABOUT": "\n".join(f"<p>{html.escape(paragraph)}</p>" for paragraph in paragraphs),
        "COVER_MEDIA": cover_media(args.cover_image, title, theme, logos),
        "SIDE_PANEL": side_panel(presented_by, theme, hosts, logos),
    }
    rendered = template
    for key, value in replacements.items():
        rendered = rendered.replace("{{" + key + "}}", value)
    remaining = sorted(set(re.findall(r"\{\{([A-Z_]+)\}\}", rendered)))
    if remaining:
        raise ValueError(f"Unresolved template placeholders: {', '.join(remaining)}")

    output = args.output.resolve() if args.output else root / "luma-preview.html"
    output.write_text(rendered, encoding="utf-8")
    return output


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("event_folder", type=Path, help="Folder containing the three core event-kit inputs")
    parser.add_argument("--output", type=Path, help="Output HTML path; defaults to <event-folder>/luma-preview.html")
    parser.add_argument("--date", default="Date to be announced")
    parser.add_argument("--time", default="Time to be announced")
    parser.add_argument("--location", default="Location to be announced")
    parser.add_argument("--presented-by", help="Displayed presenter label; defaults to the logo company names")
    parser.add_argument("--host", action="append", help="Repeat for each host; defaults to the logo company names")
    parser.add_argument("--registration-note", default="Registration details coming soon.")
    parser.add_argument("--cta", default="Request to Join")
    parser.add_argument("--cover-image", type=Path, help="Optional official cover image; otherwise generate a CSS poster")
    parser.add_argument("--theme-label", help="Featured-theme label; defaults to Main theme in socials-description.md")
    args = parser.parse_args()

    try:
        output = render(args)
    except (OSError, ValueError) as error:
        parser.error(str(error))
    print(f"Luma-style planning preview created: {output}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
