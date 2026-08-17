#!/usr/bin/env python3
"""PreToolUse nudge on Bash: point a shell search at the search tools.

`core/search-strategy.md` says which tool answers which question — `rg` over `grep -r`, `fd` over
`find`, `ast-grep` the moment the question has syntax in it. That is prose, and prose in a doctrine
file is read once at the start of a session and skipped for the rest of it. This is the same lesson
`ledger-gate.py` carries: a rule with no mechanism rots. The difference is what the mechanism is
allowed to do.

**This one never blocks.** A shell `grep` is not wrong — it is slower, noisier about generated
files, and blind to structure, none of which is worth stopping work over. Denying it would also be
false in the cases that matter most: a pipe filter, a probe against a scratch file, several searches
deliberately batched into one call. So the gate here is a sentence, and the reader decides.

Once per rule per session
-------------------------
The value is entirely in the first firing: it is read, and it either changes the next command or
has a reason not to. Firings 2..n change nothing and cost attention in the scrollback — the
upstream skill this borrows the design from measured 23 firings of three rules in one session
before adding the same dedup. State is a small file in the temp dir, keyed on a *hash* of the
session id, and every failure to read or write it fails OPEN: a broken temp dir must lose the
dedup, never the warning.

Exit code is always 0. A hook that crashes must never take a shell command down with it.
"""
import hashlib
import json
import os
import re
import sys
import tempfile

# --- what is NOT a search over the tree -------------------------------------------------------
# Each of these would produce a nudge that is simply wrong, which is how a warn-only hook loses
# the reader's attention permanently.

# A quoted heredoc body is data being written to a file, not a command being run.
HEREDOC = re.compile(r"<<-?\s*(['\"])(\w+)\1.*?^\2$", re.DOTALL | re.MULTILINE)
# Prose passed as an option value is text *about* commands — a commit message, a PR body, an issue
# comment. `--body-file` names a path instead, so it is deliberately not in this list.
PROSE_OPT = re.compile(
    r"(?:--(?:body|message|title|description|notes|comment)(?!-file)|(?<!\w)-[mF](?!\w))"
    r"[= ]\s*(['\"])(?:\\.|(?!\1).)*\1",
    re.DOTALL,
)
# Echoing text that happens to mention a command is not running it.
ECHO = re.compile(r"^\s*(echo|printf)\b")
# `gh pr list | grep open` filters another command's output. `rg` does not replace that, and the
# tree is not involved.
PIPED = re.compile(r"\|\s*(?:[A-Za-z0-9_.=/-]+\s+)*grep\b")

# --- the three rules ---------------------------------------------------------------------------
# Ordered; a single command may earn more than one. `id` is what the session dedup remembers, so
# renaming one re-arms it for everybody — which is correct, it is a different sentence.
RULES = (
    (
        "find",
        re.compile(r"(?:^|[|&;])\s*find\s"),
        "`find` — prefer the Glob tool, or `fd`: .gitignore-aware and parallel by default.",
    ),
    (
        "grep-r",
        re.compile(r"(?:^|[|&;])\s*grep\s+-[A-Za-z]*[rR]"),
        "recursive `grep` over the tree — prefer the Grep tool or `rg` (skips .gitignore'd and "
        "generated files); for a question with syntax in it, `ast-grep --lang X -p '…'`.",
    ),
    (
        "grep",
        re.compile(r"^\s*grep\s"),
        "`grep` — prefer the Grep tool or `rg`.",
    ),
)


def executable_text(command: str) -> str:
    """The command with its data parts removed, so only what actually runs is scanned."""
    text = HEREDOC.sub(" ", command or "")
    return PROSE_OPT.sub(" ", text)


def detect(command: str) -> list:
    """Ordered `(id, message)` for one command string. `grep -r` and plain `grep` never both fire."""
    text = executable_text(command)
    if not text.strip() or ECHO.match(text.strip()):
        return []
    hits, saw_grep = [], False
    for rule_id, pattern, message in RULES:
        if rule_id.startswith("grep"):
            # A pipe filter is out of scope entirely, and the specific rule wins over the generic.
            if saw_grep or PIPED.search(text):
                continue
        if pattern.search(text):
            hits.append((rule_id, message))
            saw_grep = saw_grep or rule_id.startswith("grep")
    return hits


# --- once per rule per session -----------------------------------------------------------------

def _state_path(payload: dict):
    """Temp-file path for this session, or None when the harness gave us no identity.

    The session id is hashed rather than interpolated: a value carrying `/` or `..` would otherwise
    steer this write out of the temp directory.
    """
    raw = payload.get("session_id") or os.path.basename(payload.get("transcript_path") or "")
    raw = str(raw).strip()
    if not raw:
        return None
    digest = hashlib.sha256(raw.encode("utf-8")).hexdigest()[:16]
    return os.path.join(tempfile.gettempdir(), f"keel-search-nudge-{digest}.json")


def unseen(hits: list, payload: dict) -> list:
    """Drop the rules that already spoke this session, and record the ones that are about to."""
    path = _state_path(payload)
    if path is None:
        return hits
    try:
        with open(path, encoding="utf-8") as fh:
            seen = set(json.load(fh))
    except (OSError, ValueError):
        seen = set()
    fresh = [(rule_id, message) for rule_id, message in hits if rule_id not in seen]
    if fresh:
        seen.update(rule_id for rule_id, _ in fresh)
        try:
            with open(path, "w", encoding="utf-8") as fh:
                json.dump(sorted(seen), fh)
        except OSError:
            pass  # fail open: losing the dedup is cheaper than losing the warning
    return fresh


def main() -> int:
    try:
        payload = json.load(sys.stdin)
    except (ValueError, OSError):
        return 0
    if not isinstance(payload, dict) or payload.get("tool_name") != "Bash":
        return 0
    command = (payload.get("tool_input") or {}).get("command") or ""
    if not isinstance(command, str):
        return 0

    fresh = unseen(detect(command), payload)
    if fresh:
        print(json.dumps({
            "systemMessage": "keel search-strategy: "
                             + " ".join(message for _, message in fresh)
                             + " (once per rule per session)",
            "suppressOutput": True,
        }))
    return 0


if __name__ == "__main__":
    sys.exit(main())
