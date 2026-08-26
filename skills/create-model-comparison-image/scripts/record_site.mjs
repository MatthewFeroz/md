#!/usr/bin/env node

import { createHash } from "node:crypto";
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
import { spawn } from "node:child_process";

const DEFAULT_CHROME = "/Applications/Google Chrome.app/Contents/MacOS/Google Chrome";
const DEFAULT_DURATION = 14;
const DEFAULT_FPS = 60;
const DEFAULT_WIDTH = 1440;
const DEFAULT_HEIGHT = 1024;

const sleep = (milliseconds) =>
  new Promise((resolvePromise) => setTimeout(resolvePromise, milliseconds));

function usage() {
  return `Usage: node record_site.mjs --url <url> --output <video.mp4> [options]

Record one continuous live Chrome page session through the DevTools screencast API.

Options:
  --duration <seconds>   Recording duration (default: ${DEFAULT_DURATION})
  --fps <frames>         Output frame rate (default: ${DEFAULT_FPS})
  --width <pixels>       Browser viewport width (default: ${DEFAULT_WIDTH})
  --height <pixels>      Browser viewport height (default: ${DEFAULT_HEIGHT})
  --chrome-bin <path>    Chrome executable
  --ffmpeg-bin <path>    FFmpeg executable or command (default: ffmpeg)
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
      name: "scroll_to_manifest",
      atSeconds: 1.5,
      expression: smoothScrollExpression(
        "scroll_to_manifest",
        `(() => {
          const target = document.querySelector('#manifest, .manifest, .manifest-section, [data-flights]');
          return target ? target.getBoundingClientRect().top + window.scrollY - 56 : document.body.scrollHeight * 0.45;
        })()`,
        2400,
      ),
    },
    {
      name: "select_alternate_mission",
      atSeconds: 4.5,
      expression: `(() => {
        const options = [...document.querySelectorAll('[data-mission], .mission-button')]
          .filter((element) => element.getClientRects().length > 0);
        (options[1] || options[0])?.click();
        return options.length;
      })()`,
    },
    {
      name: "filter_manifest",
      atSeconds: 5.5,
      expression: `(() => {
        const filter = document.querySelector(
          'button[data-filter="open"], button[data-filter="scheduled"], button[data-filter="upcoming"]'
        );
        filter?.click();
        return Boolean(filter);
      })()`,
    },
    {
      name: "return_to_hero",
      atSeconds: 6.4,
      expression: smoothScrollExpression("return_to_hero", "0", 2200),
    },
    {
      name: "open_reservation",
      atSeconds: 9.3,
      expression: `(() => {
        const trigger = document.querySelector(
          '.hero-actions [data-open-reserve], .hero-actions .open-reserve, [data-open-reserve], .open-reserve'
        );
        trigger?.click();
        return Boolean(trigger);
      })()`,
    },
    {
      name: "show_validation",
      atSeconds: 10.7,
      expression: `(() => {
        const submit = document.querySelector('dialog[open] form button[type="submit"]');
        submit?.click();
        return Boolean(submit);
      })()`,
    },
    {
      name: "close_reservation",
      atSeconds: 12.4,
      expression: `(() => {
        const close = document.querySelector(
          'dialog[open] .dialog-close, dialog[open] [data-close-reserve]'
        );
        close?.click();
        return Boolean(close);
      })()`,
    },
  ];
}

async function waitForFirstFrame(frameState, timeoutMs = 10000) {
  const deadline = Date.now() + timeoutMs;
  while (!frameState.latest && Date.now() < deadline) await sleep(25);
  if (!frameState.latest) throw new Error("Chrome did not emit a screencast frame");
}

async function terminate(process) {
  if (!process || process.exitCode != null) return;
  process.kill("SIGTERM");
  await Promise.race([once(process, "exit"), sleep(3000)]);
  if (process.exitCode == null) process.kill("SIGKILL");
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
      "--headless=new",
      "--disable-gpu",
      "--hide-scrollbars",
      "--allow-file-access-from-files",
      "--remote-debugging-port=0",
      `--user-data-dir=${profile}`,
      `--window-size=${options.width},${options.height}`,
      "about:blank",
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
    await cdp.send("Emulation.setDeviceMetricsOverride", {
      width: options.width,
      height: options.height,
      deviceScaleFactor: 1,
      mobile: false,
      screenWidth: options.width,
      screenHeight: options.height,
    });
    const loaded = cdp.waitFor("Page.loadEventFired");
    await cdp.send("Page.navigate", { url: options.url });
    await loaded;
    await cdp.send("Runtime.evaluate", {
      expression: "document.fonts ? document.fonts.ready.then(() => true) : true",
      awaitPromise: true,
      returnByValue: true,
    });
    await sleep(250);

    const frameState = {
      latest: null,
      received: 0,
      uniqueHashes: new Set(),
      captureBegan: null,
      capturedFrames: [],
    };
    const removeFrameHandler = cdp.on("Page.screencastFrame", (frame) => {
      const payload = Buffer.from(frame.data, "base64");
      frameState.latest = payload;
      frameState.received += 1;
      frameState.uniqueHashes.add(createHash("sha256").update(payload).digest("hex"));
      if (frameState.captureBegan != null) {
        frameState.capturedFrames.push({
          atSeconds: (performance.now() - frameState.captureBegan) / 1000,
          payload,
        });
      }
      cdp.send("Page.screencastFrameAck", { sessionId: frame.sessionId }).catch(() => {});
    });
    await cdp.send("Page.startScreencast", {
      format: "jpeg",
      quality: 92,
      maxWidth: options.width,
      maxHeight: options.height,
      everyNthFrame: 1,
    });
    await waitForFirstFrame(frameState);

    const actions = actionPlan();
    const executed = [];
    const began = performance.now();
    frameState.captureBegan = began;
    frameState.capturedFrames.push({ atSeconds: 0, payload: frameState.latest });

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
      if (elapsedSeconds >= options.duration) break;
      await sleep(8);
    }

    frameState.captureBegan = null;
    await cdp.send("Page.stopScreencast");
    removeFrameHandler();

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

    ffmpeg = spawn(
      options.ffmpegBin,
      [
        "-y",
        "-f",
        "image2pipe",
        "-framerate",
        String(options.fps),
        "-vcodec",
        "mjpeg",
        "-i",
        "pipe:0",
        "-vf",
        `scale=${options.width}:${options.height}:flags=lanczos,format=yuv420p`,
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
      { stdio: ["pipe", "ignore", "pipe"] },
    );
    ffmpeg.stderr.on("data", (chunk) => ffmpegErrors.push(chunk.toString()));

    const totalFrames = Math.round(options.duration * options.fps);
    let sourceIndex = 0;
    for (let frameIndex = 0; frameIndex < totalFrames; frameIndex += 1) {
      const targetSeconds = frameIndex / options.fps;
      while (
        sourceIndex + 1 < frameState.capturedFrames.length &&
        frameState.capturedFrames[sourceIndex + 1].atSeconds <= targetSeconds
      ) {
        sourceIndex += 1;
      }
      const payload = frameState.capturedFrames[sourceIndex].payload;
      if (!ffmpeg.stdin.write(payload)) await once(ffmpeg.stdin, "drain");
    }

    const ffmpegClosed = once(ffmpeg, "close");
    ffmpeg.stdin.end();
    const [ffmpegCode] = await ffmpegClosed;
    if (ffmpegCode !== 0) {
      throw new Error(
        `FFmpeg exited with status ${ffmpegCode}: ${ffmpegErrors.join("").slice(-4000)}`,
      );
    }

    const result = {
      live_browser_recording: true,
      capture_method: "chrome_devtools_screencast",
      continuous_page_session: true,
      motion_profile: "cinematic_smooth",
      buffered_capture: true,
      source_url: options.url,
      output: options.output,
      viewport: { width: options.width, height: options.height },
      duration_seconds: options.duration,
      fps: options.fps,
      encoded_frames: totalFrames,
      screencast_frames_received: frameState.received,
      captured_screencast_frames: frameState.capturedFrames.length,
      unique_screencast_frames: frameState.uniqueHashes.size,
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
