/**
 * The two MCP Apps' JavaScript, parsed and RUN — run with:
 *   node --experimental-strip-types src/workflow/__tests__/mcp-apps.ts
 *
 * Why this file exists: the JS was linted by nothing
 * --------------------------------------------------
 * `src/mcp/apps.py` holds the interview app's script as a Python raw string and `src/runtime/map.py`
 * holds the map's as a `_TEMPLATE` fragment. Both ship. Neither was ever handed to a JavaScript
 * engine by anything in this repo: every gate around them — `test_the_interview_app_never_builds_dom
 * _from_a_string`, `test_the_map_apps_wrapper_adds_no_second_markup_sink`, the whole of
 * `tests/test_map.py` — reads the bytes as TEXT. So a missing brace, a typo'd identifier, or a
 * renderer that throws on the first pin would have passed every one of them, shipped, and failed in
 * the user's host by rendering a blank page. `tests/test_map.py` says as much in its own docstring:
 * the DOM half is "verified rendered in a browser — repeatably, via `python scripts/preview_map.py`",
 * which is a human at a terminal, and it warns that source-text matching "would pass on a renderer
 * that never runs". This is that renderer, run.
 *
 * Blank is the specific failure both apps are most exposed to and least able to report. The map
 * swallows a build error into `cannotRender` by design — a card that says so rather than an empty
 * pane — so a renderer broken inside `detail()` is not merely silent, it is *green* under every
 * existing check. `the map renders every pane without reaching its own failure card` below is the
 * assertion that costs that bug its silence.
 *
 * Why it lives in `src/workflow/__tests__/`
 * -----------------------------------------
 * This repo has exactly one node toolchain — the workflow engine's — and CI has exactly one node
 * job. A second package for one gate would be a second toolchain to keep, for a file that is not
 * product code. `build.py` skips `__tests__` when it vendors the engine into `keel-core`, so
 * nothing here reaches `plugins/` and adding it moved no shipped byte.
 *
 * The stub DOM, and what it deliberately does NOT do
 * --------------------------------------------------
 * Hand-rolled, no `jsdom`: the suite beside this one has zero runtime dependencies and CI installs
 * nothing for it, which is a property worth more than the fidelity a parser would buy. The stub
 * therefore **does not parse HTML** — an element's `innerHTML` is a recorded string, not a tree.
 * That is stated because it decides how the hostile cases are asserted, and the two apps are
 * asserted differently for the same reason `apps.py` gates them differently:
 *
 *   * the **interview app** never writes markup, so its guarantee is that content reaches the
 *     document through `textContent` alone — here the stub's `innerHTML` setter *throws*, and the
 *     hostile strings must still come back out of the text tree intact;
 *   * the **map app** writes markup through exactly one sink, so its guarantee is that what enters
 *     that sink is escaped — here the sink records, and the hostile strings must arrive at it with
 *     their angle brackets already entities.
 *
 * A stub that parsed HTML would let the first of those be written as "no `<img>` node appeared",
 * which is a claim about the parser rather than about the app.
 *
 * `node:vm`, not `new Function`: a `<script>` body is parsed as a *script*, and `new Function`
 * parses a function body — where a stray top-level `return` is legal. `vm.Script` rejects what a
 * browser rejects, and the same object then runs, so the parse gate and the render gate are one
 * mechanism rather than two that can disagree.
 */
import assert from 'node:assert/strict';
import { spawnSync } from 'node:child_process';
import { mkdtempSync, readFileSync, rmSync } from 'node:fs';
import { tmpdir } from 'node:os';
import path from 'node:path';
import { fileURLToPath } from 'node:url';
import vm from 'node:vm';

const HERE = path.dirname(fileURLToPath(import.meta.url));
const ROOT = path.resolve(HERE, '..', '..', '..');
const RENDERER = path.join(HERE, 'render-app-documents.py');

let passed = 0;
let failed = 0;

function test(name: string, fn: () => void): void {
  try {
    fn();
    passed++;
    console.log(`  ✓ ${name}`);
  } catch (e) {
    failed++;
    console.log(`  ✗ ${name}\n      ${e instanceof Error ? e.message : String(e)}`);
  }
}

// ---------------------------------------------------------------------------------------------
// The documents. Rendered by the Python beside this file, so what is checked below is the bytes a
// host receives rather than a constant read out of a source file.
// ---------------------------------------------------------------------------------------------

type DocSpec = { name: string; file: string; app: 'interview' | 'map'; hostile: string[] };

/**
 * The interpreter is CHOSEN and then NAMED, in that order, and the naming is not politeness.
 * This repo has a recorded incident where a bare command resolved to a different Python than the
 * one the operator believed they had, and 21 tests skipped green behind it. So: `$PYTHON` if it is
 * set, else `python3`, else `python` — and whichever answered is printed with its version, because
 * the one thing that incident cost was the ability to tell which interpreter produced the run.
 */
function interpreter(): { cmd: string; banner: string } {
  const candidates = process.env.PYTHON ? [process.env.PYTHON] : ['python3', 'python'];
  const tried: string[] = [];
  for (const cmd of candidates) {
    const probe = spawnSync(cmd, ['-c', 'import sys; print(sys.version.split()[0], sys.executable)'], {
      encoding: 'utf8',
    });
    if (!probe.error && probe.status === 0) {
      return { cmd, banner: `${cmd} -> ${probe.stdout.trim()}` };
    }
    tried.push(cmd);
  }
  throw new Error(
    `no usable Python (tried: ${tried.join(', ')}). The two apps' documents are rendered by ` +
      `src/mcp/apps.py and src/runtime/map.py; set PYTHON= to name an interpreter.`,
  );
}

function render(): { dir: string; docs: DocSpec[] } {
  const dir = mkdtempSync(path.join(tmpdir(), 'keel-apps-'));
  const { cmd, banner } = interpreter();
  console.log(`  renderer: ${banner}`);
  const proc = spawnSync(cmd, [RENDERER, dir], { cwd: ROOT, encoding: 'utf8' });
  if (proc.error || proc.status !== 0) {
    throw new Error(
      `could not render the app documents with \`${cmd}\`:\n` +
        `${proc.error ? proc.error.message : ''}${proc.stderr ?? ''}`,
    );
  }
  const manifest = JSON.parse(readFileSync(path.join(dir, 'manifest.json'), 'utf8')) as {
    documents: DocSpec[];
  };
  return { dir, docs: manifest.documents };
}

/**
 * Every `<script>` in a document, by index scan.
 *
 * Deliberately dumb — no HTML parser, no regex cleverness — and honest about it: it finds the tag,
 * takes what is between `>` and the next `</script>`, and refuses anything it cannot account for.
 * The refusals are the honesty. An unclosed block or a `src=` attribute means there is JavaScript
 * in this document that this gate is not looking at, and a gate that quietly checks less than it
 * claims is the failure mode the whole file is written against.
 */
function scriptBlocks(html: string, where: string): string[] {
  const out: string[] = [];
  let i = 0;
  for (;;) {
    const open = html.indexOf('<script', i);
    if (open === -1) break;
    const gt = html.indexOf('>', open);
    assert.ok(gt !== -1, `${where}: a <script tag that never ends`);
    const attrs = html.slice(open + '<script'.length, gt);
    assert.ok(
      !/\bsrc\s*=/.test(attrs),
      `${where}: a <script src=…> carries JS this gate cannot read (and an app that fetches ` +
        `breaks the csp.resourceDomains: [] both documents declare)`,
    );
    const close = html.indexOf('</script>', gt);
    assert.ok(close !== -1, `${where}: an unclosed <script> — the rest of the document is script data`);
    out.push(html.slice(gt + 1, close));
    i = close + '</script>'.length;
  }
  assert.ok(out.length > 0, `${where}: no inline script at all — an app document with no behaviour`);
  return out;
}

/** The ids the *markup* declares, so `getElementById` can answer null for anything else. */
function declaredIds(html: string): Set<string> {
  const markupOnly = html.replace(/<script[\s\S]*?<\/script>/g, '');
  const ids = new Set<string>();
  for (const m of markupOnly.matchAll(/\sid=["']([^"']+)["']/g)) ids.add(m[1]);
  return ids;
}

// ---------------------------------------------------------------------------------------------
// The stub DOM.
// ---------------------------------------------------------------------------------------------

class StubClassList {
  names = new Set<string>();
  add(...n: string[]): void {
    for (const x of n) this.names.add(x);
  }
  remove(...n: string[]): void {
    for (const x of n) this.names.delete(x);
  }
  contains(n: string): boolean {
    return this.names.has(n);
  }
  toggle(n: string, on?: boolean): boolean {
    const want = on === undefined ? !this.names.has(n) : on;
    if (want) this.names.add(n);
    else this.names.delete(n);
    return want;
  }
}

class StubElement {
  tagName: string;
  className = '';
  disabled = false;
  style: Record<string, string> = {};
  classList = new StubClassList();
  children: StubElement[] = [];
  attrs: Record<string, string> = {};
  listeners: Record<string, Array<(ev: unknown) => void>> = {};
  own = '';
  markup: string | null = null;
  onMarkup: (el: StubElement, html: string) => void;

  constructor(tagName: string, onMarkup: (el: StubElement, html: string) => void) {
    this.tagName = tagName.toUpperCase();
    this.onMarkup = onMarkup;
  }

  get textContent(): string {
    return this.own + this.children.map((c) => c.textContent).join('');
  }
  set textContent(v: unknown) {
    this.children = [];
    this.own = v === null || v === undefined ? '' : String(v);
  }
  get innerHTML(): string {
    return this.markup ?? '';
  }
  set innerHTML(v: unknown) {
    const html = String(v);
    this.onMarkup(this, html);
    this.markup = html;
    this.children = [];
  }
  appendChild(n: StubElement): StubElement {
    this.children.push(n);
    return n;
  }
  replaceChildren(...n: StubElement[]): void {
    this.children = n;
  }
  addEventListener(type: string, fn: (ev: unknown) => void): void {
    (this.listeners[type] ??= []).push(fn);
  }
  removeEventListener(): void {}
  setAttribute(k: string, v: string): void {
    this.attrs[k] = String(v);
  }
  getAttribute(k: string): string | null {
    return k in this.attrs ? this.attrs[k] : null;
  }
  /** Every element in this subtree, self first — the harness's own reader, not part of the DOM. */
  walk(): StubElement[] {
    return [this as StubElement, ...this.children.flatMap((c) => c.walk())];
  }
}

type Harness = {
  ctx: vm.Context;
  byId: Map<string, StubElement>;
  posted: unknown[];
  timers: Array<{ delay: number }>;
  windowListeners: Record<string, Array<(ev: unknown) => void>>;
  /** Every string written to a markup sink, in write order. */
  written: Array<{ id: string; html: string }>;
  errors: string[];
};

/**
 * `sink: 'record' | 'forbid'` is the whole difference between how the two apps are checked, and it
 * is a parameter rather than two harnesses because the property is the same one seen from two
 * sides: markup either does not happen here, or it happens escaped.
 */
function harness(html: string, sink: 'record' | 'forbid'): Harness {
  const ids = declaredIds(html);
  const byId = new Map<string, StubElement>();
  const posted: unknown[] = [];
  const timers: Array<{ delay: number }> = [];
  const windowListeners: Record<string, Array<(ev: unknown) => void>> = {};
  const written: Array<{ id: string; html: string }> = [];
  const errors: string[] = [];

  const onMarkup = (el: StubElement, markup: string): void => {
    if (sink === 'forbid') {
      throw new Error(
        'this document wrote markup into the document. The interview app has no markup sink by ' +
          'design — every string it renders is agent-authored content out of someone else\'s repo ' +
          'and goes in through textContent',
      );
    }
    let id = '?';
    for (const [k, v] of byId) if (v === el) id = k;
    written.push({ id, html: markup });
  };

  const make = (tag: string): StubElement => new StubElement(tag, onMarkup);
  for (const id of ids) byId.set(id, make('div'));

  const document = {
    documentElement: make('html'),
    body: make('body'),
    createElement: (tag: string) => make(tag),
    createTextNode: (t: string) => {
      const n = make('#text');
      n.own = String(t);
      return n;
    },
    // null for an undeclared id, exactly as a browser answers: the JS then throws on the property
    // access, which is the bug (a pane the markup no longer has) reported instead of papered over.
    getElementById: (id: string) => byId.get(id) ?? null,
    querySelector: () => null,
    querySelectorAll: () => [],
    addEventListener: (type: string, fn: (ev: unknown) => void) => {
      (windowListeners[type] ??= []).push(fn);
    },
  };

  const sandbox: Record<string, unknown> = {
    document,
    console: { log: () => {}, warn: () => {}, error: (m: unknown) => errors.push(String(m)) },
    // Recorded and never fired. The bridge arms a 15s rejection timer on every call; a real timer
    // would make this gate wait for it, and firing it would test node's clock rather than the app.
    setTimeout: (_fn: unknown, delay?: number) => {
      timers.push({ delay: delay ?? 0 });
      return timers.length;
    },
    clearTimeout: () => {},
    addEventListener: (type: string, fn: (ev: unknown) => void) => {
      (windowListeners[type] ??= []).push(fn);
    },
    removeEventListener: () => {},
    parent: { postMessage: (msg: unknown) => posted.push(msg) },
    location: { href: 'about:blank' },
  };
  sandbox.window = sandbox;
  sandbox.self = sandbox;

  return {
    ctx: vm.createContext(sandbox),
    byId,
    posted,
    timers,
    windowListeners,
    written,
    errors,
  };
}

/** Parse as a script (what a browser does), then run it. Two steps, one parser. */
function parseAndRun(js: string, filename: string, h: Harness): void {
  const script = new vm.Script(js, { filename });
  script.runInContext(h.ctx);
}

function deliver(h: Harness, method: string, params: unknown): void {
  const listeners = h.windowListeners.message ?? [];
  assert.ok(listeners.length > 0, 'the app registered no `message` listener — no host can reach it');
  for (const fn of listeners) fn({ data: { jsonrpc: '2.0', method, params } });
}

// ---------------------------------------------------------------------------------------------
// The interview funnel payloads. These arrive at RUNTIME over postMessage rather than baked into
// the document, so they belong here rather than in the renderer beside this file.
// ---------------------------------------------------------------------------------------------

const WELLFORMED_FUNNEL = {
  asked: [
    {
      pin_id: 'pin_0002',
      title: 'which store backs the session cache',
      severity: 'blocker',
      prompt: 'Where should sessions live?',
      downstream: 2,
      options: [
        { id: 'redis', label: 'Redis', implication: 'one more service to operate' },
        { id: 'pg', label: 'Postgres', implication: 'no new service, slower reads' },
      ],
      allow_freeform: true,
      proposals: [{ id: 'bs_1', summary: 'start on Postgres', effort: 'S', recommended: true }],
    },
    {
      pin_id: 'pin_0001',
      title: 'the API returns a string where the DB holds an integer',
      severity: 'high',
      prompt: 'Which layer is the authority?',
      blocked_by: 'pin_0002',
      options: [],
      proposals: [],
    },
  ],
};

const HOSTILE_MARKUP = '</script><img src=x onerror=alert(1)>';
const HOSTILE_FENCE = 'A <!--<script> double escape';

const HOSTILE_FUNNEL = {
  asked: [
    {
      pin_id: HOSTILE_MARKUP,
      title: HOSTILE_FENCE,
      // Not one of the four the closed table names — the branch that must fall back rather than
      // put a content-controlled value into a class attribute.
      severity: HOSTILE_MARKUP,
      prompt: `<b>bold</b> ${HOSTILE_FENCE}`,
      downstream: 3,
      blocked_by: HOSTILE_MARKUP,
      options: [{ id: 'x', label: '<b>bold label</b>', implication: HOSTILE_MARKUP }],
      allow_freeform: true,
      proposals: [{ id: 'p', summary: HOSTILE_FENCE, effort: '<i>M</i>', recommended: true }],
      already_elected: { outcome: HOSTILE_MARKUP },
      pin_state: HOSTILE_FENCE,
    },
  ],
};

// ---------------------------------------------------------------------------------------------
// The run.
// ---------------------------------------------------------------------------------------------

const { dir, docs } = render();
try {
  console.log('MCP apps — JavaScript parse + render');

  // -- (a) every app's every script block parses ------------------------------------------------
  for (const doc of docs) {
    const html = readFileSync(path.join(dir, doc.file), 'utf8');
    test(`${doc.name}: every inline script parses as a script`, () => {
      const blocks = scriptBlocks(html, doc.name);
      blocks.forEach((js, n) => {
        new vm.Script(js, { filename: `${doc.file}#script[${n}]` });
      });
    });
  }

  // -- (b) the interview app renders, and renders hostile content as text -----------------------
  const interviewDoc = docs.find((d) => d.app === 'interview');
  assert.ok(interviewDoc, 'the manifest lists no interview app');
  const interviewHtml = readFileSync(path.join(dir, interviewDoc.file), 'utf8');
  const interviewJs = scriptBlocks(interviewHtml, 'interview app').join('\n');

  function bootInterview(): Harness {
    const h = harness(interviewHtml, 'forbid');
    parseAndRun(interviewJs, 'interview.html#script', h);
    return h;
  }

  test('the interview app boots and handshakes with the host', () => {
    const h = bootInterview();
    // The stub creates a declared id as an EMPTY element — it does not parse the markup — so the
    // proof that the script ran to its last statement is the wiring it leaves behind, not the
    // static text the document already carried.
    assert.equal((h.byId.get('refresh')!.listeners.click ?? []).length, 1,
      'the Re-read button was never wired; the script did not reach its end');
    const first = h.posted[0] as { method: string; params: { protocolVersion: string } };
    assert.equal(first.method, 'ui/initialize',
      'the view must open the extension handshake; a host sees an app that never speaks');
    assert.equal(first.params.protocolVersion, '2026-01-26',
      'the handshake must carry the APPS revision, not the core protocol\'s');
  });

  test('the interview app renders a well-formed funnel', () => {
    const h = bootInterview();
    deliver(h, 'ui/notifications/tool-result', {
      structuredContent: WELLFORMED_FUNNEL,
      arguments: { ledger: '/repo/ledger.json' },
    });
    const funnel = h.byId.get('funnel')!;
    assert.equal(funnel.children.length, 2, 'one card per asked question');
    const text = funnel.textContent;
    for (const want of [
      'which store backs the session cache',
      'Where should sessions live?',
      '2 pin(s) downstream wait on this answer',
      'Redis',
      'one more service to operate',
      'brainstorm proposals',
      'blocked by: pin_0002',
    ]) {
      assert.ok(text.includes(want), `the rendered funnel never shows ${JSON.stringify(want)}`);
    }
    assert.ok(
      funnel.walk().some((el) => el.className === 'sev sev-blocker'),
      'severity is styled off a closed class list; the blocker card carries no blocker class',
    );
    assert.equal(h.byId.get('ledger')!.textContent, '/repo/ledger.json');
  });

  test('the interview app renders an empty funnel as a statement, not as a blank pane', () => {
    const h = bootInterview();
    deliver(h, 'ui/notifications/tool-result', { structuredContent: { asked: [] } });
    assert.match(h.byId.get('funnel')!.textContent, /No open questions/);
  });

  test('the interview app puts hostile content in as text and nowhere else', () => {
    // The harness throws from any markup sink, so reaching the end of this render IS the
    // assertion that no string became markup — the executed twin of the grep in
    // tests/test_mcp_server.py::test_the_interview_app_never_builds_dom_from_a_string.
    const h = bootInterview();
    deliver(h, 'ui/notifications/tool-result', { structuredContent: HOSTILE_FUNNEL });
    const funnel = h.byId.get('funnel')!;
    assert.equal(funnel.children.length, 1, 'the hostile card did not render at all');
    const text = funnel.textContent;
    for (const want of [HOSTILE_FENCE, HOSTILE_MARKUP, '<b>bold label</b>']) {
      assert.ok(text.includes(want),
        `${JSON.stringify(want)} was dropped or rewritten instead of shown as text`);
    }
    for (const el of funnel.walk()) {
      assert.ok(!el.className.includes('<'),
        `content reached a class attribute: ${JSON.stringify(el.className)}`);
      assert.ok(!/^(IMG|SCRIPT|IFRAME|B|I)$/.test(el.tagName),
        `the app created a <${el.tagName.toLowerCase()}> from content`);
    }
    assert.ok(
      funnel.walk().some((el) => el.className === 'sev sev-low'),
      'a severity outside the closed table must fall back to `low`, not be interpolated',
    );
  });

  // -- (c) the map app renders every pane, on a well-formed ledger and on a hostile one ----------
  for (const doc of docs.filter((d) => d.app === 'map')) {
    const html = readFileSync(path.join(dir, doc.file), 'utf8');
    const js = scriptBlocks(html, doc.name).join('\n');

    test(`${doc.name}: renders every pane without reaching its own failure card`, () => {
      const h = harness(html, 'record');
      parseAndRun(js, `${doc.file}#script`, h);
      for (const id of ['list', 'detail']) {
        const el = h.byId.get(id);
        assert.ok(el, `the page has no #${id} — the markup and the script disagree`);
        assert.ok(el.innerHTML.length > 0, `#${id} rendered nothing at all`);
      }
      assert.ok(h.byId.get('tltext')!.textContent.length > 0, 'the traffic light says nothing');
      assert.match(h.byId.get('prog')!.style.width ?? '', /^\d+%$/,
        'the progress bar never got a width');
      for (const w of h.written) {
        assert.ok(!w.html.includes('this map could not render this'),
          `#${w.id} fell into map.py's cannotRender card — the renderer threw while building it, ` +
            `which every text-matching gate reads as green`);
      }
    });

    if (doc.hostile.length === 0) continue;

    test(`${doc.name}: hostile strings reach the one sink already escaped`, () => {
      const h = harness(html, 'record');
      parseAndRun(js, `${doc.file}#script`, h);
      const all = h.written.map((w) => w.html).join('\n');
      assert.ok(all.length > 0, 'nothing was written to the document');
      for (const raw of doc.hostile) {
        assert.ok(!all.includes(raw),
          `${JSON.stringify(raw)} reached the markup sink unescaped — map.py's tagged template ` +
            `is the only thing between a pin title and a live node`);
      }
      // Openers the page's OWN template never emits, so their presence can only be content. `<b>`
      // is deliberately not on this list: `map.py` writes real `<b>` tags of its own, and a check
      // that cannot tell the page's markup from the ledger's would fail on a correct renderer.
      // The ledger's own `<b>` is covered above, by the raw-string pass over `doc.hostile`.
      for (const opener of ['<img', '<script', '<!--<script', '<iframe']) {
        assert.ok(!all.toLowerCase().includes(opener),
          `${opener} appears as markup in the rendered page`);
      }
      // ...and the escape did not simply delete the data, which is the other way to pass.
      assert.ok(all.includes('&lt;img src=x onerror=alert(1)&gt;'),
        'the hostile severity is nowhere on the page, escaped or otherwise — an escape that ' +
          'loses the value is not an escape');
      assert.ok(all.includes('&lt;!--&lt;script&gt;'),
        'the double-escape payload is not on the page as text');
    });
  }
} finally {
  rmSync(dir, { recursive: true, force: true });
}

console.log(`\n${passed} passed, ${failed} failed`);
if (failed > 0) process.exitCode = 1;
