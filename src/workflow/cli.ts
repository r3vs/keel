/**
 * CLI entry — run a topology against a host and print the result as JSON.
 *
 * Invocation model (design §10, resolved without a new fork): the engine is PURE and never speaks
 * MCP. A skill/command running INSIDE a host session invokes this —
 *   node --experimental-strip-types workflow/cli.ts --host <self> --topology phase1-finding
 * — the engine drives sub-invocations of that host's OWN cli (claude -p / codex exec / opencode run)
 * and prints the result as JSON. For read-only finding/challenge topologies the calling agent then
 * writes the returned pins/events via the MCP tools it already holds (`ledger_add_pin`); the WRITE
 * topology (build-waves) runs executors in git worktrees and returns a wave summary. So the engine
 * needs no MCP client, and the read-only path needs no npm deps — only Node + the host cli.
 *
 * Topology args (oracles for challenger-verify, waves for build-waves) come from `--args-file <json>`.
 */
import { pathToFileURL } from 'node:url';
import { readFileSync } from 'node:fs';
import { runWorkflow } from './engine.ts';
import { runWorkflowSource } from './sandbox.ts';
import type { SpawnAdapter } from './adapter.ts';
import { ClaudeCliAdapter } from './adapter.ts';
import { CodexCliAdapter } from './adapters/codex.ts';
import { OpencodeCliAdapter } from './adapters/opencode.ts';
import { WorktreeAdapter } from './worktree.ts';
import { ClaudeSdkAdapter } from './adapters/claude-sdk.ts';
import { CodexSdkAdapter } from './adapters/codex-sdk.ts';
import { PiAdapter } from './adapters/pi.ts';
import type { WorkflowCtx } from './engine.ts';
import { phase1Finding } from './topologies/phase1-finding.ts';
import { challengerVerify } from './topologies/challenger-verify.ts';
import { buildWaves } from './topologies/build-waves.ts';

export type CliOpts = {
  host: string;
  topology: string;
  model?: string;
  ledger?: string;
  argsFile?: string;
  argsStdin: boolean;
  script?: string; // path to an ad-hoc workflow SOURCE (the "author on the fly" path)
  scriptStdin: boolean;
  worktree: boolean;
  json: boolean;
};

export function parseArgs(argv: string[]): CliOpts {
  const o: CliOpts = {
    host: 'claude',
    topology: 'phase1-finding',
    argsStdin: false,
    scriptStdin: false,
    worktree: false,
    json: true,
  };
  for (let i = 0; i < argv.length; i++) {
    const a = argv[i];
    if (a === '--host') o.host = argv[++i];
    else if (a === '--topology') o.topology = argv[++i];
    else if (a === '--model') o.model = argv[++i];
    else if (a === '--ledger') o.ledger = argv[++i];
    else if (a === '--args-file') o.argsFile = argv[++i];
    else if (a === '--args-stdin') o.argsStdin = true;
    else if (a === '--script') o.script = argv[++i];
    else if (a === '--script-stdin') o.scriptStdin = true;
    else if (a === '--worktree') o.worktree = true;
    else if (a === '--text') o.json = false;
  }
  // `--args-file -` / `--script -` are shorthand for reading that input from stdin.
  if (o.argsFile === '-') {
    o.argsFile = undefined;
    o.argsStdin = true;
  }
  if (o.script === '-') {
    o.script = undefined;
    o.scriptStdin = true;
  }
  return o;
}

// Default hosts are the dependency-free CLI adapters (Node + the host cli). The `*-sdk` / `pi` hosts
// are opt-in WARM adapters: they need the provider SDK installed and fail loud if it is absent.
export const ADAPTERS: Record<string, (model?: string) => SpawnAdapter> = {
  claude: (model) => new ClaudeCliAdapter({ model }),
  codex: (model) => new CodexCliAdapter({ model }),
  opencode: (model) => new OpencodeCliAdapter({ model }),
  'claude-sdk': (model) => new ClaudeSdkAdapter({ model }),
  'codex-sdk': (model) => new CodexSdkAdapter({ model }),
  pi: (model) => new PiAdapter({ model }),
};

export type Topology = (wf: WorkflowCtx, args?: any) => Promise<unknown>;

export const TOPOLOGIES: Record<string, Topology> = {
  'phase1-finding': (wf) => phase1Finding(wf),
  'challenger-verify': (wf, args) => challengerVerify(wf, args),
  'build-waves': (wf, args) => buildWaves(wf, args),
};

// build-waves writes code, so its executors must be isolated in worktrees.
const WRITE_TOPOLOGIES = new Set(['build-waves']);

export async function runCli(
  opts: CliOpts,
  deps?: {
    adapters?: Record<string, (model?: string) => SpawnAdapter>;
    topologies?: Record<string, Topology>;
    args?: unknown;
    source?: string;
    repoRoot?: string;
  },
): Promise<unknown> {
  const adapters = deps?.adapters ?? ADAPTERS;
  const topologies = deps?.topologies ?? TOPOLOGIES;
  const makeAdapter = adapters[opts.host];
  if (!makeAdapter) {
    throw new Error(`unknown --host "${opts.host}" (have: ${Object.keys(adapters).join(', ')})`);
  }

  // An ad-hoc workflow SOURCE (author-on-the-fly) takes precedence over a registered topology.
  const source =
    deps?.source ??
    (opts.scriptStdin ? readFileSync(0, 'utf8') : opts.script ? readFileSync(opts.script, 'utf8') : undefined);

  // Topology args: injected (tests) > stdin (only when the script isn't already using stdin) > file > none.
  const args =
    deps?.args ??
    (opts.argsStdin && !opts.scriptStdin
      ? JSON.parse(readFileSync(0, 'utf8') || '{}')
      : opts.argsFile
        ? JSON.parse(readFileSync(opts.argsFile, 'utf8'))
        : {});

  let adapter = makeAdapter(opts.model);
  if (opts.worktree || WRITE_TOPOLOGIES.has(opts.topology)) {
    adapter = new WorktreeAdapter(adapter, { repoRoot: deps?.repoRoot ?? process.cwd() });
  }

  if (source != null) {
    // vm sandbox + determinism guard; primitives injected as globals (agent/parallel/verify/…/checkpoint).
    const { result } = await runWorkflowSource(source, { adapter, args, onLog: (m) => console.error(m) });
    return result;
  }

  const topo = topologies[opts.topology];
  if (!topo) {
    throw new Error(`unknown --topology "${opts.topology}" (have: ${Object.keys(topologies).join(', ')})`);
  }
  const { result } = await runWorkflow((wf) => topo(wf, args), {
    adapter,
    onLog: (m) => console.error(m), // logs to stderr; stdout stays clean JSON
  });
  return result;
}

// Run only when invoked directly, not when imported by a test.
if (process.argv[1] && import.meta.url === pathToFileURL(process.argv[1]).href) {
  const opts = parseArgs(process.argv.slice(2));
  const result = await runCli(opts);
  process.stdout.write(opts.json ? `${JSON.stringify(result, null, 2)}\n` : `${String(result)}\n`);
}
