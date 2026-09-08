#!/usr/bin/env node

import { spawn } from "node:child_process";
import { createHash } from "node:crypto";
import { access, readFile, writeFile } from "node:fs/promises";
import path from "node:path";
import readline from "node:readline";

function parseArgs(argv) {
  const values = {};
  for (let index = 0; index < argv.length; index += 1) {
    const key = argv[index];
    if (!key.startsWith("--")) throw new Error(`Unexpected argument: ${key}`);
    const value = argv[index + 1];
    if (value === undefined || value.startsWith("--")) throw new Error(`Missing value for ${key}`);
    values[key.slice(2)] = value;
    index += 1;
  }
  for (const name of ["plugin-root", "scene", "output", "audit"]) {
    if (!values[name]) throw new Error(`Required argument missing: --${name}`);
  }
  return values;
}

function absolute(value) {
  return path.resolve(value);
}

async function requireFile(filePath) {
  await access(filePath);
}

async function requireMissing(filePath) {
  try {
    await access(filePath);
  } catch {
    return;
  }
  throw new Error(`Refusing to overwrite existing output: ${filePath}`);
}

class McpJsonLineClient {
  constructor(serverPath, cwd) {
    this.nextId = 1;
    this.pending = new Map();
    this.stderr = "";
    this.closed = false;
    this.child = spawn(process.execPath, [serverPath], {
      cwd,
      stdio: ["pipe", "pipe", "pipe"],
      windowsHide: true,
    });
    const lines = readline.createInterface({ input: this.child.stdout, crlfDelay: Infinity });
    lines.on("line", (line) => this.handleLine(line));
    this.child.stderr.on("data", (chunk) => {
      this.stderr += chunk.toString("utf8");
    });
    this.child.on("exit", (code, signal) => {
      this.closed = true;
      const error = new Error(`MCP server exited before completing requests: code=${code} signal=${signal}\n${this.stderr}`);
      for (const { reject } of this.pending.values()) reject(error);
      this.pending.clear();
    });
  }

  handleLine(line) {
    if (!line.trim()) return;
    let message;
    try {
      message = JSON.parse(line);
    } catch (error) {
      const wrapped = new Error(`Invalid MCP JSON line: ${error.message}\n${line}`);
      for (const { reject } of this.pending.values()) reject(wrapped);
      this.pending.clear();
      return;
    }
    const pending = this.pending.get(message.id);
    if (!pending) return;
    this.pending.delete(message.id);
    if (message.error) pending.reject(new Error(JSON.stringify(message.error)));
    else pending.resolve(message.result);
  }

  request(method, params = {}) {
    if (this.closed) return Promise.reject(new Error("MCP server is closed"));
    const id = this.nextId;
    this.nextId += 1;
    const payload = JSON.stringify({ jsonrpc: "2.0", id, method, params });
    return new Promise((resolve, reject) => {
      this.pending.set(id, { resolve, reject });
      this.child.stdin.write(`${payload}\n`, "utf8", (error) => {
        if (!error) return;
        this.pending.delete(id);
        reject(error);
      });
    });
  }

  async initialize() {
    return this.request("initialize", {
      protocolVersion: "2025-06-18",
      capabilities: {},
      clientInfo: { name: "reconstruct-paper-figures", version: "1.0.0" },
    });
  }

  async callTool(name, args) {
    const result = await this.request("tools/call", { name, arguments: args });
    if (result?.isError) {
      throw new Error(`${name} failed: ${JSON.stringify(result.structuredContent ?? result.content)}`);
    }
    return result?.structuredContent ?? result;
  }

  async close() {
    if (this.closed) return;
    this.child.stdin.end();
    await new Promise((resolve) => {
      const timer = setTimeout(() => {
        this.child.kill();
        resolve();
      }, 10000);
      this.child.once("exit", () => {
        clearTimeout(timer);
        resolve();
      });
    });
  }
}

async function main() {
  const args = parseArgs(process.argv.slice(2));
  const pluginRoot = absolute(args["plugin-root"]);
  const scenePath = absolute(args.scene);
  const outputPath = absolute(args.output);
  const auditPath = absolute(args.audit);
  const previewPath = args.preview ? absolute(args.preview) : null;
  const svgPath = args.svg ? absolute(args.svg) : null;
  const pdfPath = args.pdf ? absolute(args.pdf) : null;
  const stepDelayMs = Number(args["step-delay-ms"] ?? 100);
  const liveInspectEnabled = (args["live-inspect"] ?? "false") === "true";
  const fileInspectEnabled = (args["file-inspect"] ?? "false") === "true";
  if (!["true", "false"].includes(args["live-inspect"] ?? "false")) {
    throw new Error("--live-inspect must be true or false");
  }
  if (!["true", "false"].includes(args["file-inspect"] ?? "false")) {
    throw new Error("--file-inspect must be true or false");
  }
  if (!Number.isInteger(stepDelayMs) || stepDelayMs < 100 || stepDelayMs > 10000) {
    throw new Error("--step-delay-ms must be an integer from 100 to 10000");
  }

  const liveServer = path.join(pluginRoot, "scripts", "live-server.mjs");
  const fileServer = path.join(pluginRoot, "scripts", "file-server.mjs");
  await Promise.all([requireFile(liveServer), requireFile(fileServer), requireFile(scenePath)]);
  await Promise.all([outputPath, auditPath, previewPath, svgPath, pdfPath].filter(Boolean).map(requireMissing));

  const sceneBytes = await readFile(scenePath);
  const sceneSha256 = createHash("sha256").update(sceneBytes).digest("hex");
  const scene = JSON.parse(sceneBytes.toString("utf8"));
  const live = new McpJsonLineClient(liveServer, pluginRoot);
  let launch;
  let draw;
  let liveInspect;
  let save;
  try {
    await live.initialize();
    launch = await live.callTool("visio_live_launch", {
      mode: "new",
      page_name: scene.scene_id,
      canvas: scene.canvas,
      step_delay_ms: stepDelayMs,
      maximize: true,
      include_preview: false,
    });
    draw = await live.callTool("visio_live_draw_scene", {
      scene,
      step_delay_ms: stepDelayMs,
      existing_policy: "error",
    });
    if (draw.error || draw.failed_index !== null) throw new Error(`Scene execution failed: ${JSON.stringify(draw)}`);
    // Large grouped pages can exceed the live bridge's fixed 30 s inspect
    // timeout even after drawing succeeds. The saved-file inspection below is
    // authoritative and has the same semantic IDs, so live inspect is opt-in.
    liveInspect = liveInspectEnabled
      ? await live.callTool("visio_live_inspect", { max_shapes: 250 })
      : { skipped: true, reason: "saved-file inspection is authoritative" };
    save = await live.callTool("visio_live_save", { output_path: outputPath, overwrite: false });
    await live.callTool("visio_live_shutdown", { confirm: true, dirty_action: "discard" });
  } catch (error) {
    try {
      await live.callTool("visio_live_shutdown", { confirm: true, dirty_action: "discard" });
    } catch {
      // Preserve the original failure; shutdown is best-effort only.
    }
    throw error;
  } finally {
    await live.close();
  }

  const fileClient = new McpJsonLineClient(fileServer, pluginRoot);
  let validate;
  let inspect;
  let fidelity;
  const exports = {};
  try {
    await fileClient.initialize();
    validate = await fileClient.callTool("visio_validate", { input_path: outputPath });
    inspect = fileInspectEnabled
      ? await fileClient.callTool("visio_inspect_file", { input_path: outputPath, max_shapes: 250 })
      : { skipped: true, reason: "validate_fidelity has a 120 s timeout and is authoritative" };
    fidelity = await fileClient.callTool("visio_validate_fidelity", {
      scene_path: scenePath,
      input_path: outputPath,
      minimum_primitive_ratio: 0.9,
    });
    if (previewPath) {
      exports.preview = await fileClient.callTool("visio_export", {
        input_path: outputPath,
        format: "png",
        output_path: previewPath,
        page_scope: "current",
        width: 2400,
        overwrite: false,
      });
    }
    if (svgPath) {
      exports.svg = await fileClient.callTool("visio_export", {
        input_path: outputPath,
        format: "svg",
        output_path: svgPath,
        page_scope: "current",
        overwrite: false,
      });
    }
    if (pdfPath) {
      exports.pdf = await fileClient.callTool("visio_export", {
        input_path: outputPath,
        format: "pdf",
        output_path: pdfPath,
        page_scope: "current",
        overwrite: false,
      });
    }
  } finally {
    await fileClient.close();
  }

  const audit = {
    schema_version: "visio-scene-mcp-runtime-v1",
    backend: "visio_scenegraph",
    scene_sha256: sceneSha256,
    runtime_version: `Microsoft Visio ${launch.visioVersion} via TZ-mx Visio-Illustrator`,
    opened: Boolean(launch.sessionId),
    saved: Boolean(save.validated),
    reopened: Boolean(validate.valid && fidelity.valid),
    object_counts: {
      total_objects: scene.nodes.length + scene.connectors.length,
      text_objects: scene.nodes.filter((node) => node.kind === "text").length,
      vector_objects: scene.nodes.length,
      edge_objects: scene.connectors.length,
      connector_objects: scene.connectors.length,
      atomic_rasters: scene.nodes.filter((node) => node.kind === "image").length,
    },
    scene_path: scenePath,
    output_path: outputPath,
    plugin_root: pluginRoot,
    runtime_verified: true,
    launch,
    draw,
    live_inspect: liveInspect,
    save,
    file_validate: validate,
    file_inspect: inspect,
    fidelity,
    exports,
    publication_note: "VSDX runtime verification proves the Visio authoring backend only. Final live-Type AI/PDF proof still belongs to Illustrator.",
  };
  await writeFile(auditPath, `${JSON.stringify(audit, null, 2)}\n`, { encoding: "utf8", flag: "wx" });
  process.stdout.write(`${JSON.stringify({ output: outputPath, audit: auditPath, runtime_verified: true })}\n`);
}

main().catch(async (error) => {
  const detail = error.stack || error.message;
  try {
    const args = parseArgs(process.argv.slice(2));
    const failureAudit = {
      schema_version: "visio-scene-mcp-runtime-v1",
      scene_path: absolute(args.scene),
      output_path: absolute(args.output),
      plugin_root: absolute(args["plugin-root"]),
      runtime_verified: false,
      failure: detail,
      publication_note: "Fail-closed runtime record; no VSDX backend success is claimed.",
    };
    await writeFile(absolute(args.audit), `${JSON.stringify(failureAudit, null, 2)}\n`, {
      encoding: "utf8",
      flag: "wx",
    });
  } catch (auditError) {
    process.stderr.write(`Could not write failure audit: ${auditError.message}\n`);
  }
  process.stderr.write(`${detail}\n`);
  process.exitCode = 1;
});
