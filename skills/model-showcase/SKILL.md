---
name: model-showcase
description: Build a polished side-by-side image and video showcase for two Merge Gateway models by running the same browser-demo brief through Pi, repairing visible presentation failures, recording both live demos with FFmpeg, and rendering social-ready assets. Use for model-versus-model coding demos, visual capability posts, and animated comparisons; do not present the result as an untouched one-shot benchmark.
---

# Build a model showcase

Create a social-ready two-model browser demo through Pi and Merge Gateway. Optimize for a clear,
fun result while preserving a useful audit trail.

## Set the contract

- Give both models the same initial brief and isolated Pi configuration.
- Put model A on the left and model B on the right.
- Use plain model names. Never append `fixed`, `repaired`, or similar claims.
- Treat the result as a capabilities showcase, not a scientific one-shot benchmark.
- Keep generated sites, logs, captures, videos, and music outside the `md` repository. Default to
  `/Users/mattferoz/model-comparison-artifacts/<run-name>/` unless the user chooses another folder.
- Preserve every model version and log every repair.
- Record live Chrome windows with FFmpeg. Never synthesize motion from screenshots or frame dumps.

Collect only missing model slugs, display names, the shared brief, and optional local audio. Do not
ask follow-up questions when the user already supplied them.

## Prepare

Set `<skill-dir>` to this skill directory and `<run>` to the artifact folder. Require:

```sh
command -v pi
command -v ffmpeg
command -v ffprobe
command -v bun
test -x "/Applications/Google Chrome.app/Contents/MacOS/Google Chrome"
test -n "$MERGE_GATEWAY_API_KEY"
```

Create `<run>/site-a`, `<run>/site-b`, and `<run>/build-prompt.txt`. Stage bundled provider logos:

```sh
python3 "<skill-dir>/scripts/stage_provider_logos.py" \
  --model-a "<gateway-slug-a>" --model-b "<gateway-slug-b>" --folder "<run>"
```

The runners create workspace-local Pi settings containing an environment-variable reference, not
the Gateway key. Set `MERGE_GATEWAY_BASE_URL` only for a non-default Merge Gateway endpoint.

## Precheck both models

Before generation, run the small Pi write-tool probe for each exact model. This verifies the agentic
tool path rather than only testing text completion, and does not count against the repair limit.
Run the probes concurrently:

```sh
python3 "<skill-dir>/scripts/run_showcase.py" precheck \
  --model "<gateway-slug-a>" --label "<display-name-a>" \
  --workspace "<run>/precheck-a"

python3 "<skill-dir>/scripts/run_showcase.py" precheck \
  --model "<gateway-slug-b>" --label "<display-name-b>" \
  --workspace "<run>/precheck-b"
```

Require both `precheck-result.json` files to report `tool_path_verified: true`. If a model needs a
verified vendor option, pass the same `--sampling-params-json` to its precheck and initial run. For
example, use this only if the exact Qwen model passes with it:

```sh
--sampling-params-json '{"provider_options":{"qwen":{"thinking":{"type":"disabled"}}}}'
```

Stop and report the exact provider error when a precheck fails. Do not spend a full generation on
an unhealthy or tool-incompatible model.

## Generate both demos

Start the two model runs concurrently:

```sh
python3 "<skill-dir>/scripts/run_showcase.py" start \
  --model "<gateway-slug-a>" --label "<display-name-a>" \
  --workspace "<run>/site-a" --prompt-file "<run>/build-prompt.txt"

python3 "<skill-dir>/scripts/run_showcase.py" start \
  --model "<gateway-slug-b>" --label "<display-name-b>" \
  --workspace "<run>/site-b" --prompt-file "<run>/build-prompt.txt"
```

Use `--exact-prompt` when the user's prompt contains a complete execution contract or requires a
framework, dependency, or network policy that conflicts with the appended compact build contract.

Each workspace receives an isolated Pi session and archives its initial `index.html` under
`versions/00-initial/`.

## Reach publishability

Open each demo, exercise its main interaction, and inspect the beginning, middle, and end of a
recording. A side passes when:

- the page loads without a visible error;
- the requested technology is genuinely used;
- the main subject remains visible and motion continues through the clip;
- the camera is stable and follows the intended subject;
- important objects are not upside down, floating, frozen, or detached;
- important text and controls fit inside the panel;
- the recording has no blank or frozen section.

If a side fails, write only its observed failures to a repair prompt and continue the same Pi
session:

```sh
python3 "<skill-dir>/scripts/run_showcase.py" repair \
  --workspace "<run>/site-a" --prompt-file "<run>/repair-a-1.txt"
```

Reinspect after every repair and stop as soon as the checklist passes. Allow at most three repair
prompts per model. The runner enforces the limit, archives each result, and writes
`repair-log.json`.

After all three model repairs are used, make a targeted local edit only when a checklist failure
still blocks publication. Preserve and log the exact scope before editing:

```sh
python3 "<skill-dir>/scripts/log_local_fix.py" begin \
  --workspace "<run>/site-a" \
  --reason "<visible problem>" --check "<failed checklist item>"

# Edit only the files needed for that failure, then verify the demo.

python3 "<skill-dir>/scripts/log_local_fix.py" finish \
  --workspace "<run>/site-a" --changed-file "index.html"
```

Do not expand the concept during repair. Prefer stable scripted motion over physics, collision, or
AI systems when the clip only needs to demonstrate the visual idea.

## Capture and render

Capture 1440x1024 screenshots and 2880x2048 2x screenshots with Chrome after both sides pass.
Render the locked social image:

```sh
python3 "<skill-dir>/scripts/render_showcase.py" \
  --folder "<run>" --model-a "<display-name-a>" --model-b "<display-name-b>" \
  --output-stem "<model-a>-vs-<model-b>-showcase"
```

For video, list AVFoundation devices with
`ffmpeg -hide_banner -f avfoundation -list_devices true -i ""`, choose a dedicated display, then
record each live demo:

```sh
bun run "<skill-dir>/scripts/record_site.mjs" \
  --url "file://<run>/site-a/index.html" --output "<run>/<model-a>-raw.mp4" \
  --screen-device "<device>" --display-left "<x>" --display-top "<y>" --webgl

bun run "<skill-dir>/scripts/record_site.mjs" \
  --url "file://<run>/site-b/index.html" --output "<run>/<model-b>-raw.mp4" \
  --screen-device "<device>" --display-left "<x>" --display-top "<y>" --webgl
```

Add `--drive-demo` only when both pages expose compatible keyboard driving controls. Require both
recording audits to report FFmpeg as the real-time capture source, a continuous page session,
60 fps, at least two unique motion samples, completed scroll traces, and non-empty actions.

Composite the raw recordings into the locked frame:

```sh
python3 "<skill-dir>/scripts/render_video.py" \
  --comparison "<run>/<showcase-stem>.png" \
  --video-a "<run>/<model-a>-raw.mp4" --video-b "<run>/<model-b>-raw.mp4" \
  --output "<run>/<showcase-stem>-silent.mp4"
```

When the user provides local music, copy it into the run archive and add it to the silent master:

```sh
python3 "<skill-dir>/scripts/add_music.py" \
  --video "<run>/<showcase-stem>-silent.mp4" --audio "<run>/<audio-file>" \
  --output "<run>/<showcase-stem>.mp4"
```

The default mix is `-14dB` with 0.5-second fade-in, 0.8-second fade-out, and AAC 192 kbps. Adjust
the level when the user asks. For this internal workflow, do not add a licensing or copyright gate.

## Deliver

Publish the 1920x1080 PNG and final 1920x1080 H.264 MP4. Keep the 2x PNG, SVG, silent master,
sites, Pi sessions, prompts, logs, screenshots, raw recordings, audio source, and audits in the run
archive. Verify the final video with `ffprobe` and visually inspect frames near the start, middle,
and end before handing it off.

## Resources

- `scripts/run_showcase.py`: precheck, initial Pi session, and bounded same-session repairs
- `scripts/log_local_fix.py`: preserve and audit checklist-scoped local edits
- `scripts/stage_provider_logos.py`: stage bundled provider symbols
- `scripts/render_showcase.py`: render locked PNG, 2x PNG, and SVG assets
- `scripts/record_site.mjs`: record a live Chrome page directly through FFmpeg
- `scripts/render_video.py`: composite both recordings into the locked frame
- `scripts/add_music.py`: add optional local music to the silent master
