/**
 * Minimal TypeScript client for SelfPrompt.
 *
 * Shells out to the `selfprompt` CLI (must be installed and on PATH:
 * `pip install selfprompt`) and parses its `--json` output. No other
 * runtime dependencies -- this is meant to be embeddable in Cursor/Continue
 * extensions or any Node-based agent host without dragging in a package
 * graph.
 */

import { spawn } from "node:child_process";

export interface Turn {
  index: number;
  timestamp: string;
  observation: string;
  critique: {
    progress_made: boolean;
    confidence: number;
    issues: string[];
    notes: string;
  };
  action: {
    type: "tool_call" | "delegate" | "message" | "finish" | "abort";
    detail: string;
    tool_name?: string;
    tool_args?: Record<string, unknown>;
    delegate_agent?: string;
  };
  result: string;
  tokens_used: number;
  cost_usd: number;
}

export interface LoopResult {
  goal: string;
  finished: boolean;
  stop_reason: string;
  turn_count: number;
  total_tokens: number;
  total_cost_usd: number;
  turns: Turn[];
}

export interface RunOptions {
  goalId?: string;
  provider?: "anthropic" | "openai" | "mock";
  model?: string;
  maxTurns?: number;
  multiAgent?: boolean;
  autoApprove?: boolean;
  cwd?: string;
  binary?: string; // defaults to "selfprompt"
}

/** Run a goal via the `selfprompt` CLI and resolve with the parsed result. */
export function runGoal(goal: string, options: RunOptions = {}): Promise<LoopResult> {
  const bin = options.binary ?? "selfprompt";
  const args = ["run", goal, "--json"];
  if (options.goalId) args.push("--goal-id", options.goalId);
  if (options.provider) args.push("--provider", options.provider);
  if (options.model) args.push("--model", options.model);
  if (options.maxTurns) args.push("--max-turns", String(options.maxTurns));
  if (options.multiAgent) args.push("--multi-agent");
  if (options.autoApprove) args.push("--yes");

  return new Promise((resolve, reject) => {
    const child = spawn(bin, args, { cwd: options.cwd });
    let stdout = "";
    let stderr = "";
    child.stdout.on("data", (chunk) => (stdout += chunk));
    child.stderr.on("data", (chunk) => (stderr += chunk));
    child.on("error", reject);
    child.on("close", () => {
      try {
        const lastLine = stdout.trim().split("\n").pop() ?? "";
        resolve(JSON.parse(lastLine) as LoopResult);
      } catch (err) {
        reject(new Error(`failed to parse selfprompt output: ${err}\nstderr: ${stderr}`));
      }
    });
  });
}

/** Fetch the recorded progress/lessons for a goal via `selfprompt status`. */
export function getStatus(goalId: string, options: { cwd?: string; binary?: string } = {}): Promise<string> {
  const bin = options.binary ?? "selfprompt";
  return new Promise((resolve, reject) => {
    const child = spawn(bin, ["status", goalId], { cwd: options.cwd });
    let stdout = "";
    child.stdout.on("data", (chunk) => (stdout += chunk));
    child.on("error", reject);
    child.on("close", () => resolve(stdout));
  });
}
