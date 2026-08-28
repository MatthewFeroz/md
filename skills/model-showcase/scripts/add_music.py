#!/usr/bin/env python3
"""Add a low background-music bed to a finished showcase video."""

from __future__ import annotations

import argparse
import json
import math
import shutil
import subprocess
from pathlib import Path


DEFAULT_VOLUME_DB = -14.0
DEFAULT_FADE_IN = 0.5
DEFAULT_FADE_OUT = 0.8


def executable(name: str) -> str:
    value = shutil.which(name)
    if value:
        return value
    raise SystemExit(f"Executable not found: {name}")


def probe(ffprobe: str, path: Path) -> dict[str, object]:
    result = subprocess.run(
        [
            ffprobe,
            "-v",
            "error",
            "-show_streams",
            "-show_format",
            "-of",
            "json",
            str(path),
        ],
        text=True,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        check=False,
    )
    if result.returncode != 0:
        raise SystemExit(f"Could not inspect {path}: {result.stderr.strip()}")
    return json.loads(result.stdout)


def duration(payload: dict[str, object], path: Path) -> float:
    details = payload.get("format")
    raw = details.get("duration") if isinstance(details, dict) else None
    try:
        value = float(raw)
    except (TypeError, ValueError):
        raise SystemExit(f"Could not determine duration for {path}") from None
    if not math.isfinite(value) or value <= 0:
        raise SystemExit(f"Duration must be positive for {path}")
    return value


def has_audio(payload: dict[str, object]) -> bool:
    streams = payload.get("streams")
    return isinstance(streams, list) and any(
        isinstance(stream, dict) and stream.get("codec_type") == "audio"
        for stream in streams
    )


def build_command(
    ffmpeg: str,
    video: Path,
    audio: Path,
    output: Path,
    *,
    video_duration: float,
    volume_db: float = DEFAULT_VOLUME_DB,
    fade_in: float = DEFAULT_FADE_IN,
    fade_out: float = DEFAULT_FADE_OUT,
) -> list[str]:
    fade_out_start = max(0.0, video_duration - fade_out - 0.08)
    audio_filter = (
        f"volume={volume_db:g}dB,"
        f"afade=t=in:st=0:d={fade_in:g},"
        f"afade=t=out:st={fade_out_start:.3f}:d={fade_out:g}"
    )
    return [
        ffmpeg,
        "-y",
        "-i",
        str(video),
        "-stream_loop",
        "-1",
        "-i",
        str(audio),
        "-filter_complex",
        f"[1:a:0]{audio_filter}[music]",
        "-map",
        "0:v:0",
        "-map",
        "[music]",
        "-t",
        f"{video_duration:.3f}",
        "-c:v",
        "copy",
        "-c:a",
        "aac",
        "-b:a",
        "192k",
        "-shortest",
        "-movflags",
        "+faststart",
        str(output),
    ]


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--video", required=True, type=Path)
    parser.add_argument("--audio", required=True, type=Path)
    parser.add_argument("--output", required=True, type=Path)
    parser.add_argument("--volume-db", type=float, default=DEFAULT_VOLUME_DB)
    parser.add_argument("--fade-in", type=float, default=DEFAULT_FADE_IN)
    parser.add_argument("--fade-out", type=float, default=DEFAULT_FADE_OUT)
    parser.add_argument("--ffmpeg-bin", default="ffmpeg")
    parser.add_argument("--ffprobe-bin", default="ffprobe")
    args = parser.parse_args()

    video = args.video.expanduser().resolve()
    audio = args.audio.expanduser().resolve()
    output = args.output.expanduser().resolve()
    for label, path in (("Video", video), ("Audio", audio)):
        if not path.is_file():
            raise SystemExit(f"{label} does not exist: {path}")
    if output in {video, audio}:
        raise SystemExit("Output must differ from both inputs")
    if args.fade_in < 0 or args.fade_out < 0:
        raise SystemExit("Fade durations cannot be negative")

    ffprobe = executable(args.ffprobe_bin)
    video_probe = probe(ffprobe, video)
    if has_audio(video_probe):
        raise SystemExit(
            "Input video already has audio; use the silent showcase master to avoid replacing it"
        )
    video_duration = duration(video_probe, video)
    if args.fade_in + args.fade_out > video_duration:
        raise SystemExit("Combined fades exceed the video duration")
    output.parent.mkdir(parents=True, exist_ok=True)
    command = build_command(
        executable(args.ffmpeg_bin),
        video,
        audio,
        output,
        video_duration=video_duration,
        volume_db=args.volume_db,
        fade_in=args.fade_in,
        fade_out=args.fade_out,
    )
    completed = subprocess.run(command, text=True, check=False)
    if completed.returncode != 0:
        raise SystemExit(f"FFmpeg exited with status {completed.returncode}")
    result = {
        "video": str(video),
        "audio": str(audio),
        "output": str(output),
        "volume_db": args.volume_db,
        "fade_in_seconds": args.fade_in,
        "fade_out_seconds": args.fade_out,
        "duration_seconds": video_duration,
    }
    output.with_suffix(".music-result.json").write_text(
        json.dumps(result, indent=2) + "\n", encoding="utf-8"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
