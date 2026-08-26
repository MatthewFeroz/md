#!/usr/bin/env python3
"""Render the locked comparison PNGs and a Figma-importable SVG."""

from __future__ import annotations

import argparse
import base64
import hashlib
import html
import json
import mimetypes
import os
import re
import shutil
import signal
import struct
import subprocess
from pathlib import Path


CANVAS = (1920, 1080)
HEADER_HEIGHT = 187
DIVIDER_WIDTH = 2
LOGO_BOXES = {"a": 108, "b": 96}
HEADER_GAP = 30
HEADER_MAX_WIDTHS = {"a": 683, "b": 801}
NAME_SIZE = 96
SHOT_A_X = 52.7010498046875
SHOT_A_WIDTH = 854.5978393554688
SHOT_A_RADIUS = 8.152
SHOT_B_X = 1013.369140625
SHOT_B_WIDTH = 853.2615966796875
SHOT_B_RADIUS = 8.146
SHOT_Y = 277.0
SHOT_HEIGHT = 615.0
PANEL_SHADOW = {
    "primary": {"dx": 0, "dy": 12, "std_deviation": 12, "opacity": 0.12},
    "contact": {"dx": 0, "dy": 2, "std_deviation": 3, "opacity": 0.08},
}
FONT_FILES = ("FHOscarPro-SemiBold.otf", "FHOscarPro-Light.otf")
CHROME_TIMEOUT_SECONDS = 120

# Locked from Figma file 68puDwQfM9TSOGY0xve1KA. Node 3:2614 is the
# complete 1920x1080 comparison frame; node 3:2660 is its MERGE badge.
FIGMA_FILE_KEY = "68puDwQfM9TSOGY0xve1KA"
FIGMA_LAYOUT_NODE_ID = "3:2614"
FIGMA_NODE_ID = "3:2660"
MERGE_BADGE_X = 770.0
MERGE_BADGE_Y = 930.5
MERGE_BADGE_WIDTH = 378.0297546386719
MERGE_BADGE_HEIGHT = 111.0
MERGE_BADGE_BORDER = 3.0
MERGE_BADGE_RADIUS = 97.5
MERGE_BADGE_FILL = "#FAF8F5"
MERGE_BADGE_STROKE = "#D9D9D9"
MERGE_LOCKUP_X = 50.99992370605469
MERGE_LOCKUP_Y = 27.0
MERGE_LOCKUP_WIDTH = 276.0297546386719
MERGE_LOCKUP_HEIGHT = 57.0
MERGE_MARK_WIDTH = 46.18862533569336
MERGE_MARK_HEIGHT = 57.0
MERGE_WORDMARK_X = 75.57760620117188
MERGE_WORDMARK_Y = 9.780256271362305
MERGE_WORDMARK_WIDTH = 200.4523162841797
MERGE_WORDMARK_HEIGHT = 37.41017532348633
MERGE_BADGE_FILES = {
    "merge-mark.svg": "ae97c225009a617dc4e9cc0b858a5f6195e47c8b0ff6d773338052b1532137e8",
    "merge-wordmark.svg": "fc475b785091b61df0bd766631ce0a0f5cde39d11569e19c62ae812968d1da0c",
}


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser()
    parser.add_argument("--folder", required=True, type=Path)
    parser.add_argument("--model-a", required=True)
    parser.add_argument("--model-b", required=True)
    parser.add_argument("--output-stem", required=True)
    parser.add_argument(
        "--chrome-bin",
        default="/Applications/Google Chrome.app/Contents/MacOS/Google Chrome",
    )
    return parser.parse_args()


def png_dimensions(path: Path) -> tuple[int, int] | None:
    try:
        with path.open("rb") as handle:
            header = handle.read(24)
        if header[:8] != b"\x89PNG\r\n\x1a\n":
            return None
        return struct.unpack(">II", header[16:24])
    except OSError:
        return None


def stage_fonts(skill_dir: Path, folder: Path) -> None:
    """Place the brand fonts beside comparison.html.

    template.html requests them with relative url(), which resolves against the
    HTML document's own directory. Without this the @font-face silently falls
    back to a system font: the render still succeeds and data-ready="1" is still
    set, but the names are in the wrong typeface and the measured widths that
    drive the SVG header geometry are wrong by roughly 12%.
    """
    for name in FONT_FILES:
        source = skill_dir / name
        if not source.is_file():
            raise SystemExit(f"Required font is missing from the harness: {source}")
        shutil.copy2(source, folder / name)


def stage_merge_badge(skill_dir: Path, folder: Path) -> tuple[Path, Path]:
    """Validate and stage the exact exported Figma badge vectors."""
    source_dir = skill_dir / "assets" / "merge-badge"
    payloads: dict[str, bytes] = {}
    for name, expected_hash in MERGE_BADGE_FILES.items():
        source = source_dir / name
        if not source.is_file():
            raise SystemExit(f"Required MERGE badge asset is missing: {source}")
        payload = source.read_bytes()
        actual_hash = hashlib.sha256(payload).hexdigest()
        if actual_hash != expected_hash:
            raise SystemExit(
                f"MERGE badge asset no longer matches Figma node {FIGMA_NODE_ID}: "
                f"{source} has SHA-256 {actual_hash}, expected {expected_hash}"
            )
        payloads[name] = payload

    destination_dir = folder / "merge-badge"
    destination_dir.mkdir(parents=True, exist_ok=True)
    staged: dict[str, Path] = {}
    for name in MERGE_BADGE_FILES:
        destination = destination_dir / name
        destination.write_bytes(payloads[name])
        staged[name] = destination
    return staged["merge-mark.svg"], staged["merge-wordmark.svg"]


def assert_fonts_active(dom: str) -> None:
    loaded = re.search(r'data-fonts="([^"]*)"', dom)
    if loaded is None:
        raise SystemExit("Template did not report font status")
    if loaded.group(1) != "ok":
        raise SystemExit(
            "FH Oscar Pro did not load; names would render in a fallback face "
            f"and header measurements would be wrong (status: {loaded.group(1)})"
        )


def find_asset(folder: Path, stem: str, extensions: tuple[str, ...]) -> Path:
    matches = [folder / f"{stem}{extension}" for extension in extensions]
    existing = [path for path in matches if path.is_file()]
    if len(existing) != 1:
        raise SystemExit(
            f"Expected exactly one {stem} asset ({', '.join(extensions)}); found {existing}"
        )
    return existing[0]


def find_retina_shot(folder: Path, stem: str, source: tuple[int, int]) -> Path | None:
    """Return the 2x capture for a side when the harness produced a valid one.

    Without it the @2x composite upscales a 1x screenshot, so the websites are
    visibly softer than the vector headers around them.
    """
    path = folder / f"{stem}@2x.png"
    if not path.is_file():
        return None
    expected = (source[0] * 2, source[1] * 2)
    dimensions = png_dimensions(path)
    if dimensions != expected:
        raise SystemExit(
            f"{path.name} must be exactly {expected[0]}x{expected[1]}; got {dimensions}"
        )
    return path


def data_uri(path: Path) -> str:
    mime = mimetypes.guess_type(path.name)[0] or "application/octet-stream"
    payload = base64.b64encode(path.read_bytes()).decode("ascii")
    return f"data:{mime};base64,{payload}"


def run_chrome(chrome: Path, arguments: list[str], *, cwd: Path) -> subprocess.CompletedProcess[str]:
    """Run one headless Chrome invocation under a hard wall-clock cap.

    Chrome is started in its own process group so a timeout can reap the whole
    renderer/GPU tree; killing only the parent leaves children holding the pipes
    and communicate() keeps blocking.
    """
    process = subprocess.Popen(
        [str(chrome), *arguments],
        cwd=cwd,
        text=True,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        start_new_session=True,
    )
    try:
        stdout, stderr = process.communicate(timeout=CHROME_TIMEOUT_SECONDS)
    except subprocess.TimeoutExpired:
        try:
            os.killpg(process.pid, signal.SIGKILL)
        except (ProcessLookupError, PermissionError):
            process.kill()
        process.communicate()
        raise SystemExit(
            f"Chrome did not exit within {CHROME_TIMEOUT_SECONDS}s: "
            f"{' '.join(arguments)}"
        )
    if process.returncode != 0:
        raise SystemExit(
            f"Chrome exited {process.returncode}: {' '.join(arguments)}\n{stderr.strip()}"
        )
    return subprocess.CompletedProcess(
        process.args, process.returncode, stdout=stdout, stderr=stderr
    )


def measured_names(dom: str) -> tuple[tuple[float, float], tuple[float, float]]:
    """Return ((width, font_size), (width, font_size)) for the two rendered names.

    The template shrinks both names to a shared size when the widest lockup
    would overflow its column, so the SVG must mirror the measured size rather
    than assume NAME_SIZE.
    """
    matches = re.findall(
        r'class="name"[^>]*data-width="([0-9.]+)"[^>]*data-size="([0-9.]+)"', dom
    )
    if len(matches) != 2:
        raise SystemExit("Could not measure both model names in the rendered DOM")
    return (
        (float(matches[0][0]), float(matches[0][1])),
        (float(matches[1][0]), float(matches[1][1])),
    )


def header_lockup(
    model: str, logo: Path, center_x: float, name_width: float, name_size: float, suffix: str
) -> str:
    logo_box = LOGO_BOXES[suffix]
    max_width = HEADER_MAX_WIDTHS[suffix]
    group_width = logo_box + HEADER_GAP + name_width
    if group_width > max_width:
        raise SystemExit(f"Header lockup is too wide for {model}: {group_width:.1f}px")
    start_x = center_x - group_width / 2
    logo_y = (HEADER_HEIGHT - logo_box) / 2
    text_x = start_x + logo_box + HEADER_GAP
    text_y = HEADER_HEIGHT / 2 + name_size * 0.34
    return f"""
  <g id="header-{suffix}" aria-label="{html.escape(model)} header">
    <image id="logo-{suffix}" x="{start_x:.2f}" y="{logo_y:.2f}" width="{logo_box}" height="{logo_box}"
      preserveAspectRatio="xMidYMid meet" href="{data_uri(logo)}"/>
    <text id="model-{suffix}" x="{text_x:.2f}" y="{text_y:.2f}"
      font-family="FH Oscar Pro, Arial, sans-serif" font-size="{name_size:g}" font-weight="600"
      letter-spacing="{-0.02 * name_size:.2f}" fill="#000000">{html.escape(model)}</text>
  </g>"""


def merge_badge_svg(mark: Path, wordmark: Path) -> str:
    """Return the locked Figma badge as the topmost SVG group."""
    # SVG strokes straddle their path. Inset the 3px outline by 1.5px so the
    # visible bounds equal Figma's border-box dimensions.
    stroke_inset = MERGE_BADGE_BORDER / 2
    rect_width = MERGE_BADGE_WIDTH - MERGE_BADGE_BORDER
    rect_height = MERGE_BADGE_HEIGHT - MERGE_BADGE_BORDER
    centerline_radius = MERGE_BADGE_RADIUS - stroke_inset
    return f"""
  <g id="merge-badge" data-figma-file-key="{FIGMA_FILE_KEY}"
    data-figma-node-id="{FIGMA_NODE_ID}"
    transform="translate({MERGE_BADGE_X} {MERGE_BADGE_Y})">
    <rect x="{stroke_inset}" y="{stroke_inset}" width="{rect_width}" height="{rect_height}"
      rx="{centerline_radius}" fill="{MERGE_BADGE_FILL}" stroke="{MERGE_BADGE_STROKE}"
      stroke-width="{MERGE_BADGE_BORDER}"/>
    <g id="merge-lockup" transform="translate({MERGE_LOCKUP_X} {MERGE_LOCKUP_Y})">
      <image id="merge-mark" x="0" y="0" width="{MERGE_MARK_WIDTH}"
        height="{MERGE_MARK_HEIGHT}" preserveAspectRatio="none" href="{data_uri(mark)}"/>
      <image id="merge-wordmark" x="{MERGE_WORDMARK_X}" y="{MERGE_WORDMARK_Y}"
        width="{MERGE_WORDMARK_WIDTH}" height="{MERGE_WORDMARK_HEIGHT}"
        preserveAspectRatio="none" href="{data_uri(wordmark)}"/>
    </g>
  </g>"""


def write_svg(
    output: Path,
    model_a: str,
    model_b: str,
    logo_a: Path,
    logo_b: Path,
    shot_a: Path,
    shot_b: Path,
    merge_mark: Path,
    merge_wordmark: Path,
    name_metrics: tuple[tuple[float, float], tuple[float, float]],
) -> None:
    header_a = header_lockup(model_a, logo_a, 480, name_metrics[0][0], name_metrics[0][1], "a")
    header_b = header_lockup(model_b, logo_b, 1440, name_metrics[1][0], name_metrics[1][1], "b")
    svg = f"""<?xml version="1.0" encoding="UTF-8"?>
<svg xmlns="http://www.w3.org/2000/svg" xmlns:xlink="http://www.w3.org/1999/xlink"
  width="1920" height="1080" viewBox="0 0 1920 1080">
  <title>{html.escape(model_a)} vs {html.escape(model_b)} model comparison</title>
  <defs>
    <filter id="panel-shadow" x="-10%" y="-10%" width="120%" height="140%"
      color-interpolation-filters="sRGB">
      <feDropShadow dx="0" dy="12" stdDeviation="12" flood-color="#000000" flood-opacity="0.12"/>
      <feDropShadow dx="0" dy="2" stdDeviation="3" flood-color="#000000" flood-opacity="0.08"/>
    </filter>
    <clipPath id="clip-a"><rect x="{SHOT_A_X}" y="{SHOT_Y}" width="{SHOT_A_WIDTH}" height="{SHOT_HEIGHT}" rx="{SHOT_A_RADIUS}"/></clipPath>
    <clipPath id="clip-b"><rect x="{SHOT_B_X}" y="{SHOT_Y}" width="{SHOT_B_WIDTH}" height="{SHOT_HEIGHT}" rx="{SHOT_B_RADIUS}"/></clipPath>
  </defs>
  <rect id="canvas" width="1920" height="1080" fill="#FAF8F5"/>
{header_a}
{header_b}
  <g id="website-a" filter="url(#panel-shadow)">
    <g clip-path="url(#clip-a)">
      <image x="{SHOT_A_X}" y="{SHOT_Y}" width="{SHOT_A_WIDTH}" height="{SHOT_HEIGHT}"
        preserveAspectRatio="xMidYMid slice" href="{data_uri(shot_a)}"/>
    </g>
  </g>
  <g id="website-b" filter="url(#panel-shadow)">
    <g clip-path="url(#clip-b)">
      <image x="{SHOT_B_X}" y="{SHOT_Y}" width="{SHOT_B_WIDTH}" height="{SHOT_HEIGHT}"
        preserveAspectRatio="xMidYMid slice" href="{data_uri(shot_b)}"/>
    </g>
  </g>
  <rect id="column-divider" x="959" y="0" width="{DIVIDER_WIDTH}" height="1095" fill="#D9D9D9"/>
  <rect id="header-divider" x="0" y="{HEADER_HEIGHT}" width="1920" height="{DIVIDER_WIDTH}" fill="#DDDDDC"/>
  <circle id="crosshair-dot" cx="960" cy="188" r="19" fill="#FAF8F5"
    stroke="#D9D9D9" stroke-width="2"/>
{merge_badge_svg(merge_mark, merge_wordmark)}
</svg>
"""
    output.write_text(svg, encoding="utf-8")


def main() -> int:
    args = parse_args()
    folder = args.folder.expanduser().resolve()
    chrome = Path(args.chrome_bin).expanduser().resolve()
    if not chrome.is_file():
        raise SystemExit(f"Chrome executable not found: {chrome}")
    folder.mkdir(parents=True, exist_ok=True)

    skill_dir = Path(__file__).resolve().parents[1]
    stage_fonts(skill_dir, folder)
    merge_mark, merge_wordmark = stage_merge_badge(skill_dir, folder)
    template = (skill_dir / "template.html").read_text(encoding="utf-8")
    logo_a = find_asset(folder, "logo-a", (".svg", ".png"))
    logo_b = find_asset(folder, "logo-b", (".svg", ".png"))
    shot_a = find_asset(folder, "shot-a", (".png",))
    shot_b = find_asset(folder, "shot-b", (".png",))
    for shot in (shot_a, shot_b):
        if png_dimensions(shot) != (1440, 1024):
            raise SystemExit(f"{shot.name} must be exactly 1440x1024; got {png_dimensions(shot)}")
    retina_a = find_retina_shot(folder, "shot-a", (1440, 1024))
    retina_b = find_retina_shot(folder, "shot-b", (1440, 1024))

    rendered_html = template.replace("{{MODEL_A}}", html.escape(args.model_a)).replace(
        "{{MODEL_B}}", html.escape(args.model_b)
    )
    rendered_html = rendered_html.replace('data-src="logo-a.svg"', f'data-src="{logo_a.name}"')
    rendered_html = rendered_html.replace('data-src="logo-b.svg"', f'data-src="{logo_b.name}"')
    # One document serves both renders: Chrome resolves srcset against the device
    # scale factor, so the 1x pass keeps the 1x capture and the 2x pass picks the
    # 2x capture without a second template.
    for side, retina in (("a", retina_a), ("b", retina_b)):
        if retina is None:
            continue
        rendered_html = rendered_html.replace(
            f'src="shot-{side}.png"',
            f'src="shot-{side}.png" srcset="shot-{side}.png 1x, {retina.name} 2x"',
        )
    comparison_html = folder / "comparison.html"
    comparison_html.write_text(rendered_html, encoding="utf-8")

    # No --user-data-dir: a persistent profile makes headless Chrome write the
    # screenshot and then hold its singleton lock without ever exiting.
    common = [
        "--headless",
        "--disable-gpu",
        "--hide-scrollbars",
        "--allow-file-access-from-files",
        # High-resolution transparent logos require a full pixel-bounds scan
        # before the template can mark itself ready. Keep enough virtual time
        # for that deterministic normalization step on a cold Chrome start.
        "--virtual-time-budget=30000",
        "--window-size=1920,1080",
    ]
    output_png = folder / f"{args.output_stem}.png"
    output_2x = folder / f"{args.output_stem}@2x.png"
    page_url = comparison_html.as_uri()

    # Validate before rendering: a fallback typeface or a failed logo would be
    # baked into both PNGs and the SVG geometry alike.
    dom = run_chrome(chrome, [*common, "--dump-dom", page_url], cwd=folder).stdout
    warnings = re.findall(r'data-warn="([^"]+)"', dom)
    if warnings:
        raise SystemExit("Logo warnings: " + "; ".join(warnings))
    if 'data-ready="1"' not in dom:
        raise SystemExit("Template normalization did not finish")
    assert_fonts_active(dom)

    run_chrome(chrome, [*common, f"--screenshot={output_png}", page_url], cwd=folder)
    run_chrome(
        chrome,
        [*common, "--force-device-scale-factor=2", f"--screenshot={output_2x}", page_url],
        cwd=folder,
    )

    output_svg = folder / f"{args.output_stem}.svg"
    write_svg(
        output_svg,
        args.model_a,
        args.model_b,
        logo_a,
        logo_b,
        retina_a or shot_a,
        retina_b or shot_b,
        merge_mark,
        merge_wordmark,
        measured_names(dom),
    )
    result = {
        "png": str(output_png),
        "png_dimensions": png_dimensions(output_png),
        "png_2x": str(output_2x),
        "png_2x_dimensions": png_dimensions(output_2x),
        "figma_svg": str(output_svg),
        "figma_layout_node_id": FIGMA_LAYOUT_NODE_ID,
        "source_viewport": {"width": 1440, "height": 1024},
        "embedded_capture_scale": {
            "a": 2 if retina_a else 1,
            "b": 2 if retina_b else 1,
        },
        "logo_warnings": warnings,
        "panel_shadow": PANEL_SHADOW,
        "merge_badge": {
            "figma_file_key": FIGMA_FILE_KEY,
            "figma_node_id": FIGMA_NODE_ID,
            "bounds": {
                "x": MERGE_BADGE_X,
                "y": MERGE_BADGE_Y,
                "width": MERGE_BADGE_WIDTH,
                "height": MERGE_BADGE_HEIGHT,
            },
            "asset_sha256": MERGE_BADGE_FILES,
        },
    }
    (folder / "render-result.json").write_text(
        json.dumps(result, indent=2) + "\n", encoding="utf-8"
    )
    print(json.dumps(result, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
