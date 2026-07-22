/**
 * CLI entry — run a topology against a host and print the result as JSON.
 *
 * Invocation model (design §10, resolved without a new fork): the engine is PURE and never speaks
 * MCP. A skill/command running INSIDE a host session invokes this —
 *   node --experimental-strip-types workflow/cli.ts --host <self> --topology phase1-finding
 * — the engine drives sub-invocations of that host's OWN cli (claude -p / codex exec / opencode run)
 * and prints the surviving pins as JSON. The calling agent then writes them with the `ledger_add_pin`
 * MCP tool it already holds. So the engine needs no MCP client, and this path needs no npm deps —
 * only Node + the host cli. That is why the CLI is discovery/dry-run: it finds, it does not write.
 */
import { pathToFileURL } from 'node:url';
import { runWorkflow } from './engine.ts';
import type { SpawnAdapter } from './adapter.ts';
import { ClaudeCliAdapter } from './adapter.ts';
import { CodexCliAdapter } from './adapters/codex.ts';
import { OpencodeCliAdapter } from './adapters/opencode.ts';
import { phase1Finding } from './topologies/phase1-finding.ts';
import type { WorkflowCtx } from './engine.ts';

export type CliOpts = {
  host: string;
  topology: string;
  model?: string;
  ledger?: string;
  json: boolean;
};

export function parseArgs(argv: string[]): CliOpts {
  const o: CliOpts = { host: 'claude', topology: 'phase1-finding', json: true };
  for (let i = 0; i < argv.length; i++) {
    const a = argv[i];
    if (a === '--host') o.host = argv[++i];
    else if (a === '--topology') o.topology = argv[++i];
    else if (a === '--model') o.model = argv[++i];
    else if (a === '--ledger') o.ledger = argv[++i];
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

export const TOPOLOGIES: Record<string, (wf: WorkflowCtx) => Promise<unknown>> = {
  'phase1-finding': (wf) => phase1Finding(wf),
};

export async function runCli(
  opts: CliOpts,
  deps?: {
    adapters?: Record<string, (model?: string) => SpawnAdapter>;
    topologies?: Record<string, (wf: WorkflowCtx) => Promise<unknown>>;
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
  const { result } = await runWorkflow(topo, {
    adapter: makeAdapter(opts.model),
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
