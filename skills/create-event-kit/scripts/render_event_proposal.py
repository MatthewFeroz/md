#!/usr/bin/env python3
"""Render a one-page event proposal as self-contained HTML and optional PDF."""

from __future__ import annotations

import argparse
import html
import os
import re
import shutil
import subprocess
import tempfile
from pathlib import Path
from urllib.parse import urlparse


SKILL_ROOT = Path(__file__).resolve().parent.parent
TEMPLATE_PATH = SKILL_ROOT / "assets" / "event-proposal-template.html"
TOKEN_PATTERN = re.compile(r"\{\{[A-Z_]+\}\}")


def escape_text(value: str) -> str:
    normalized = value.replace("\u2014", " - ").replace("\u2013", "-").replace("\u2011", "-")
    return html.escape(normalized)


def read_brief(path: Path) -> tuple[str, list[str]]:
    markdown = path.read_text(encoding="utf-8").strip()
    lines = markdown.splitlines()
    if not lines or not lines[0].startswith("# "):
        raise ValueError("event-brief.md must begin with an H1 title")
    title = lines[0][2:].strip()
    paragraphs = [
        block.strip()
        for block in re.split(r"\n\s*\n", "\n".join(lines[1:]).strip())
        if block.strip()
    ]
    if not paragraphs:
        raise ValueError("event-brief.md must contain proposal copy")
    return title, paragraphs


def read_socials(path: Path) -> dict[str, str]:
    markdown = path.read_text(encoding="utf-8")
    sections: dict[str, str] = {}
    matches = list(re.finditer(r"(?m)^## (.+?)\s*$", markdown))
    for index, match in enumerate(matches):
        start = match.end()
        end = matches[index + 1].start() if index + 1 < len(matches) else len(markdown)
        sections[match.group(1).strip().lower()] = markdown[start:end].strip()
    return sections


def replace_tokens(template: str, values: dict[str, str]) -> str:
    rendered = template
    for key, value in values.items():
        rendered = rendered.replace(f"{{{{{key}}}}}", value)
    unresolved = sorted(set(TOKEN_PATTERN.findall(rendered)))
    if unresolved:
        raise ValueError(f"Unresolved template tokens: {', '.join(unresolved)}")
    return rendered


def render_partner_guide(url: str | None, label: str) -> str:
    if not url:
        return ""
    parsed = urlparse(url)
    if parsed.scheme not in {"http", "https"} or not parsed.netloc:
        raise ValueError("--partner-guide-url must be an absolute http(s) URL")
    safe_url = html.escape(url, quote=True)
    return f'<a class="partner-guide" href="{safe_url}">{escape_text(label)} →</a>'


def render_voices(entries: list[str], companies: list[str]) -> str:
    values = entries or companies
    voices: list[str] = []
    for value in values:
        name, separator, role = value.partition("|")
        name = name.strip()
        role = role.strip()
        if not name:
            raise ValueError("--voice entries must include a name before the optional |")
        role_html = f'<p class="voice-role">{escape_text(role)}</p>' if separator and role else ""
        voices.append(
            '<div class="voice-item">'
            f'<p class="voice-name">{escape_text(name)}</p>'
            f"{role_html}"
            "</div>"
        )
    return "".join(voices)


def find_chrome() -> str | None:
    configured = os.environ.get("EVENT_PROPOSAL_CHROME")
    candidates = [
        configured,
        shutil.which("google-chrome"),
        shutil.which("chromium"),
        shutil.which("chromium-browser"),
        "/Applications/Google Chrome.app/Contents/MacOS/Google Chrome",
        "/Applications/Chromium.app/Contents/MacOS/Chromium",
    ]
    for candidate in candidates:
        if candidate and Path(candidate).is_file():
            return candidate
    return None


def export_pdf(html_path: Path, pdf_path: Path) -> None:
    chrome = find_chrome()
    if not chrome:
        raise RuntimeError(
            "Chrome or Chromium is required for PDF export; set EVENT_PROPOSAL_CHROME to its executable"
        )
    with tempfile.TemporaryDirectory(prefix="event-proposal-chrome-") as profile:
        command = [
            chrome,
            "--headless=new",
            "--disable-gpu",
            "--disable-dev-shm-usage",
            "--no-pdf-header-footer",
            f"--user-data-dir={profile}",
            f"--print-to-pdf={pdf_path}",
            html_path.resolve().as_uri(),
        ]
        completed = subprocess.run(command, capture_output=True, text=True, timeout=60)
    if completed.returncode != 0 or not pdf_path.is_file():
        details = completed.stderr.strip() or completed.stdout.strip() or "unknown Chrome error"
        raise RuntimeError(f"PDF export failed: {details}")


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("event_folder", type=Path)
    parser.add_argument("output_folder", type=Path)
    parser.add_argument("--company", action="append", required=True, help="Repeat in display order")
    parser.add_argument("--discussion", action="append", help="Repeat for each discussion anchor")
    parser.add_argument(
        "--voice",
        action="append",
        help="Repeat as 'name|role or perspective'; defaults to company names",
    )
    parser.add_argument("--audience", default="Audience to be confirmed.")
    parser.add_argument(
        "--outcome",
        default="A focused conversation that gives attendees a clearer way to act on the event thesis.",
    )
    parser.add_argument(
        "--status",
        default="Format, date, venue, speakers, and registration to be confirmed collaboratively.",
    )
    parser.add_argument("--partner-guide-url")
    parser.add_argument("--partner-guide-label", default="Partner guide")
    parser.add_argument("--pdf", action="store_true", help="Also export event-proposal.pdf")
    args = parser.parse_args()

    event_folder = args.event_folder.resolve()
    output_folder = args.output_folder.resolve()
    title, paragraphs = read_brief(event_folder / "event-brief.md")
    socials = read_socials(event_folder / "socials-description.md")
    discussions = args.discussion or [
        "What changes if the event thesis is true?",
        "What must teams build or change to act on it?",
        "Where should people remain in the loop?",
    ]

    overview_html = "".join(f"<p>{escape_text(paragraph)}</p>" for paragraph in paragraphs)
    discussion_html = "".join(
        '<div class="discussion-item">'
        f'<div class="discussion-number">{index:02d}</div>'
        f'<p class="discussion-text">{escape_text(question)}</p>'
        "</div>"
        for index, question in enumerate(discussions, start=1)
    )
    thesis = socials.get("main theme", title)
    values = {
        "DOCUMENT_TITLE": escape_text(f"{title} - Event Proposal"),
        "COMPANY_LINE": escape_text(" × ".join(args.company)),
        "TITLE": escape_text(title),
        "THESIS": escape_text(thesis),
        "OVERVIEW_HTML": overview_html,
        "VOICE_HTML": render_voices(args.voice or [], args.company),
        "DISCUSSION_HTML": discussion_html,
        "AUDIENCE": escape_text(args.audience),
        "OUTCOME": escape_text(args.outcome),
        "STATUS": escape_text(args.status),
        "PARTNER_GUIDE_HTML": render_partner_guide(
            args.partner_guide_url, args.partner_guide_label
        ),
    }

    template = TEMPLATE_PATH.read_text(encoding="utf-8")
    rendered = replace_tokens(template, values)
    output_folder.mkdir(parents=True, exist_ok=True)
    html_path = output_folder / "event-proposal.html"
    html_path.write_text(rendered, encoding="utf-8")
    print(f"Wrote {html_path}")

    if args.pdf:
        pdf_path = output_folder / "event-proposal.pdf"
        export_pdf(html_path, pdf_path)
        print(f"Wrote {pdf_path}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
