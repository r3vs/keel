# Module: Security / Secrets / Dependencies (deterministic)

The commoditized part — let the tools do the work, don't re-derive what they already know.
All output normalizes to SARIF/JSON, then passes `fp-check`, then becomes pins.

## Tools → what they catch
- **semgrep** (`--config=auto`, SARIF) — SAST: injection, XSS, SSRF, weak crypto, authz gaps,
  30+ languages. (OpenGrep fork if cross-file taint is needed.)
- **gitleaks** — secrets in the working tree AND full git history (committed-then-"removed"
  secrets are the vibecode signature).
- **osv-scanner** + **trivy** — dependency vulns (SCA), IaC misconfig, license, SBOM.

## Run it — the tools produce reports, the runtime turns them into pins

```bash
semgrep --config=auto --sarif -o .audit/semgrep.sarif .
gitleaks detect --report-format sarif --report-path .audit/gitleaks.sarif
osv-scanner --format json -r . > .audit/osv.json
```

Then pass those reports to the `findings_gate` tool — the ingester **and** the fp-check gate: it normalizes SARIF and OSV to one finding
stream, runs the five ordered checks (intentional-stub → reachability → framework suppression →
corroboration → duplicate merge), clusters N instances of one root cause into a single pin with
many anchors, and maps survivors to `defect` / `incompleteness`.

**Do not hand-read the reports into pins.** Everything below — the clustering, the reachability
downgrade, the 200-instances-one-pin rule — is what that command already does. Re-deriving it by
judgment produces a different answer every run, on a step whose entire purpose is being the same
every run. Missing tools degrade per-tool: pass the reports that exist, note the gap, never block.

## Pin mapping
- Kind = `defect`. Usually `question: null` → straight to remediation (still plan-gated in
  Phase 3), because "fix the SQLi" needs no user judgment.
- Promote to `needs_input` ONLY on genuine scope ambiguity (e.g. "this endpoint looks
  deliberately public — intended?").
- **Reachability via the graph** downgrades findings in unreachable/dead code (see fp-check).
- **Cluster by rule/root-cause**: 200 SQLi instances = one clustered pin (one decision:
  "parameterize everywhere?"), 200 anchors — never 200 questions.

## Discipline
Keep this lean. This is where existing tools are strong and the skill adds least; its value is
in the reachability filter, the clustering, and feeding the shared findings stream — not in
re-explaining OWASP.
