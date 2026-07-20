# Brief — a log-tailing CLI

A command-line tool that follows one or more log files, filters lines by a pattern, and prints
matches with color. Reads config from a file; no network, no database, no server.

- **Project type:** CLI tool (prune API, client/rendering, identity, persistence).
- **Must:** stream files without loading them fully; a `--filter` regex; a `--json` output mode.
- **Out of scope for v1:** a TUI, remote log sources, a plugin system.
- **Constraints:** single binary / single entrypoint; runs offline.

Expected forge behavior: the interview should prune the pruned clusters silently (no persistence
or API questions), elect outcomes + the streaming approach, and produce a thin vertical slice
(read → filter → render) test-first.
