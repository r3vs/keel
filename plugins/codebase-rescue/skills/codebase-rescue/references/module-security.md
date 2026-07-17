# Module: Security / Secrets / Dependencies (deterministic)

The commoditized part — let the tools do the work, don't re-derive what they already know.
All output normalizes to SARIF/JSON, then passes `fp-check`, then becomes pins.

## Tools → what they catch
- **semgrep** (`--config=auto`, SARIF) — SAST: injection, XSS, SSRF, weak crypto, authz gaps,
  30+ languages. (OpenGrep fork if cross-file taint is needed.)
- **gitleaks** — secrets in the working tree AND full git history (committed-then-"removed"
  secrets are the vibecode signature).
- **osv-scanner** + **trivy** — dependency vulns (SCA), IaC misconfig, license, SBOM.

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
