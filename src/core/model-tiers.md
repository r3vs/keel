# Model tiers — the roster's model policy, one source, generated per host

Sibling of `agents.md`. That file classifies each role by **cognitive demand** (a `tier`); this file
resolves a tier to a concrete **model + reasoning effort**, once per **profile**, and `build.py`
derives each host's adapter from it — exactly as it derives the write-permission mechanism from the
roster's permission lines. There is nothing to keep in sync, because there is no second copy: change
a cell here and every host that ships that profile changes with it, or `build.py --check` fails.

## The one idea: bind the model to the ROLE, not to the task

A `task → model` matrix is a heuristic — it asks the agent to guess how hard the work is, which is
the exact guessing this package forbids. But the roster already encodes the demand: the `challenger`
refutes an oracle (the hardest reasoning in the system), the `executor` implements one bounded scope
(high volume, well-scoped), the `researcher` reads at fan-out (cheap, parallel). So the tier is a
property of the **role**, known deterministically, and the model follows from `(tier, profile)`. No
task inspection, no heuristic.

Escalation is not a heuristic either: the `executor` moves up a tier **only** on a ledger signal — a
`reviewer` `REJECT` twice, or an unmet `acceptance_criterion` — never on a vibe that the item "feels
hard". Escalation is a runtime decision on observed evidence, so it is **not** emitted into any
adapter; the adapters carry the steady-state default only.

## Tiers (defined in `agents.md`, repeated here for the reader)

| Tier | Demand | Roles | Volume |
|------|--------|-------|--------|
| **T3** | deepest reasoning; refute an oracle | `challenger` | rare |
| **T2** | judgment; find real bugs; propose | `reviewer`, `brainstorm` | medium |
| **T1** | bounded implementation (the one writer) | `executor` | **high — the grind** |
| **T0** | read / verify at fan-out | `researcher`, `measurer` | high |

The **orchestrator** (the main loop) is not a roster subagent and has no tier. On hosts where a
plugin cannot set the main-loop model (Claude Code — verified), it is *guidance* (`/model`), not
emitted config. On hosts where the primary agent's model is configurable (opencode/Pi), it is set.

## The parse contract (so this doc and `build.py` cannot disagree)

`build.py` reads the profile blocks below. The rules, exact:

- A profile starts at a heading `## Profile <LETTER> · <provider-id> — <host(s)>`.
- Inside it, each assignment is a list line:  `` - `<role>` → `<model>` · `<effort>` ``
  where `<effort>` is optional (omit the `` · `…` `` for a role whose host takes no effort field).
- `<model>` is a bare alias (`opus`) or a `provider/model-id` (`opencode-go/glm-5.2`, `openai/gpt-5.6-sol`).
- A role absent from a profile gets **no `model:` line at all**, so the host falls back to its own
  default (the session model) — a missing row is graceful degradation, never an error. The adapter
  never writes `inherit`: it is a Claude-only keyword that opencode/Pi reject (study finding E1).

Effort does **not** map 1:1 across providers, so each cell states the effort **in that host's own
vocabulary**: Claude `low|medium|high|xhigh` (no `max` — session-only), opencode `reasoningEffort`
`minimal|low|medium|high|xhigh`, Codex `model_reasoning_effort` `low|medium|high`. GLM-5.2's native
`high|max` is mapped onto opencode's `high|xhigh`.

---

## Profile A · anthropic — Claude Code

Per-subagent `model:` + `effort:` in `agents/<role>.md`. Orchestrator is `/model` (opus default,
fable for the hardest projects) — the plugin cannot set it.

- `challenger` → `fable` · `xhigh`
- `reviewer` → `opus` · `high`
- `brainstorm` → `opus` · `high`
- `executor` → `sonnet` · `high`
- `researcher` → `sonnet` · `low`
- `measurer` → `sonnet` · `low`

## Profile B · openai — Codex (also opencode/Pi if you bind pure-OpenAI)

`model` + `model_reasoning_effort` in `.codex/agents/<role>.toml`. GPT-5.6 tiers Sol/Terra/Luna.
The exact model-id strings are account- and version-specific — **confirm against your own
`codex` model list**; these are the intended tiers, not verified string literals.

- `challenger` → `gpt-5.6-sol` · `high`
- `reviewer` → `gpt-5.6-sol` · `high`
- `brainstorm` → `gpt-5.6-terra` · `high`
- `executor` → `gpt-5.6-terra` · `medium`
- `researcher` → `gpt-5.6-luna` · `low`
- `measurer` → `gpt-5.6-luna` · `low`

## Profile C · opencode-go — opencode/Pi (open-weight, one $10 sub)

`model: opencode/<id>` + `reasoningEffort` per agent. Reserve the dear models (GLM-5.2) for the rare
high-stakes gates; the cheap workhorse (MiniMax M3) absorbs the volume — a cheap writer is safe
because the strong readers are the gate. `orchestrator` is the primary agent.

- `orchestrator` → `opencode-go/kimi-k3`
- `challenger` → `opencode-go/glm-5.2` · `xhigh`
- `reviewer` → `opencode-go/glm-5.2` · `high`
- `brainstorm` → `opencode-go/glm-5.2` · `high`
- `executor` → `opencode-go/minimax-m3` · `medium`
- `researcher` → `opencode-go/minimax-m3` · `low`
- `measurer` → `opencode-go/minimax-m3` · `low`

## Profile D · mixed — opencode/Pi (best-of-both, needs both the $10 Go sub AND ChatGPT-sub auth)

The state-of-the-art profile for two subscriptions. Two design ideas beyond picking models:

1. **Cross-provider adversarial gating.** The `executor` runs on one family (Go), and the
   `reviewer`/`challenger` that check it run on another (OpenAI). A same-family checker shares the
   writer's blind spots; a cross-family checker catches the errors one family makes systematically.
   This is the whole point of the adversarial roster, made stronger.
2. **Quota-arbitrage across two flat pools.** Go ($10 sub) and OpenAI (ChatGPT sub) are independent
   quotas. The two high-volume clusters (`executor` vs `researcher`/`measurer`) sit on **different**
   pools, so neither drains first; and if one is rate-limited the other still serves its roles.

Pool Go = orchestrator + executor + brainstorm · Pool OpenAI = reviewer + challenger + researcher +
measurer. The `executor`'s escalation target is `gpt-5.6-sol` — jumping *family*, not just effort.
OpenAI model-ids arrive via the opencode codex-auth plugin and may lag native Sol/Terra/Luna
(the backend has surfaced `gpt-5.x-codex`); **confirm against your authed model list**.

- `orchestrator` → `opencode-go/kimi-k3`
- `challenger` → `openai/gpt-5.6-sol` · `high`
- `reviewer` → `openai/gpt-5.6-sol` · `high`
- `brainstorm` → `opencode-go/glm-5.2` · `high`
- `executor` → `opencode-go/minimax-m3` · `medium`
- `researcher` → `openai/gpt-5.6-luna` · `low`
- `measurer` → `openai/gpt-5.6-luna` · `low`

---

## Which host ships which profile, and how it is delivered

| Host | Profile | Delivered by | Granularity |
|------|---------|--------------|-------------|
| Claude Code | **A** | the plugin's `agents/<role>.md` frontmatter (marketplace install) | per-role |
| Codex | **B** | `scripts/install.sh` → `~/.codex/agents/<role>.toml` (auto-discovered) — a Codex plugin manifest **cannot** carry agents | per-role |
| opencode | **C** | `scripts/install.sh` → `~/.config/opencode/agent/<role>.md` | per-role |
| Pi | — | **session-level only**: Pi's core is *"no sub-agents"*, so the roster runs in-session — set `defaultModel` + `defaultThinkingLevel` to the orchestrator tier | session |

Only Claude Code delivers per-role models through the marketplace plugin itself. Codex and opencode
ride `install.sh` (their plugin/host formats can't carry agents), and **Pi has no first-class subagents
at all** — there the profile is guidance for the session model, not a per-role adapter.

`C` is the opencode default (one $10 Go sub — the safe floor). **`D` (mixed) is recommended if you
have both subs**: strictly more powerful (cross-family gating + quota split), applied via the override
below.

## Override — native per-agent config, no custom layer (the "config, not logic" rule)

The shipped plugin bakes the default profile. To change the model of a role — or to switch opencode/Pi
from `C` to `D` — you do **not** edit the plugin: you drop your own per-agent file, which the host
loads with precedence over the plugin's:

- Claude Code → `.claude/agents/<role>.md` (`model:` / `effort:`)
- opencode → `.opencode/agents/<role>.md` (`model:` / `reasoningEffort:`) — e.g. copy the Profile `D` rows above
- Codex → `.codex/agents/<role>.toml` (`model` / `model_reasoning_effort`)
- Pi → `~/.pi/agent/settings.json` (`defaultModel` / `defaultThinkingLevel`); per-role would need a Pi
  subagent extension, which this package does not ship

The models here move fast; this is data, not code, and the override path is the host's own — so a new
model lands as one edited line, never a build change.
