# Phase 1 — Comprehension (build the as-is)

Produce a navigable, visual-first map of what the code IS now, with problems pinned on it.
The user will review pins, never the whole wiki. Attention scales with the number of
problems, not codebase size.

## Step 1 — Knowledge graph (backbone)

Build a local, multi-language graph with `graph-build`. Backbone = **Graphify** (MIT;
models DB schema as nodes; spans DB<->API<->frontend; plain NetworkX `graph.json` with stable
node ids + `source_location` + confidence tags). GitNexus is optional/secondary only
(noncommercial license; code-structure only). The semantic pass can run local via Ollama. This is what lets every later step stay in bounded context — you query the
graph instead of reading files one by one, which is the state-of-the-art answer to
auditing something too large to hold in one context window.

Requirements:
- **Stable node IDs.** Graphify's `graph.json` gives each node an `id` + `source_file` +
  `source_location`; anchor pins to these directly (no MCP round-trip needed).
- **Cross-layer edges = HINTS, not facts.** Graphify links DB<->ORM<->API<->frontend, but
  those edges are the INFERRED tier. Use them to know *which* entities to compare; the
  contract-reconciliation module computes the field-level shape diff itself from the anchored
  source locations.
- **"Why" nodes** (Graphify idea): NOTE/WHY/HACK comments, docstrings, design rationale as
  separate nodes. These feed spec reconstruction — the only in-code trace of intent, and
  even that is treated as a hint, not authority.
- **Confidence tags** on relationships (`extracted`/`inferred`/`ambiguous`) → propagate to
  pin `confidence`, which the severity threshold uses.

## Step 2 — As-is wiki (visual-first, descriptive)

Generate with `wiki-asis` (CodeWiki; subscription mode runs on the Claude login). This
documents the mess AS IT IS. It is never the to-be. Visual vocabulary:

- Architecture map (from the graph) — node-link, problem nodes highlighted.
- ER diagram of the DB with conflicting columns flagged.
- Contract-diff panels — three columns DB │ API │ Frontend, divergent field in red.
- Sequence diagrams for flows — arrows that end in nothing ARE the unfinished work,
  visually obvious.
- Hotspot heatmap (churn × complexity) and coupling overlay.
- Completeness traffic-light on the map: exists / stub / missing.

Rule: the wiki is a map with pins, not prose to read start-to-finish. Judgment and the
"why" are the only text, kept minimal and on-demand behind each pin — never compressed into
an icon (that empties them of the content the skill is supposed to deliver).

Output artifact is interactive (React + a graph lib: react-flow / cytoscape / d3), not
static Markdown — clickable nodes carry state, a side panel shows each pin's minimal text +
linked interview question + a "brainstorm" button. (Mermaid from CodeWiki is fine for the
static diagrams inside it.)

## Step 3 — Deterministic findings + analysis modules

Run the tools in `references/toolchain.md` and the Phase-1 modules in `modules.json`. Emit
ONE normalized findings stream (SARIF/JSON) so the fp-check gate and the interview operate
on a single format. Order of value for a slop rescue:
1. `contract-reconciliation` (core — read its full playbook)
2. `completeness` (distinguish stub / missing / done — prevents false alarms on unfinished
   work)
3. `placeholder-stub`, then the defect/maintainability/correctness modules.

Every candidate finding passes the **`fp-check` gate** before it becomes a surfaced pin. AI
over-reports; this gate is non-negotiable.

## Step 4 — Materialize pins

For each surviving finding, write a `Pin` (schema: `core/ledger.md`):
- Discriminated by `kind`; `as_is` in the kind-specific shape.
- `anchors[]` = one entry per involved layer (cross-layer), with `role` and `loc`.
- `confidence` from the graph/tool provenance.
- `severity` — remember blocker/high can never later go to silent default.
- `cluster_id` — collapse N instances of one decision into one, so Phase 2 asks once.
- `is_intentional_stub` set on `incompleteness` pins so the map renders them neutral, not
  as errors.

## Output

`ledger.json` populated with pins (state `detected` → `needs_input` once questions are
generated), the interactive as-is wiki, and the queryable graph. These three artifacts are
what Phase 2 reads — Phase 1 does not carry conversational state forward.
