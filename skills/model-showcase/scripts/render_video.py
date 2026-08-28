#!/usr/bin/env python3
"""Render two model recordings inside the locked comparison frame."""

from __future__ import annotations

import argparse
import json
import math
import shutil
import subprocess
import tempfile
from pathlib import Path

from render_showcase import (
    CANVAS,
    FIGMA_FILE_KEY,
    FIGMA_LAYOUT_NODE_ID,
    FIGMA_NODE_ID,
    MERGE_BADGE_FILES,
    MERGE_BADGE_HEIGHT,
    MERGE_BADGE_WIDTH,
    MERGE_BADGE_X,
    MERGE_BADGE_Y,
    SHOT_A_RADIUS,
    SHOT_A_WIDTH,
    SHOT_A_X,
    SHOT_B_RADIUS,
    SHOT_B_WIDTH,
    SHOT_B_X,
    SHOT_HEIGHT,
    SHOT_Y,
    png_dimensions,
)


DEFAULT_CHROME = "/Applications/Google Chrome.app/Contents/MacOS/Google Chrome"
DEFAULT_FPS = 60


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description=(
            "Render the sole publishable MP4: model A moving in the left panel "
            "and model B moving in the right panel of the locked comparison frame."
        )
    )
    parser.add_argument(
        "--comparison",
        required=True,
        type=Path,
        help="1920x1080 comparison PNG produced by render_showcase.py",
    )
    parser.add_argument("--video-a", required=True, type=Path, help="Raw model A MP4")
    parser.add_argument("--video-b", required=True, type=Path, help="Raw model B MP4")
    parser.add_argument(
        "--output", required=True, type=Path, help="Final two-model comparison MP4"
    )
    parser.add_argument("--result", type=Path, help="Audit JSON output path")
    parser.add_argument(
        "--duration",
        type=float,
        help="Seconds to render; defaults to the shorter source duration",
    )
    parser.add_argument("--chrome-bin", default=DEFAULT_CHROME)
    parser.add_argument("--ffmpeg-bin", default="ffmpeg")
    parser.add_argument("--ffprobe-bin", default="ffprobe")
    parser.add_argument("--fps", type=int, default=DEFAULT_FPS)
    parser.add_argument("--preset", default="medium")
    parser.add_argument("--crf", type=int, default=18)
    return parser.parse_args()


def executable(value: str) -> str:
    path = Path(value).expanduser()
    if path.is_file():
        return str(path.resolve())
    resolved = shutil.which(value)
    if resolved:
        return resolved
    raise SystemExit(f"Executable not found: {value}")


def run_checked(
    command: list[str], *, cwd: Path | None = None
) -> subprocess.CompletedProcess[str]:
    result = subprocess.run(
        command,
        cwd=cwd,
        text=True,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        check=False,
    )
    if result.returncode != 0:
        raise SystemExit(
            f"Command exited {result.returncode}: {' '.join(command)}\n"
            f"{result.stderr.strip()}"
        )
    return result


def probe_video(ffprobe: str, path: Path) -> dict[str, object]:
    result = run_checked(
        [
            ffprobe,
            "-v",
            "error",
            "-select_streams",
            "v:0",
            "-show_entries",
            "stream=codec_name,width,height,pix_fmt,r_frame_rate,nb_frames:format=duration",
            "-of",
            "json",
            str(path),
        ]
    )
    payload = json.loads(result.stdout)
    streams = payload.get("streams", [])
    if len(streams) != 1:
        raise SystemExit(f"Expected one primary video stream in {path}")
    stream = streams[0]
    width = stream.get("width")
    height = stream.get("height")
    if (
        not isinstance(width, int)
        or not isinstance(height, int)
        or width <= 0
        or height <= 0
    ):
        raise SystemExit(f"Could not determine video dimensions for {path}")
    video_duration(payload, path)
    return payload


def video_duration(probe: dict[str, object], path: Path | str) -> float:
    details = probe.get("format")
    raw_duration = details.get("duration") if isinstance(details, dict) else None
    try:
        duration = float(raw_duration)
    except (TypeError, ValueError):
        raise SystemExit(f"Could not determine video duration for {path}") from None
    if not math.isfinite(duration) or duration <= 0:
        raise SystemExit(f"Video duration must be positive for {path}")
    return duration


def comparison_duration(
    probe_a: dict[str, object],
    probe_b: dict[str, object],
    requested: float | None,
) -> float:
    available = min(
        video_duration(probe_a, "model A"), video_duration(probe_b, "model B")
    )
    if requested is None:
        return available
    if not math.isfinite(requested) or requested <= 0:
        raise SystemExit("Duration must be a positive finite number")
    if requested > available + 0.001:
        raise SystemExit(
            f"Requested duration {requested:g}s exceeds the shorter source "
            f"({available:g}s); both comparison panels must remain moving"
        )
    return requested


def panel_layouts() -> dict[str, dict[str, float | int]]:
    """Return the Figma geometry and its integer video-compositing bounds."""
    return {
        "a": {
            "x": round(SHOT_A_X),
            "y": round(SHOT_Y),
            "width": round(SHOT_A_WIDTH),
            "height": round(SHOT_HEIGHT),
            "radius": SHOT_A_RADIUS,
            "figma_x": SHOT_A_X,
            "figma_width": SHOT_A_WIDTH,
        },
        "b": {
            "x": round(SHOT_B_X),
            "y": round(SHOT_Y),
            "width": round(SHOT_B_WIDTH),
            "height": round(SHOT_HEIGHT),
            "radius": SHOT_B_RADIUS,
            "figma_x": SHOT_B_X,
            "figma_width": SHOT_B_WIDTH,
        },
    }


def panel_mask_html(width: int, height: int, radius: float) -> str:
    return f"""<!doctype html>
<html>
<head>
<meta charset="utf-8">
<style>
  * {{ box-sizing: border-box; margin: 0; padding: 0; }}
  html, body {{
    width: {width}px; height: {height}px; overflow: hidden; background: transparent;
  }}
  .mask {{
    width: {width}px; height: {height}px; border-radius: {radius}px; background: #fff;
  }}
</style>
</head>
<body><div class="mask"></div></body>
</html>
"""


def render_panel_mask(
    chrome: str,
    folder: Path,
    side: str,
    layout: dict[str, float | int],
) -> Path:
    width = int(layout["width"])
    height = int(layout["height"])
    html_path = folder / f"panel-{side}-mask.html"
    png_path = folder / f"panel-{side}-mask.png"
    html_path.write_text(
        panel_mask_html(width, height, float(layout["radius"])), encoding="utf-8"
    )
    run_checked(
        [
            chrome,
            "--headless",
            "--disable-gpu",
            "--hide-scrollbars",
            "--allow-file-access-from-files",
            "--default-background-color=00000000",
            "--force-device-scale-factor=1",
            f"--window-size={width},{height}",
            f"--screenshot={png_path}",
            html_path.as_uri(),
        ],
        cwd=folder,
    )
    dimensions = png_dimensions(png_path)
    if dimensions != (width, height):
        raise SystemExit(
            f"Panel {side} mask must be {width}x{height}; Chrome rendered {dimensions}"
        )
    return png_path


def validate_comparison(comparison: Path) -> dict[str, object]:
    dimensions = png_dimensions(comparison)
    if dimensions != CANVAS:
        raise SystemExit(
            f"Comparison background must be {CANVAS[0]}x{CANVAS[1]}; got {dimensions}"
        )

    audit_path = comparison.parent / "render-result.json"
    if not audit_path.is_file():
        raise SystemExit(
            f"Comparison audit not found: {audit_path}; render the frame with "
            "render_showcase.py first"
        )
    try:
        audit = json.loads(audit_path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as error:
        raise SystemExit(
            f"Could not read comparison audit {audit_path}: {error}"
        ) from None

    badge = audit.get("merge_badge")
    expected = {
        "figma_file_key": FIGMA_FILE_KEY,
        "figma_node_id": FIGMA_NODE_ID,
        "asset_sha256": MERGE_BADGE_FILES,
    }
    if audit.get("figma_layout_node_id") != FIGMA_LAYOUT_NODE_ID:
        raise SystemExit(
            "Comparison was not rendered from the locked full-frame Figma node"
        )
    if not isinstance(badge, dict) or any(
        badge.get(key) != value for key, value in expected.items()
    ):
        raise SystemExit("Comparison does not contain the hash-locked MERGE badge")
    if Path(str(audit.get("png", ""))).name != comparison.name:
        raise SystemExit("Comparison PNG does not match its render-result.json audit")
    return audit


def build_ffmpeg_command(
    ffmpeg: str,
    comparison: Path,
    video_a: Path,
    video_b: Path,
    mask_a: Path,
    mask_b: Path,
    output: Path,
    *,
    duration: float,
    preset: str,
    crf: int,
    fps: int = DEFAULT_FPS,
) -> list[str]:
    panels = panel_layouts()
    a = panels["a"]
    b = panels["b"]
    filter_graph = ";".join(
        [
            f"[0:v:0]fps={fps},format=rgba[base]",
            (
                f"[1:v:0]setpts=PTS-STARTPTS,fps={fps},"
                f"scale={a['width']}:{a['height']}:force_original_aspect_ratio=increase:flags=lanczos,"
                f"crop={a['width']}:{a['height']},setsar=1,format=rgba[a]"
            ),
            f"[3:v:0]fps={fps},format=rgba,alphaextract[mask-a]",
            "[a][mask-a]alphamerge[a-rounded]",
            (
                f"[2:v:0]setpts=PTS-STARTPTS,fps={fps},"
                f"scale={b['width']}:{b['height']}:force_original_aspect_ratio=increase:flags=lanczos,"
                f"crop={b['width']}:{b['height']},setsar=1,format=rgba[b]"
            ),
            f"[4:v:0]fps={fps},format=rgba,alphaextract[mask-b]",
            "[b][mask-b]alphamerge[b-rounded]",
            (
                f"[base][a-rounded]overlay={a['x']}:{a['y']}:"
                "format=auto:eof_action=pass[with-a]"
            ),
            (
                f"[with-a][b-rounded]overlay={b['x']}:{b['y']}:"
                "format=auto:eof_action=pass,format=yuv420p[v]"
            ),
        ]
    )
    return [
        ffmpeg,
        "-y",
        "-loop",
        "1",
        "-framerate",
        str(fps),
        "-i",
        str(comparison),
        "-i",
        str(video_a),
        "-i",
        str(video_b),
        "-loop",
        "1",
        "-framerate",
        str(fps),
        "-i",
        str(mask_a),
        "-loop",
        "1",
        "-framerate",
        str(fps),
        "-i",
        str(mask_b),
        "-filter_complex",
        filter_graph,
        "-map",
        "[v]",
        "-an",
        "-t",
        f"{duration:.6f}",
        "-r",
        str(fps),
        "-c:v",
        "libx264",
        "-preset",
        preset,
        "-crf",
        str(crf),
        "-pix_fmt",
        "yuv420p",
        "-movflags",
        "+faststart",
        str(output),
    ]


def main() -> int:
    args = parse_args()
    comparison = args.comparison.expanduser().resolve()
    video_a = args.video_a.expanduser().resolve()
    video_b = args.video_b.expanduser().resolve()
    output = args.output.expanduser().resolve()
    result_path = (
        args.result.expanduser().resolve()
        if args.result
        else output.with_suffix(".render-result.json")
    )

    inputs = {"comparison": comparison, "video A": video_a, "video B": video_b}
    for label, path in inputs.items():
        if not path.is_file():
            raise SystemExit(f"{label.capitalize()} not found: {path}")
    if output in inputs.values():
        raise SystemExit("Output must differ from the comparison and both raw videos")
    if video_a == video_b:
        raise SystemExit("Model A and model B must use distinct raw video files")
    if args.crf < 0 or args.crf > 51:
        raise SystemExit("CRF must be between 0 and 51")
    if args.fps <= 0:
        raise SystemExit("FPS must be positive")

    comparison_audit = validate_comparison(comparison)
    chrome = executable(args.chrome_bin)
    ffmpeg = executable(args.ffmpeg_bin)
    ffprobe = executable(args.ffprobe_bin)
    probe_a = probe_video(ffprobe, video_a)
    probe_b = probe_video(ffprobe, video_b)
    duration = comparison_duration(probe_a, probe_b, args.duration)

    output.parent.mkdir(parents=True, exist_ok=True)
    result_path.parent.mkdir(parents=True, exist_ok=True)
    panels = panel_layouts()
    with tempfile.TemporaryDirectory(prefix="merge-comparison-video-") as temp:
        temp_dir = Path(temp)
        mask_a = render_panel_mask(chrome, temp_dir, "a", panels["a"])
        mask_b = render_panel_mask(chrome, temp_dir, "b", panels["b"])
        run_checked(
            build_ffmpeg_command(
                ffmpeg,
                comparison,
                video_a,
                video_b,
                mask_a,
                mask_b,
                output,
                duration=duration,
                preset=args.preset,
                crf=args.crf,
                fps=args.fps,
            )
        )

    output_probe = probe_video(ffprobe, output)
    output_stream = output_probe["streams"][0]
    if (output_stream.get("width"), output_stream.get("height")) != CANVAS:
        raise SystemExit("Comparison video must remain exactly 1920x1080")

    result = {
        "comparison_video": True,
        "publishable_asset": True,
        "output": str(output),
        "comparison": {
            "path": str(comparison),
            "figma_layout_node_id": comparison_audit["figma_layout_node_id"],
        },
        "sources": {
            "a": {"path": str(video_a), "role": "intermediate", "video": probe_a},
            "b": {"path": str(video_b), "role": "intermediate", "video": probe_b},
        },
        "canvas": {"width": CANVAS[0], "height": CANVAS[1]},
        "panels": panels,
        "duration_seconds": duration,
        "fps": args.fps,
        "video": output_probe,
        "merge_badge": {
            "enabled_by_default": True,
            "inherited_from_comparison": True,
            "figma_file_key": FIGMA_FILE_KEY,
            "figma_layout_node_id": FIGMA_LAYOUT_NODE_ID,
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
    result_path.write_text(json.dumps(result, indent=2) + "\n", encoding="utf-8")
    print(json.dumps(result, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
