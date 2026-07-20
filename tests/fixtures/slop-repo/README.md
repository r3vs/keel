# slop-repo — a rescue test fixture (deliberately misaligned)

A tiny multi-layer app with **planted** problems, used as a target for the runtime and as a
fixture for `scripts/run_evals.py --run`. It is a test target, never a dependency.

The canonical contract is `contract.json`. The layers below drift from it on purpose:

- **`schema.sql`** (DB): the `users.role` enum is missing `member`, and `display_name` is
  nullable where the contract says NOT NULL → two `contract_mismatch`es the shape engine finds.
- **`handlers.py`** (API): `get_user` is an intentional stub (`NotImplementedError`) →
  `incompleteness`, not a defect; `search_users` builds SQL by string concatenation → a real
  `defect` the ast-grep pack + findings gate confirm.

`python runtime/shapes.py --contract tests/fixtures/slop-repo/contract.json --ddl
tests/fixtures/slop-repo/schema.sql` shows the drift; `ast-grep scan` over `handlers.py` shows the
placeholder + SQLi shapes. See `tests/test_fixture_slop_repo.py` for the assertions.
