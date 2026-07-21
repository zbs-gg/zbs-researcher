#!/usr/bin/env node
/*
 * zbs-researcher — one-command installer for the ZBS Researcher
 * (deep-research) Claude Code plugin.
 *
 * Thin, transparent shim: it prints exactly which commands it will run,
 * asks before running them, and touches nothing else.
 *
 *   npx -y zbs-researcher@latest          # interactive (confirms first)
 *   npx -y zbs-researcher@latest --yes    # non-interactive
 *
 * Node >= 18, zero dependencies (node stdlib only).
 */
"use strict";

const { execSync, spawn } = require("node:child_process");
const readline = require("node:readline");

const MARKETPLACE_CMD = "claude plugin marketplace add zbs-gg/zbs-research";
const INSTALL_CMD = "claude plugin install deep-research@zbs-research";
const INSTALL_LINK = "https://code.claude.com/docs";

// Banner art mirrors skills/deep-research/scripts/term_ui.py — visual parity
// with the runner's own banner is intentional; keep the two in sync.
const ART_LINES = [
  "████ ███   ███    ███  ████  ███ ████  ██  ███   ███ █  █ ████ ███",
  "  █  █  █ █       █  █ █    █    █    █  █ █  █ █    █  █ █    █  █",
  " █   ███   ██     ███  ███   ██  ███  ████ ███  █    ████ ███  ███",
  "█    █  █    █    █ █  █       █ █    █  █ █ █  █    █  █ █    █ █",
  "████ ███  ███     █  █ ████ ███  ████ █  █ █  █  ███ █  █ ████ █  █",
];
const SUBTITLE = "                  deep research · reactions from real humans";
const PLAIN_TITLE = "ZBS RESEARCHER — deep research";
const ART_MIN_COLUMNS = 78;
const SPINNER_FRAMES = ["|", "/", "-", "\\"];
const SPINNER_INTERVAL_MS = 120;

// --- flags -----------------------------------------------------------------
const flags = { yes: false, dryRun: false, noColor: false, help: false };
for (const arg of process.argv.slice(2)) {
  if (arg === "--yes" || arg === "-y") flags.yes = true;
  else if (arg === "--dry-run") flags.dryRun = true;
  else if (arg === "--no-color") flags.noColor = true;
  else if (arg === "--help" || arg === "-h") flags.help = true;
  else process.stderr.write("(ignoring unknown argument: " + arg + ")\n");
}

// NO_COLOR counts only when present AND non-empty (no-color.org), matching
// the runner's term_ui.py precedence. Plain tier = no ANSI anywhere.
const plainTier =
  flags.noColor ||
  Boolean(process.env.NO_COLOR) ||
  process.env.TERM === "dumb" ||
  !process.stderr.isTTY;
const useColor = !plainTier;
// Animation additionally requires a real TTY (already implied) and no CI.
const animate = !plainTier && !process.env.CI;

// ANSI is only ever written to stderr; stdout stays clean text.
function paint(code, text) {
  return useColor ? "\x1b[" + code + "m" + text + "\x1b[0m" : text;
}

function banner() {
  const width = process.stderr.columns || 80;
  if (plainTier || width < ART_MIN_COLUMNS) return PLAIN_TITLE;
  const lines = ART_LINES.map((line) => paint("1;36", line));
  lines.push(paint("2", SUBTITLE));
  return lines.join("\n");
}

function printPlannedCommands() {
  console.log("Commands to run:");
  console.log("  1. " + MARKETPLACE_CMD);
  console.log("  2. " + INSTALL_CMD);
}

function printHelp() {
  console.log("Usage: npx -y zbs-researcher@latest [options]");
  console.log("");
  console.log("Installs the deep-research (ZBS Researcher) Claude Code plugin.");
  console.log("");
  console.log("Options:");
  console.log("  -y, --yes      run without the confirmation prompt");
  console.log("      --dry-run  print the commands, execute nothing");
  console.log("      --no-color disable ANSI colors");
  console.log("  -h, --help     show this help");
}

function hasClaude() {
  const probe = process.platform === "win32" ? "where claude" : "which claude";
  try {
    execSync(probe, { stdio: "ignore" });
    return true;
  } catch (_e) {
    return false;
  }
}

// EOF-safe confirm: resolves false on Ctrl-C/Ctrl-D instead of hanging.
function confirm() {
  return new Promise((resolve) => {
    const rl = readline.createInterface({
      input: process.stdin,
      output: process.stderr,
    });
    let answered = false;
    rl.question("Proceed? [y/N] ", (answer) => {
      answered = true;
      rl.close();
      resolve(/^y(es)?$/i.test(answer.trim()));
    });
    rl.on("close", () => {
      if (!answered) {
        process.stderr.write("\n");
        resolve(false);
      }
    });
  });
}

// Runs one shell command. Output is captured and re-printed after the
// command finishes, so the TTY-gated spinner never fights live output;
// stdin is inherited. Never rejects — resolves { code, output, seconds }.
function runCommand(cmd) {
  return new Promise((resolve) => {
    const started = Date.now();
    const cols = process.stderr.columns || 80;
    const label = ("running: " + cmd).slice(0, Math.max(10, cols - 3));
    let spinnerTimer = null;
    if (animate) {
      let frame = 0;
      spinnerTimer = setInterval(() => {
        process.stderr.write(
          "\r" +
            paint("36", SPINNER_FRAMES[frame++ % SPINNER_FRAMES.length]) +
            " " +
            label
        );
      }, SPINNER_INTERVAL_MS);
    } else {
      process.stderr.write("→ " + label + "\n");
    }
    const stopSpinner = () => {
      if (spinnerTimer) {
        clearInterval(spinnerTimer);
        spinnerTimer = null;
        // Clear the spinner line before any of the command's output appears.
        process.stderr.write(
          "\r" + " ".repeat(Math.min(cols - 1, label.length + 2)) + "\r"
        );
      }
    };
    let output = "";
    let done = false;
    const finish = (code, extra) => {
      if (done) return;
      done = true;
      stopSpinner();
      if (extra) output += (output ? "\n" : "") + extra;
      resolve({
        code,
        output: output.trim(),
        seconds: ((Date.now() - started) / 1000).toFixed(1),
      });
    };
    let child;
    try {
      child = spawn(cmd, { shell: true, stdio: ["inherit", "pipe", "pipe"] });
    } catch (e) {
      finish(1, String((e && e.message) || e));
      return;
    }
    child.stdout.on("data", (chunk) => {
      output += chunk;
    });
    child.stderr.on("data", (chunk) => {
      output += chunk;
    });
    child.on("error", (e) => finish(1, String((e && e.message) || e)));
    child.on("close", (code) => finish(code === null ? 1 : code));
  });
}

function reportCommand(cmd, result) {
  if (result.code === 0) {
    process.stderr.write(
      paint("32", "+") + " " + cmd + " (" + result.seconds + "s)\n"
    );
  } else {
    process.stderr.write(
      paint("31", "x") + " " + cmd + " (exit " + result.code + ")\n"
    );
  }
  if (result.output) {
    process.stderr.write(
      result.output
        .split("\n")
        .map((line) => "  " + line)
        .join("\n") + "\n"
    );
  }
}

async function main() {
  process.stderr.write(banner() + "\n\n");
  if (flags.help) {
    printHelp();
    return 0;
  }

  console.log(
    "Installs the deep-research (ZBS Researcher) plugin into Claude Code."
  );
  console.log("");
  printPlannedCommands();
  console.log("");

  if (flags.dryRun) {
    console.log("(dry run — nothing executed)");
    return 0;
  }

  if (!hasClaude()) {
    console.log(
      "Could not find the `claude` CLI on PATH."
    );
    console.log("Install Claude Code first:");
    console.log("  " + INSTALL_LINK);
    console.log(
      "Then run the two commands above manually — or re-run this installer."
    );
    return 0;
  }

  if (!flags.yes) {
    if (!process.stdin.isTTY) {
      // Non-interactive stdin (pipe/EOF): never hang on a prompt.
      console.log(
        "Non-interactive stdin — nothing executed."
      );
      console.log(
        "Run with --yes to execute."
      );
      return 0;
    }
    const proceed = await confirm();
    if (!proceed) {
      console.log(
        "Cancelled — nothing executed."
      );
      return 0;
    }
  }

  const marketplace = await runCommand(MARKETPLACE_CMD);
  reportCommand(MARKETPLACE_CMD, marketplace);
  if (marketplace.code !== 0) {
    if (/already/i.test(marketplace.output)) {
      process.stderr.write(
        paint(
          "2",
          "  (marketplace already added — continuing)"
        ) + "\n"
      );
    } else {
      console.log(
        "Failed to add the marketplace."
      );
      return 1;
    }
  }

  const install = await runCommand(INSTALL_CMD);
  reportCommand(INSTALL_CMD, install);
  if (install.code !== 0) {
    if (/already/i.test(install.output)) {
      process.stderr.write(
        paint(
          "2",
          "  (plugin already installed — continuing)"
        ) + "\n"
      );
    } else {
      console.log(
        "Failed to install the plugin."
      );
      return 1;
    }
  }

  // Loose verification: `claude plugin list` output format is unpinned, so
  // just grep for the plugin id anywhere in it.
  let listing = null;
  try {
    listing = execSync("claude plugin list", {
      encoding: "utf8",
      stdio: ["ignore", "pipe", "pipe"],
    });
  } catch (_e) {
    listing = null;
  }
  if (listing === null) {
    console.log(
      "Commands ran, but verification via `claude plugin list` failed — check manually."
    );
    return 0;
  }
  if (!/deep-research/i.test(listing)) {
    console.log(
      "Plugin not visible in `claude plugin list` — check manually."
    );
    return 1;
  }

  console.log("");
  console.log("Done! Open Claude Code and say: run deep research");
  return 0;
}

main().then(
  (code) => {
    process.exitCode = code;
  },
  (e) => {
    process.stderr.write("Unexpected error: " + String((e && e.stack) || e) + "\n");
    process.exitCode = 1;
  }
);
