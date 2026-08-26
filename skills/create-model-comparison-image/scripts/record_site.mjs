#!/usr/bin/env node

import { once } from "node:events";
import {
  existsSync,
  mkdtempSync,
  rmSync,
  writeFileSync,
} from "node:fs";
import { tmpdir } from "node:os";
import { extname, join, parse, resolve } from "node:path";
import { pathToFileURL } from "node:url";
import { spawn, spawnSync } from "node:child_process";

const DEFAULT_CHROME = "/Applications/Google Chrome.app/Contents/MacOS/Google Chrome";
const DEFAULT_DURATION = 14;
const DEFAULT_FPS = 60;
const DEFAULT_WIDTH = 1440;
const DEFAULT_HEIGHT = 1024;

const sleep = (milliseconds) =>
  new Promise((resolvePromise) => setTimeout(resolvePromise, milliseconds));

function usage() {
  return `Usage: node record_site.mjs --url <url> --output <video.mp4> [options]

Record one continuous live Chrome page session with FFmpeg's native screen capture.

Options:
  --duration <seconds>   Recording duration (default: ${DEFAULT_DURATION})
  --fps <frames>         Output frame rate (default: ${DEFAULT_FPS})
  --width <pixels>       Browser viewport width (default: ${DEFAULT_WIDTH})
  --height <pixels>      Browser viewport height (default: ${DEFAULT_HEIGHT})
  --chrome-bin <path>    Chrome executable
  --ffmpeg-bin <path>    FFmpeg executable or command (default: ffmpeg)
  --screen-device <id>   AVFoundation screen device (default: 2)
  --display-left <px>    Display's global top-left X coordinate (default: 0)
  --display-top <px>     Display's global top-left Y coordinate (default: 0)
  --result <path>        Audit JSON path (default: beside output)
  --help                 Show this help
`;
}

export function parseArgs(argv) {
  const values = {
    duration: DEFAULT_DURATION,
    fps: DEFAULT_FPS,
    width: DEFAULT_WIDTH,
    height: DEFAULT_HEIGHT,
    chromeBin: DEFAULT_CHROME,
    ffmpegBin: "ffmpeg",
    screenDevice: "2",
    displayLeft: 0,
    displayTop: 0,
  };
  const valueOptions = new Set([
    "--url",
    "--output",
    "--duration",
    "--fps",
    "--width",
    "--height",
    "--chrome-bin",
    "--ffmpeg-bin",
    "--screen-device",
    "--display-left",
    "--display-top",
    "--result",
  ]);

  for (let index = 0; index < argv.length; index += 1) {
    const option = argv[index];
    if (option === "--help") return { help: true };
    if (!valueOptions.has(option)) throw new Error(`Unknown option: ${option}`);
    const value = argv[index + 1];
    if (value == null) throw new Error(`Missing value for ${option}`);
    index += 1;
    const key = {
      "--url": "url",
      "--output": "output",
      "--duration": "duration",
      "--fps": "fps",
      "--width": "width",
      "--height": "height",
      "--chrome-bin": "chromeBin",
      "--ffmpeg-bin": "ffmpegBin",
      "--screen-device": "screenDevice",
      "--display-left": "displayLeft",
      "--display-top": "displayTop",
      "--result": "result",
    }[option];
    values[key] = value;
  }

  if (!values.url) throw new Error("--url is required");
  if (!values.output) throw new Error("--output is required");
  for (const key of ["duration", "fps", "width", "height"]) {
    values[key] = Number(values[key]);
    if (!Number.isFinite(values[key]) || values[key] <= 0) {
      throw new Error(`--${key} must be a positive number`);
    }
  }
  values.fps = Math.round(values.fps);
  values.width = Math.round(values.width);
  values.height = Math.round(values.height);
  for (const key of ["displayLeft", "displayTop"]) {
    values[key] = Number(values[key]);
    if (!Number.isFinite(values[key])) {
      throw new Error(`--${key === "displayLeft" ? "display-left" : "display-top"} must be a number`);
    }
    values[key] = Math.round(values[key]);
  }
  values.output = resolve(values.output);
  const outputParts = parse(values.output);
  values.result = values.result
    ? resolve(values.result)
    : join(outputParts.dir, `${outputParts.name}.record-result.json`);
  return values;
}

class CdpClient {
  constructor(url) {
    this.url = url;
    this.nextId = 1;
    this.pending = new Map();
    this.handlers = new Map();
    this.socket = null;
  }

  async connect() {
    this.socket = new WebSocket(this.url);
    await new Promise((resolvePromise, reject) => {
      const onOpen = () => {
        this.socket.removeEventListener("error", onError);
        resolvePromise();
      };
      const onError = () => {
        this.socket.removeEventListener("open", onOpen);
        reject(new Error(`Could not connect to Chrome DevTools: ${this.url}`));
      };
      this.socket.addEventListener("open", onOpen, { once: true });
      this.socket.addEventListener("error", onError, { once: true });
    });
    this.socket.addEventListener("message", (event) => this.handle(event.data));
  }

  handle(raw) {
    const message = JSON.parse(String(raw));
    if (message.id != null) {
      const pending = this.pending.get(message.id);
      if (!pending) return;
      this.pending.delete(message.id);
      if (message.error) pending.reject(new Error(message.error.message));
      else pending.resolve(message.result ?? {});
      return;
    }
    const handlers = this.handlers.get(message.method);
    if (!handlers) return;
    for (const handler of handlers) handler(message.params ?? {});
  }

  send(method, params = {}) {
    if (!this.socket || this.socket.readyState !== WebSocket.OPEN) {
      return Promise.reject(new Error("Chrome DevTools connection is not open"));
    }
    const id = this.nextId;
    this.nextId += 1;
    return new Promise((resolvePromise, reject) => {
      this.pending.set(id, { resolve: resolvePromise, reject });
      this.socket.send(JSON.stringify({ id, method, params }));
    });
  }

  on(method, handler) {
    if (!this.handlers.has(method)) this.handlers.set(method, new Set());
    this.handlers.get(method).add(handler);
    return () => this.handlers.get(method)?.delete(handler);
  }

  waitFor(method, timeoutMs = 15000) {
    return new Promise((resolvePromise, reject) => {
      let remove = () => {};
      const timer = setTimeout(() => {
        remove();
        reject(new Error(`Timed out waiting for ${method}`));
      }, timeoutMs);
      remove = this.on(method, (params) => {
        clearTimeout(timer);
        remove();
        resolvePromise(params);
      });
    });
  }

  close() {
    if (this.socket?.readyState === WebSocket.OPEN) this.socket.close();
  }
}

function waitForDevtools(chrome, timeoutMs = 15000) {
  return new Promise((resolvePromise, reject) => {
    let stderr = "";
    const timer = setTimeout(() => {
      cleanup();
      reject(new Error(`Chrome did not expose DevTools within ${timeoutMs}ms`));
    }, timeoutMs);
    const onData = (chunk) => {
      stderr += chunk.toString();
      const match = stderr.match(/DevTools listening on (ws:\/\/[^\s]+)/);
      if (!match) return;
      cleanup();
      resolvePromise(match[1]);
    };
    const onExit = (code) => {
      cleanup();
      reject(new Error(`Chrome exited before recording began (status ${code})`));
    };
    const cleanup = () => {
      clearTimeout(timer);
      chrome.stderr.off("data", onData);
      chrome.off("exit", onExit);
    };
    chrome.stderr.on("data", onData);
    chrome.once("exit", onExit);
  });
}

async function pageTarget(port, timeoutMs = 15000) {
  const deadline = Date.now() + timeoutMs;
  while (Date.now() < deadline) {
    try {
      const response = await fetch(`http://127.0.0.1:${port}/json/list`);
      const targets = await response.json();
      const page = targets.find((target) => target.type === "page");
      if (page?.webSocketDebuggerUrl) return page.webSocketDebuggerUrl;
    } catch {
      // Chrome can expose its WebSocket before the JSON endpoint is ready.
    }
    await sleep(100);
  }
  throw new Error("Could not find the Chrome page target");
}

function smoothScrollExpression(name, targetExpression, durationMs) {
  return `(() => {
    const requestedDestination = ${targetExpression};
    const maximum = Math.max(0, document.documentElement.scrollHeight - window.innerHeight);
    const destination = Math.max(0, Math.min(maximum, Number(requestedDestination) || 0));
    const start = window.scrollY;
    const distance = destination - start;
    const rootStyle = document.documentElement.style;
    const bodyStyle = document.body.style;
    const previous = {
      rootValue: rootStyle.getPropertyValue("scroll-behavior"),
      rootPriority: rootStyle.getPropertyPriority("scroll-behavior"),
      bodyValue: bodyStyle.getPropertyValue("scroll-behavior"),
      bodyPriority: bodyStyle.getPropertyPriority("scroll-behavior"),
    };
    rootStyle.setProperty("scroll-behavior", "auto", "important");
    bodyStyle.setProperty("scroll-behavior", "auto", "important");
    window.__mergeScrollTraces ||= [];
    const trace = {
      name: ${JSON.stringify(name)},
      requested_duration_ms: ${durationMs},
      start_y: start,
      destination_y: destination,
      samples: [],
      completed: false,
    };
    window.__mergeScrollTraces.push(trace);
    const began = performance.now();
    const restoreScrollBehavior = () => {
      if (previous.rootValue) {
        rootStyle.setProperty("scroll-behavior", previous.rootValue, previous.rootPriority);
      } else {
        rootStyle.removeProperty("scroll-behavior");
      }
      if (previous.bodyValue) {
        bodyStyle.setProperty("scroll-behavior", previous.bodyValue, previous.bodyPriority);
      } else {
        bodyStyle.removeProperty("scroll-behavior");
      }
    };
    const step = (now) => {
      const progress = Math.min(1, (now - began) / ${durationMs});
      const eased = progress < 0.5
        ? 16 * Math.pow(progress, 5)
        : 1 - Math.pow(-2 * progress + 2, 5) / 2;
      window.scrollTo({
        top: start + distance * eased,
        left: window.scrollX,
        behavior: "instant",
      });
      trace.samples.push({
        elapsed_ms: Number((now - began).toFixed(3)),
        y: window.scrollY,
      });
      if (progress < 1) {
        requestAnimationFrame(step);
      } else {
        window.scrollTo({ top: destination, left: window.scrollX, behavior: "instant" });
        trace.samples.push({
          elapsed_ms: Number((performance.now() - began).toFixed(3)),
          y: window.scrollY,
        });
        trace.actual_duration_ms = Number((performance.now() - began).toFixed(3));
        trace.completed = true;
        restoreScrollBehavior();
      }
    };
    requestAnimationFrame(step);
    return true;
  })()`;
}

export function actionPlan() {
  return [
    {
      name: "activate_primary_control",
      atSeconds: 0.75,
      expression: `(() => {
        const controls = [...document.querySelectorAll(
          'button, [role="button"], input[type="button"], input[type="submit"], a[href]'
        )].filter((element) => {
          const style = getComputedStyle(element);
          return element.getClientRects().length > 0 &&
            style.visibility !== 'hidden' &&
            style.display !== 'none' &&
            !element.disabled;
        });
        const label = (element) => String(
          element.innerText || element.value || element.getAttribute('aria-label') ||
          element.getAttribute('title') || ''
        ).trim();
        const score = (element) => {
          const text = label(element).toLowerCase();
          if (/restart|reset|stop|pause|close|cancel/.test(text)) return -1;
          if (/^start\s+(race|game|demo)$/.test(text)) return 100;
          if (/^(start|play|run|launch|begin)$/.test(text)) return 90;
          if (/start|play|run|launch|begin|race/.test(text)) return 60;
          return 0;
        };
        const ranked = controls
          .map((element) => ({ element, score: score(element) }))
          .filter((entry) => entry.score > 0)
          .sort((left, right) => right.score - left.score);
        const selected = ranked[0]?.element;
        selected?.click();
        return selected ? label(selected) : null;
      })()`,
    },
    {
      name: "scroll_to_content",
      atSeconds: 4.5,
      expression: smoothScrollExpression(
        "scroll_to_content",
        "document.body.scrollHeight * 0.45",
        2400,
      ),
    },
    {
      name: "return_to_top",
      atSeconds: 8.0,
      expression: smoothScrollExpression("return_to_top", "0", 2200),
    },
    {
      name: "activate_replay_control",
      atSeconds: 12.25,
      expression: `(() => {
        const controls = [...document.querySelectorAll('button, [role="button"], input[type="button"]')]
          .filter((element) => element.getClientRects().length > 0 && !element.disabled);
        const label = (element) => String(
          element.innerText || element.value || element.getAttribute('aria-label') || ''
        ).trim();
        const replay = controls.find((element) => /restart|again|replay/i.test(label(element)));
        replay?.click();
        return replay ? label(replay) : null;
      })()`,
    },
  ];
}

async function terminate(process) {
  if (!process || process.exitCode != null) return;
  process.kill("SIGTERM");
  await Promise.race([once(process, "exit"), sleep(3000)]);
  if (process.exitCode == null) process.kill("SIGKILL");
}

async function evaluateValue(cdp, expression) {
  const response = await cdp.send("Runtime.evaluate", {
    expression,
    awaitPromise: true,
    returnByValue: true,
  });
  return response.result?.value;
}

async function sizeBrowserViewport(cdp, options) {
  const { windowId } = await cdp.send("Browser.getWindowForTarget");
  const setBounds = async (width, height) => {
    await cdp.send("Browser.setWindowBounds", {
      windowId,
      bounds: {
        left: options.displayLeft,
        top: options.displayTop,
        width,
        height,
        windowState: "normal",
      },
    });
    await sleep(250);
  };
  const readMetrics = () => evaluateValue(cdp, `(() => ({
    screenX: window.screenX,
    screenY: window.screenY,
    outerWidth: window.outerWidth,
    outerHeight: window.outerHeight,
    innerWidth: window.innerWidth,
    innerHeight: window.innerHeight,
    devicePixelRatio: window.devicePixelRatio,
  }))()`);

  await setBounds(options.width, options.height);
  let metrics = await readMetrics();
  const frameWidth = Math.max(0, metrics.outerWidth - metrics.innerWidth);
  const frameHeight = Math.max(0, metrics.outerHeight - metrics.innerHeight);
  await setBounds(options.width + frameWidth, options.height + frameHeight);
  metrics = await readMetrics();

  if (metrics.innerWidth !== options.width || metrics.innerHeight !== options.height) {
    throw new Error(
      `Could not size Chrome viewport to ${options.width}x${options.height}; got ` +
        `${metrics.innerWidth}x${metrics.innerHeight}`,
    );
  }
  if (metrics.devicePixelRatio !== 1) {
    throw new Error(
      `FFmpeg screen capture requires a 1x display; Chrome reported devicePixelRatio=${metrics.devicePixelRatio}`,
    );
  }

  const horizontalFrame = Math.max(0, metrics.outerWidth - metrics.innerWidth);
  const verticalFrame = Math.max(0, metrics.outerHeight - metrics.innerHeight);
  return {
    ...metrics,
    cropX: Math.round(metrics.screenX - options.displayLeft + horizontalFrame / 2),
    cropY: Math.round(metrics.screenY - options.displayTop + verticalFrame),
  };
}

function sampleMotion(ffmpegBin, videoPath) {
  const probe = spawnSync(
    ffmpegBin,
    [
      "-hide_banner",
      "-loglevel",
      "error",
      "-i",
      videoPath,
      "-vf",
      "fps=2,scale=160:-1",
      "-f",
      "framemd5",
      "-",
    ],
    { encoding: "utf8" },
  );
  if (probe.status !== 0) {
    throw new Error(`Could not audit recorded motion: ${probe.stderr.slice(-2000)}`);
  }
  const hashes = probe.stdout
    .split("\n")
    .filter((line) => line && !line.startsWith("#"))
    .map((line) => line.split(",").at(-1)?.trim())
    .filter(Boolean);
  return { samples: hashes.length, uniqueSamples: new Set(hashes).size };
}

export async function recordSite(options) {
  if (!existsSync(options.chromeBin)) {
    throw new Error(`Chrome executable not found: ${options.chromeBin}`);
  }
  if (extname(options.output).toLowerCase() !== ".mp4") {
    throw new Error("--output must end in .mp4");
  }

  const profile = mkdtempSync(join(tmpdir(), "merge-live-recording-"));
  const chrome = spawn(
    options.chromeBin,
    [
      "--disable-gpu",
      "--hide-scrollbars",
      "--allow-file-access-from-files",
      "--no-first-run",
      "--no-default-browser-check",
      "--remote-debugging-port=0",
      `--user-data-dir=${profile}`,
      `--window-position=${options.displayLeft},${options.displayTop}`,
      `--window-size=${options.width},${options.height}`,
      `--app=${options.url}`,
    ],
    { stdio: ["ignore", "ignore", "pipe"] },
  );

  let cdp;
  let ffmpeg;
  const ffmpegErrors = [];
  try {
    const browserWebSocket = await waitForDevtools(chrome);
    const port = new URL(browserWebSocket).port;
    cdp = new CdpClient(await pageTarget(port));
    await cdp.connect();
    await cdp.send("Page.enable");
    await cdp.send("Runtime.enable");
    await cdp.send("Page.bringToFront");
    const loaded = cdp.waitFor("Page.loadEventFired");
    await cdp.send("Page.navigate", { url: options.url });
    await loaded;
    await cdp.send("Runtime.evaluate", {
      expression: "document.fonts ? document.fonts.ready.then(() => true) : true",
      awaitPromise: true,
      returnByValue: true,
    });
    await sleep(250);
    const viewport = await sizeBrowserViewport(cdp, options);
    await cdp.send("Page.bringToFront");

    if (viewport.cropX < 0 || viewport.cropY < 0) {
      throw new Error(
        `Chrome content lies outside the selected display: crop ${viewport.cropX},${viewport.cropY}`,
      );
    }

    ffmpeg = spawn(
      options.ffmpegBin,
      [
        "-hide_banner",
        "-loglevel",
        "warning",
        "-y",
        "-thread_queue_size",
        "512",
        "-f",
        "avfoundation",
        "-pixel_format",
        "nv12",
        "-framerate",
        String(options.fps),
        "-capture_cursor",
        "0",
        "-i",
        `${options.screenDevice}:none`,
        "-t",
        String(options.duration),
        "-vf",
        `crop=${options.width}:${options.height}:${viewport.cropX}:${viewport.cropY},format=yuv420p`,
        "-an",
        "-r",
        String(options.fps),
        "-c:v",
        "libx264",
        "-preset",
        "fast",
        "-crf",
        "18",
        "-pix_fmt",
        "yuv420p",
        "-movflags",
        "+faststart",
        options.output,
      ],
      { stdio: ["ignore", "ignore", "pipe"] },
    );
    ffmpeg.stderr.on("data", (chunk) => ffmpegErrors.push(chunk.toString()));
    const ffmpegClosed = once(ffmpeg, "close");

    const actions = actionPlan();
    const executed = [];
    const began = performance.now();

    while (true) {
      const elapsedSeconds = (performance.now() - began) / 1000;
      for (const action of actions) {
        if (action.executed || elapsedSeconds < action.atSeconds) continue;
        action.executed = true;
        const response = await cdp.send("Runtime.evaluate", {
          expression: action.expression,
          returnByValue: true,
        });
        executed.push({
          name: action.name,
          at_seconds: Number(elapsedSeconds.toFixed(3)),
          page_result: response.result?.value ?? null,
        });
      }
      if (ffmpeg.exitCode != null && elapsedSeconds < options.duration - 0.25) {
        throw new Error(
          `FFmpeg stopped before capture completed: ${ffmpegErrors.join("").slice(-4000)}`,
        );
      }
      if (elapsedSeconds >= options.duration) break;
      await sleep(8);
    }

    const scrollTraceResponse = await cdp.send("Runtime.evaluate", {
      expression: `(() => (window.__mergeScrollTraces || []).map((trace) => {
        const steps = trace.samples.slice(1).map((sample, index) =>
          Math.abs(sample.y - trace.samples[index].y)
        );
        const tail = steps.slice(-Math.min(8, steps.length));
        const last = trace.samples[trace.samples.length - 1];
        return {
          name: trace.name,
          completed: trace.completed,
          requested_duration_ms: trace.requested_duration_ms,
          actual_duration_ms: trace.actual_duration_ms || null,
          sample_count: trace.samples.length,
          start_y: trace.start_y,
          destination_y: trace.destination_y,
          end_y: last ? last.y : trace.start_y,
          maximum_step_px: steps.length ? Math.max(...steps) : 0,
          maximum_tail_step_px: tail.length ? Math.max(...tail) : 0,
          completion_error_px: last ? Math.abs(trace.destination_y - last.y) : null,
        };
      }))()`,
      returnByValue: true,
    });
    const scrollTraces = scrollTraceResponse.result?.value ?? [];

    const [ffmpegCode] = await ffmpegClosed;
    if (ffmpegCode !== 0) {
      throw new Error(
        `FFmpeg exited with status ${ffmpegCode}: ${ffmpegErrors.join("").slice(-4000)}`,
      );
    }
    const motion = sampleMotion(options.ffmpegBin, options.output);

    const result = {
      live_browser_recording: true,
      capture_method: "ffmpeg_avfoundation_screen",
      ffmpeg_is_capture_source: true,
      direct_realtime_capture: true,
      continuous_page_session: true,
      motion_profile: "cinematic_smooth",
      buffered_capture: false,
      source_url: options.url,
      output: options.output,
      viewport: { width: options.width, height: options.height },
      screen_device: options.screenDevice,
      browser_viewport: viewport,
      duration_seconds: options.duration,
      fps: options.fps,
      motion_samples: motion.samples,
      unique_motion_samples: motion.uniqueSamples,
      actions: executed,
      scroll_traces: scrollTraces,
    };
    writeFileSync(options.result, `${JSON.stringify(result, null, 2)}\n`, "utf8");
    return { ...result, result: options.result };
  } finally {
    cdp?.close();
    await terminate(ffmpeg);
    await terminate(chrome);
    if (profile.startsWith(join(tmpdir(), "merge-live-recording-"))) {
      rmSync(profile, { recursive: true, force: true });
    }
  }
}

async function main() {
  try {
    const options = parseArgs(process.argv.slice(2));
    if (options.help) {
      process.stdout.write(usage());
      return;
    }
    const result = await recordSite(options);
    process.stdout.write(`${JSON.stringify(result, null, 2)}\n`);
  } catch (error) {
    process.stderr.write(`${error.message}\n`);
    process.exitCode = 1;
  }
}

const invokedPath = process.argv[1] ? pathToFileURL(resolve(process.argv[1])).href : "";
if (import.meta.url === invokedPath) await main();
