---
name: create-model-comparison-image
description: Compare two Merge Gateway models by giving each the same website brief in one fresh Pi run, then create a locked 1920x1080 Twitter/X comparison image and an optional animated two-panel MP4. Use for model-vs-model website bake-offs and social comparison posts.
---

# Create a model comparison

Run the content comparison directly through Pi.

## Contract

- Give both models the same brief and the same isolated Pi settings.
- Invoke Pi once per model in a fresh workspace. Use no retry, follow-up, repair, or continued
  session.
- Preserve each model's `index.html` as written. A broken result is a failed side, not permission
  to ask the model again.
- Capture both sites only after Pi exits. Rendering and recording must not call a model.
- Render the still with the locked 1920x1080 Figma geometry in `template.html`.
- When motion is requested, let FFmpeg record each live Chrome session directly.
- The only publishable video is the combined comparison MP4. Keep the two raw site recordings
  as audit artifacts.

## Inputs

Collect only missing values:

1. Two display names and exact Merge Gateway slugs such as `xai/grok-4.6`.
2. One shared website brief.
3. A new output folder.
4. Optional custom symbol logos. Otherwise derive each provider from its model slug.

Model A appears on the left. Model B appears on the right.

## Prepare

Set `<skill-dir>` to this skill directory. Require Pi, Chrome, FFmpeg, and a Gateway key:

```sh
command -v pi
pi --version
command -v ffmpeg
command -v ffprobe
test -x "/Applications/Google Chrome.app/Contents/MacOS/Google Chrome"
test -n "$MERGE_GATEWAY_API_KEY"
```

`scripts/run_once.py` creates an isolated Pi configuration inside each model workspace. It does
not modify the user's global Pi settings and stores only the environment-variable reference, not
the API key. Set `MERGE_GATEWAY_BASE_URL` only when using a non-default Gateway URL.

Before a full build, send a bounded tool-call probe through the same Gateway endpoint and model.
Apply any verified vendor controls with `--sampling-params-json`. For example, Qwen models that
default to thinking mode may require:

```sh
--sampling-params-json '{"provider_options":{"qwen":{"thinking":{"type":"disabled"}}}}'
```

Use only controls that the exact model passes in the probe. A plain text health check does not
verify Pi's tool path.

Create a new output folder with `site-a/` and `site-b/`. Save the shared brief once as
`build-prompt.txt`. Unless the user supplies custom logos, stage both provider symbols:

```sh
python3 "<skill-dir>/scripts/stage_provider_logos.py" \
  --model-a "<gateway-slug-a>" \
  --model-b "<gateway-slug-b>" \
  --folder "<output-folder>"
```

This writes `logo-a.svg` and `logo-b.svg`. It refuses unknown providers, incomplete bundled
assets, and existing targets.

## Run both models

Launch these two commands concurrently. Each command sends one prompt to one fresh Pi process:

```sh
python3 "<skill-dir>/scripts/run_once.py" \
  --model "<gateway-slug-a>" \
  --label "<display-name-a>" \
  --workspace "<output-folder>/site-a" \
  --prompt-file "<output-folder>/build-prompt.txt"

python3 "<skill-dir>/scripts/run_once.py" \
  --model "<gateway-slug-b>" \
  --label "<display-name-b>" \
  --workspace "<output-folder>/site-b" \
  --prompt-file "<output-folder>/build-prompt.txt"
```

Require both `run-result.json` files to contain:

```json
{
  "prompt_count": 1,
  "pi_run_count": 1,
  "fresh_session": true,
  "retry_count": 0,
  "repair_count": 0,
  "status": "complete"
}
```

Do not continue when either side fails.

## Capture the stills

Capture each completed site at 1440x1024 and at 2x with headless Chrome. Write:

- `shot-a.png` and `shot-b.png` at 1440x1024
- `shot-a@2x.png` and `shot-b@2x.png` at 2880x2048

Use `--headless`, `--disable-gpu`, `--hide-scrollbars`, `--allow-file-access-from-files`,
`--window-size=1440,1024`, and a short virtual-time budget. Add
`--force-device-scale-factor=2` only for the 2x captures. Keep both websites unchanged after
capture.

## Render the Twitter image

```sh
python3 "<skill-dir>/scripts/render_comparison.py" \
  --folder "<output-folder>" \
  --model-a "<display-name-a>" \
  --model-b "<display-name-b>" \
  --output-stem "<model-a-slug>-vs-<model-b-slug>-comparison"
```

Require:

- a 1920x1080 PNG for Twitter/X;
- a 3840x2160 PNG;
- an editable SVG;
- the exact Merge badge and locked panel geometry;
- unchanged website captures inside both panels.

Inspect the combined PNG for clipping, blank panels, incorrect names, broken logos, or displaced
badge geometry. Do not alter either model's website to improve the comparison.

## Render the comparison video

When motion is requested, record each site in one continuous live Chrome session. Use FFmpeg's
native screen-capture input as the recorder; do not build a video from screenshots or buffered
browser images. On macOS, list AVFoundation devices and select a dedicated display:

```sh
ffmpeg -hide_banner -f avfoundation -list_devices true -i ""
```

Position Chrome on that display and pass its AVFoundation device and global top-left coordinates:

```sh
node "<skill-dir>/scripts/record_site.mjs" \
  --url "file://<output-folder>/site-a/index.html" \
  --output "<output-folder>/<model-a-stem>-raw.mp4" \
  --screen-device "<avfoundation-device>" \
  --display-left "<global-x>" \
  --display-top "<global-y>"

node "<skill-dir>/scripts/record_site.mjs" \
  --url "file://<output-folder>/site-b/index.html" \
  --output "<output-folder>/<model-b-stem>-raw.mp4" \
  --screen-device "<avfoundation-device>" \
  --display-left "<global-x>" \
  --display-top "<global-y>"
```

Require both recording audits to report FFmpeg as the real-time capture source, one continuous
page session, 60 fps, at least two unique motion samples, completed scroll traces, and a non-empty
action list. The raw recordings are internal inputs.

Render the publishable two-panel video over the locked comparison image:

```sh
python3 "<skill-dir>/scripts/render_video.py" \
  --comparison "<output-folder>/<comparison-stem>.png" \
  --video-a "<output-folder>/<model-a-stem>-raw.mp4" \
  --video-b "<output-folder>/<model-b-stem>-raw.mp4" \
  --output "<output-folder>/<comparison-stem>.mp4"
```

Require a silent 1920x1080 H.264 MP4 at 60 fps. Verify dimensions with `ffprobe` and inspect
frames near the start, middle, and end. Both panels must move while the names, divider, ring, and
Merge badge stay fixed.

## Deliver

Publish only:

- the 1920x1080 comparison PNG;
- the 1920x1080 comparison MP4 when requested.

Keep the 2x PNG and SVG as source assets. Retain both sites, Pi event logs, run audits,
screenshots, raw recordings, and render audits in the output folder for provenance.

## Resources

- `scripts/run_once.py`: one prompt, one fresh Pi run, isolated Merge Gateway config
- `scripts/stage_provider_logos.py`: validate and stage provider symbols
- `scripts/render_comparison.py`: render the locked PNG, 2x PNG, and SVG
- `scripts/record_site.mjs`: record each live Chrome session directly with FFmpeg
- `scripts/render_video.py`: composite both recordings into the locked comparison frame
- `template.html`: locked 1920x1080 comparison layout
- `assets/provider-logos/`: provider symbol catalog and manifest
- `assets/merge-badge/`: locked Merge mark and wordmark
- `FHOscarPro-SemiBold.otf`, `FHOscarPro-Light.otf`: comparison typography
