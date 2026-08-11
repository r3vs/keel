<!-- GENERATED FILE - do not edit. Source: src/core/module-design.md at the repo root; regenerate with: python scripts/build.py -->

# Module design — the vocabulary for saying where a boundary goes (shared core)

This package has a lot of machinery for checking that layers **agree** — the field-shape engine
diffs them, the generators project them from one contract. None of it says where a boundary should
sit in the first place, or whether the one in front of you is earning its keep. That judgment needs
words, and words that drift are the reason two agents "agree" about a design and build different
things.

Use these terms exactly. Do not substitute *component*, *service*, *API* or *boundary* — each is
already overloaded somewhere the reader has been.

## Glossary

**Module** — anything with an interface and an implementation. Deliberately scale-agnostic: a
function, a class, a package, a tier-spanning slice. *Avoid*: unit, component, service.

**Interface** — everything a caller must know to use the module correctly. Not only the type
signature: also invariants, ordering constraints, error modes, required configuration, performance
characteristics. *Avoid*: API, signature — both name only the type-level surface, and the facts that
break callers usually are not on it.

**Implementation** — what is inside. Distinct from **adapter**: a thing can be a small adapter over
a large implementation (a Postgres repository) or a large adapter over a small one (an in-memory
fake).

**Depth** — leverage at the interface: how much behavior a caller or a test can exercise per unit of
interface it has to learn. **Deep** = a lot of behavior behind a small interface. **Shallow** = an
interface nearly as complex as what it hides.

**Seam** *(Michael Feathers)* — a place where behavior can be altered without editing in that place;
the *location* at which an interface lives. Where the seam goes is a separate decision from what
sits behind it, and conflating them is the most common way a design argument goes in circles.
*Avoid*: boundary — overloaded with DDD's bounded context.

**Adapter** — a concrete thing satisfying an interface at a seam. Names a *role* (which slot it
fills), never a substance (what is inside it).

**Leverage** — what callers get from depth: more capability per unit of interface learned. One
implementation paying back across N call sites and M tests.

**Locality** — what maintainers get from depth: change, bugs, knowledge and verification concentrate
in one place instead of spreading across callers. Fix once, fixed everywhere.

## Four tests, not four opinions

- **The deletion test.** Imagine the module gone. If complexity *vanishes*, it was a pass-through
  and was never earning its keep. If complexity *reappears, multiplied, across its callers*, it was.
  This is the one to reach for first, because it is answerable by reading the call sites rather than
  by taste.
- **The interface is the test surface.** Callers and tests cross the same seam. Wanting to test
  *past* the interface is the signal that the module is the wrong shape — not the signal that the
  test needs privileged access. `test-driven-development` states the operational half: no test is
  written at a seam nobody confirmed.
- **One adapter means a hypothetical seam; two adapters mean a real one.** Do not introduce a seam
  until something actually varies across it. This is the test that pushes back hardest on an agent's
  standing bias toward abstraction, so apply it out loud.
- **Depth is a property of the interface, not of the implementation.** A deep module can be composed
  internally of small swappable parts — they are simply not part of its interface. A module may have
  **internal seams** (private, used by its own tests) as well as the **external seam** at its
  interface, and only the second is a promise to anyone.

## Where this lands in the ledger

A depth finding is a **`design_concern` pin**, not a refactor you perform. That routing is the whole
point of having the vocabulary here rather than in one skill: the reviewer, the debugger and the
rescue module all reach the same words and all reach the same door. `accepted` is a legitimate
outcome — a shallow module the team has deliberately chosen is a decision, and recording it stops the
next survey re-proposing it.

Two signals this package already computes make the judgment cheaper, and both are `D0` facts rather
than opinions, in the trust-axes sense: the graph's **blast radius** says how far a change here travels
— a large radius behind a small interface is depth, a large radius behind a large one is the absence
of it — and **co-change** says which places have historically had to move together, which is locality
measured rather than asserted.

**Where the seam goes is elected, never inferred.** Deriving it from the shape of the existing code
is the same circularity this package refuses everywhere else: the as-is cannot supply the to-be. Put
the seam to the human as a fork with two or three concrete options, exactly as any other
`open_decision`.

## Designing it twice

Your first interface is unlikely to be your best one, and an agent's first is the most conventional
one — which is the same thing said less kindly. When the interface itself is the open question, run
the `brainstorm` role on it in parallel, one proposal per **radically different constraint**:

- minimise the interface — one to three entry points, maximum leverage per entry point;
- maximise flexibility — many use cases, room to extend;
- optimise for the most common caller — the default case becomes trivial;
- ports and adapters, when the seam crosses a process or a vendor.

Each proposal states its interface (including invariants, ordering, error modes), a usage example,
what it hides, and where its leverage is thin. Then compare on **depth**, **locality** and **seam
placement**, and give one recommendation with a reason — a menu handed to the human is work not
done. The role stays what it always is — it **proposes and never elects** — so the comparison ends at a
fork in the interview, not at a decision.

## Rejected framings

- **Depth as a ratio of implementation lines to interface lines** (Ousterhout's formulation):
  rewards padding the implementation, and would score a bloated module as a good one. Depth here is
  leverage, which is measured at the caller.
- **"Interface" as the language's `interface` keyword, or a class's public methods**: too narrow. The
  ordering constraint nobody wrote down is part of the interface, and it is usually the part that
  breaks people.
- **"Boundary"**: means bounded context to half your readers. Say **seam** or **interface**.

## Attribution

**Seam** is Michael Feathers (*Working Effectively with Legacy Code*). **Deep modules** and **design
it twice** are John Ousterhout (*A Philosophy of Software Design*), with the depth definition
deliberately changed as noted above. The glossary's shape — terms with explicit *avoid* lists, tests
rather than principles, and a rejected-framings section — is adapted with thanks from the
MIT-licensed `codebase-design` skill in [`mattpocock/skills`](https://github.com/mattpocock/skills).
The ledger routing, the two computed signals and the elected-seam rule are ours.
