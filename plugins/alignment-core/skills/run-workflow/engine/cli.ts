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
import type { SpawnAdapter } from './adapter.ts';
import { ClaudeCliAdapter } from './adapter.ts';
import { CodexCliAdapter } from './adapters/codex.ts';
import { OpencodeCliAdapter } from './adapters/opencode.ts';
import { WorktreeAdapter } from './worktree.ts';
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
  worktree: boolean;
  json: boolean;
};

export function parseArgs(argv: string[]): CliOpts {
  const o: CliOpts = { host: 'claude', topology: 'phase1-finding', worktree: false, json: true };
  for (let i = 0; i < argv.length; i++) {
    const a = argv[i];
    if (a === '--host') o.host = argv[++i];
    else if (a === '--topology') o.topology = argv[++i];
    else if (a === '--model') o.model = argv[++i];
    else if (a === '--ledger') o.ledger = argv[++i];
    else if (a === '--args-file') o.argsFile = argv[++i];
    else if (a === '--worktree') o.worktree = true;
    else if (a === '--text') o.json = false;
  }
  return o;
}

// CLI-adapter hosts only — no npm dep needed (the warm SDK adapters are opt-in extras).
export const ADAPTERS: Record<string, (model?: string) => SpawnAdapter> = {
  claude: (model) => new ClaudeCliAdapter({ model }),
  codex: (model) => new CodexCliAdapter({ model }),
  opencode: (model) => new OpencodeCliAdapter({ model }),
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
    repoRoot?: string;
  },
): Promise<unknown> {
  const adapters = deps?.adapters ?? ADAPTERS;
  const topologies = deps?.topologies ?? TOPOLOGIES;
  const makeAdapter = adapters[opts.host];
  if (!makeAdapter) {
    throw new Error(`unknown --host "${opts.host}" (have: ${Object.keys(adapters).join(', ')})`);
  }
  const topo = topologies[opts.topology];
  if (!topo) {
    throw new Error(`unknown --topology "${opts.topology}" (have: ${Object.keys(topologies).join(', ')})`);
  }
  const args = deps?.args ?? (opts.argsFile ? JSON.parse(readFileSync(opts.argsFile, 'utf8')) : {});

  let adapter = makeAdapter(opts.model);
  if (opts.worktree || WRITE_TOPOLOGIES.has(opts.topology)) {
    adapter = new WorktreeAdapter(adapter, { repoRoot: deps?.repoRoot ?? process.cwd() });
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
