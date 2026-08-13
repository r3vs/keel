"""The ledger → issue-tracker projection (`runtime/tracker.py`), exercised entirely offline.

**Why there is no network here, stated first because it is the design constraint that shaped the
module.** A test that reaches api.github.com is a test that needs a token, a repository nobody
minds being written to, and an internet connection on every CI leg — so it gets skipped, and a
skipped test is a claim about an interpreter nobody ran (`test_treesitter.py` records the same
lesson one backend over). `tracker.Client` therefore takes a `urlopen`-like callable, and
`FakeGitHub` below is a small in-memory repository that answers the four calls the module makes.
Everything the module can be wrong about is reachable from here: the payload shape, idempotency,
the state arcs, orphans, every degradation, and the two failure modes that come from GitHub's own
documented behaviour (a pull request answering as an issue, and labels silently dropped).

The classes map to the properties, not to the functions:

  * `TestTheProjectionIsAProjection` — payload shape and determinism.
  * `TestItIsIdempotentByPinId` — the property the whole design exists to have.
  * `TestTheArcsFollowTheLedger` — settling closes, reopening reopens.
  * `TestItReportsRatherThanDestroys` — orphans, duplicates, hand edits, foreign labels.
  * `TestItDegradesIntoAResult` — no token, no network, no repo, no budget.
  * `TestTheTrackerIsAWindowAndNotADoor` — structural: nothing here can write the ledger.
"""
from __future__ import annotations

import ast
import io
import json
import os
import pathlib
import sys
import tempfile
import unittest
import urllib.error
import urllib.parse

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "src", "runtime"))

import tracker  # noqa: E402
from ledger import Ledger  # noqa: E402

RUNTIME = pathlib.Path(__file__).resolve().parent.parent / "src" / "runtime"
REPO = "acme/widgets"


# ── the offline transport ────────────────────────────────────────────────────────────────────

class FakeResponse:
    """What `urlopen` hands back: `.status`, `.headers`, `.read()`. Headers are a plain dict with
    GitHub's own lowercase spelling, so the module's case-folding is exercised rather than assumed.
    """

    def __init__(self, status: int, payload, headers: dict | None = None):
        self.status = status
        self.headers = headers or {}
        self._body = json.dumps(payload).encode("utf-8") if payload is not None else b""

    def read(self) -> bytes:
        return self._body


class FakeGitHub:
    """An in-memory repository behind a `urlopen`-compatible callable.

    It implements only what the module calls — list issues, create one, patch one — and records
    every request, because half of what these tests assert is about what was NOT sent (no second
    create, no write at all on a clean run, nothing after the reserve is reached).
    """

    def __init__(self, issues=None, remaining=None, reset_at=1_700_000_000,
                 drop_labels=False, page_size=100):
        self.issues = [dict(i) for i in (issues or [])]
        self.requests: list = []
        self.remaining = remaining
        self.reset_at = reset_at
        self.drop_labels = drop_labels        # the documented no-push-access behaviour
        self.page_size = page_size
        self._next_number = max([i.get("number", 0) for i in self.issues] + [0]) + 1

    # -- helpers --------------------------------------------------------------------------------

    def _headers(self, extra: dict | None = None) -> dict:
        out = {"content-type": "application/json"}
        if self.remaining is not None:
            out["x-ratelimit-remaining"] = str(self.remaining)
            out["x-ratelimit-reset"] = str(self.reset_at)
        out.update(extra or {})
        return out

    def issue(self, number: int) -> dict:
        for issue in self.issues:
            if issue.get("number") == number:
                return issue
        raise AssertionError(f"no issue {number} in the fake repo")

    # -- the callable ---------------------------------------------------------------------------

    def __call__(self, request, timeout=None):
        method = request.get_method()
        url = request.full_url
        payload = json.loads(request.data.decode("utf-8")) if request.data else None
        self.requests.append((method, url, payload))

        if method == "GET" and "/issues?" in url:
            return self._list(url)
        if method == "POST" and url.endswith("/issues"):
            return self._create(payload)
        if method == "PATCH" and "/issues/" in url:
            return self._patch(int(url.rsplit("/", 1)[1]), payload)
        raise AssertionError(f"the module made a call this fake does not implement: {method} {url}")

    def _list(self, url: str):
        # Parsed, never substring-matched: `per_page=100` contains `page=`, and reading the page
        # number out of it asks for page 100 of a two-issue repo — an empty index, which reads
        # exactly like "nothing is projected yet". The fake found that bug in itself first.
        query = urllib.parse.parse_qs(urllib.parse.urlparse(url).query)
        page = int(query.get("page", ["1"])[0])
        # The label filter is the module's index key; honouring it here is what makes the
        # labels-dropped test mean something (an unlabelled issue must be invisible to the index).
        matching = [i for i in self.issues if tracker.INDEX_LABEL in
                    [label_name(x) for x in i.get("labels", [])]]
        start = (page - 1) * self.page_size
        chunk = matching[start:start + self.page_size]
        extra = {}
        if start + self.page_size < len(matching):
            extra["link"] = (f'<{tracker.API}/repos/{REPO}/issues?state=all&page={page + 1}>; '
                             f'rel="next"')
        return FakeResponse(200, chunk, self._headers(extra))

    def _create(self, payload):
        issue = {"number": self._next_number, "title": payload["title"],
                 "body": payload["body"], "state": "open",
                 "labels": [] if self.drop_labels
                 else [{"name": n} for n in payload.get("labels", [])]}
        self._next_number += 1
        self.issues.append(issue)
        return FakeResponse(201, issue, self._headers())

    def _patch(self, number: int, payload):
        issue = self.issue(number)
        for key in ("title", "body", "state"):
            if key in payload:
                issue[key] = payload[key]
        if "labels" in payload:
            issue["labels"] = [{"name": n} for n in payload["labels"]]
        return FakeResponse(200, issue, self._headers())


def label_name(label) -> str:
    return label.get("name") if isinstance(label, dict) else label


def raising(exc):
    """A transport that fails the way a broken network does."""
    def _open(request, timeout=None):
        raise exc
    return _open


# ── fixtures ─────────────────────────────────────────────────────────────────────────────────

def a_ledger() -> Ledger:
    """One open blocker with a fork, one open assumption pin, one criterion — a real ledger built
    through the runtime, never a hand-written dict, because a hand-written pin is exactly what the
    module is forbidden to be tested against."""
    led = Ledger(os.path.join(tempfile.mkdtemp(), "ledger.json"))
    led.add_pin(
        kind="contract_mismatch", title="role set disagrees between DB and frontend",
        severity="blocker", confidence="extracted",
        provenance=[{"source": "contract_recon", "detail": "db↔api shape diff"}],
        as_is={"db": ["admin", "user"], "frontend": ["admin", "user", "superadmin"],
               "disagreeing_layers": ["db", "frontend"]},
        to_be=None,
        question={"prompt": "What is the intended role set?",
                  "options": [{"id": "opt_db", "label": "Only {admin,user}",
                               "implication": "remove the FE check"},
                              {"id": "opt_add", "label": "Add superadmin to the schema",
                               "implication": "migration + enum everywhere"}],
                  "allow_freeform": True})
    led.add_pin(
        kind="ambiguity", title="retention window was never stated", severity="medium",
        confidence="inferred",
        provenance=[{"source": "agent_assumption", "detail": "assumed 30 days to proceed"}])
    led.save()
    return led


def project(led: Ledger, api: FakeGitHub, **kw) -> dict:
    return tracker.project(led.data, REPO, token="t0ken", urlopen=api, **kw)


def diff(led: Ledger, api: FakeGitHub, **kw) -> dict:
    return tracker.diff(led.data, REPO, token="t0ken", urlopen=api, **kw)


# ── the properties ───────────────────────────────────────────────────────────────────────────

class TestTheProjectionIsAProjection(unittest.TestCase):

    def setUp(self):
        self.led = a_ledger()
        self.pin = self.led.readable_pins()[0]

    def test_the_body_carries_the_pin_id_its_delta_and_its_fork(self):
        body = tracker.render(self.pin, "ledger.json")
        self.assertIn(self.pin["id"], body)
        self.assertIn("superadmin", body)                    # the as-is payload
        self.assertIn("What is the intended role set?", body)
        self.assertIn("`opt_db`", body)                      # the offered option ids
        self.assertIn("single source of truth", body)        # where the truth lives

    def test_it_says_an_answer_written_here_decides_nothing(self):
        """The one sentence the whole design rests on has to be IN the artifact a human reads."""
        body = tracker.render(self.pin, "ledger.json")
        self.assertIn("Only the human elects", body)
        self.assertIn("no tool reads it", body)

    def test_an_agent_assumption_is_marked_as_one_rather_than_scheduled(self):
        assumed = self.led.readable_pins()[1]
        body = tracker.render(assumed, "ledger.json")
        self.assertIn("agent's assumption", body)
        self.assertIn("do not schedule it", body)

    def test_the_title_and_labels_carry_kind_and_state(self):
        self.assertTrue(tracker.title(self.pin).startswith("[contract_mismatch]"))
        self.assertEqual(tracker.labels(self.pin),
                         ["keel", "keel:contract_mismatch", "keel:needs_input"])

    def test_an_unchanged_pin_renders_byte_identically(self):
        """Determinism is not tidiness here: a body that re-renders differently makes every drift
        check a false positive, and the fingerprint in the marker meaningless."""
        self.assertEqual(tracker.render(self.pin), tracker.render(self.pin))
        self.assertEqual(tracker.drift_check(tracker.wrap(self.pin["id"],
                                                          tracker.render(self.pin)),
                                             tracker.render(self.pin))["status"], "in_sync")

    def test_a_long_payload_is_clipped_and_the_clip_is_declared(self):
        pin = dict(self.pin, as_is={"blob": "x" * 5000})
        body = tracker.render(pin)
        self.assertIn("clipped", body)
        self.assertLess(len(body), 3000)

    def test_a_malformed_pin_renders_instead_of_raising(self):
        """`pin_read`'s guarantee, carried into the surface that has no human standing beside it.
        A title that is an object took the AGENTS.md projection down; this is the same field."""
        body = tracker.render({"id": "pin_x", "title": {"oops": 1}, "severity": ["blocker"],
                               "provenance": "not-a-list", "question": "not-an-object"})
        self.assertIn("pin_x", body)


class TestItIsIdempotentByPinId(unittest.TestCase):

    def test_two_runs_over_an_unchanged_ledger_create_one_issue_per_pin(self):
        led, api = a_ledger(), FakeGitHub()
        first = project(led, api)
        created = len(api.issues)
        second = project(led, api)
        self.assertEqual(first["planned"].get("create"), 2)
        self.assertEqual(len(api.issues), created, "the second run created a duplicate issue")
        self.assertEqual(second["planned"].get("create"), None)
        self.assertTrue(second["in_sync"])
        self.assertEqual(second["applied"], [])

    def test_the_index_is_keyed_on_the_marker_not_the_title(self):
        """A human renaming the issue must not make the projection create a second one."""
        led, api = a_ledger(), FakeGitHub()
        project(led, api)
        api.issues[0]["title"] = "renamed by a human during triage"
        out = project(led, api)
        self.assertEqual(_actions(out)[0], "update")
        self.assertEqual(len(api.issues), 2)

    def test_a_pull_request_carrying_the_marker_is_not_treated_as_an_issue(self):
        """GitHub's docs: 'every pull request is an issue, but not every issue is a pull request.'
        Without the skip, a PR quoting a fence would be closed by a settling pin."""
        led = a_ledger()
        pin_id = led.readable_pins()[0]["id"]
        fake_pr = {"number": 91, "title": "wip", "state": "open",
                   "labels": [{"name": "keel"}], "pull_request": {"url": "…"},
                   "body": tracker.wrap(pin_id, tracker.render(led.readable_pins()[0]))}
        api = FakeGitHub(issues=[fake_pr])
        out = project(led, api)
        self.assertEqual(out["planned"].get("create"), 2, "the PR was mistaken for the projection")
        self.assertEqual(api.issue(91)["state"], "open")

    def test_a_truncated_index_writes_nothing_at_all(self):
        """An index that could not be read in full makes 'no issue carries this pin' an artifact of
        the walk rather than a fact — and creating on it duplicates every pin, forever."""
        led = a_ledger()
        api = FakeGitHub(page_size=1)
        project(led, api)                       # seed two issues so the listing paginates
        api.remaining = 5                       # …and make the walk stop inside the reserve
        out = project(led, api)
        self.assertEqual(out["stopped_early"]["reason"], "index_truncated")
        self.assertEqual(out["stopped_early"]["index"]["reason"], "rate_limit")
        self.assertEqual(out["applied"], [])
        # And it must not read as agreement. Dropping the write actions from the report made
        # `in_sync` true — a run that could not read the tracker claiming the tracker matched.
        self.assertFalse(out["in_sync"])


class TestTheArcsFollowTheLedger(unittest.TestCase):

    def _settle(self, led: Ledger, pin_id: str) -> None:
        led.defer(pin_id, rationale="out of scope this quarter",
                  flip_criteria="a second tenant signs", human_answer="not now")
        led.save()

    def test_settling_a_pin_closes_its_issue_with_a_state_reason(self):
        led, api = a_ledger(), FakeGitHub()
        project(led, api)
        pin_id = led.readable_pins()[0]["id"]
        number = [i["number"] for i in api.issues if pin_id in i["body"]][0]
        self._settle(led, pin_id)
        out = project(led, api)
        self.assertEqual(api.issue(number)["state"], "closed")
        self.assertEqual(_payload_of(api, "PATCH")["state_reason"], "completed")
        self.assertEqual(out["planned"].get("close"), 1)

    def test_a_settled_pin_that_was_never_projected_does_not_open_an_issue_to_close_it(self):
        led = a_ledger()
        self._settle(led, led.readable_pins()[0]["id"])
        api = FakeGitHub()
        out = project(led, api)
        self.assertEqual(len(api.issues), 1)                 # only the still-open pin
        self.assertIn("ignored", out["planned"])

    def test_reopening_a_pin_reopens_its_issue(self):
        led, api = a_ledger(), FakeGitHub()
        project(led, api)
        pin_id = led.readable_pins()[0]["id"]
        self._settle(led, pin_id)
        project(led, api)
        led.reopen(pin_id, source="feedback:incident", reason="a second tenant signed")
        led.save()
        out = project(led, api)
        number = [i["number"] for i in api.issues if pin_id in i["body"]][0]
        self.assertEqual(api.issue(number)["state"], "open")
        self.assertEqual(_payload_of(api, "PATCH")["state_reason"], "reopened")
        self.assertEqual(out["planned"].get("reopen"), 1)

    def test_a_decided_pin_carries_its_outcome_into_the_issue_it_closes(self):
        led, api = a_ledger(), FakeGitHub()
        project(led, api)
        pin_id = led.readable_pins()[0]["id"]
        self._settle(led, pin_id)
        project(led, api)
        closed = [i for i in api.issues if pin_id in i["body"]][0]
        self.assertIn("**Elected outcome**", closed["body"])


class TestItReportsRatherThanDestroys(unittest.TestCase):

    def test_an_issue_whose_pin_is_gone_is_reported_and_left_alone(self):
        led, api = a_ledger(), FakeGitHub()
        project(led, api)
        stale = {"number": 77, "title": "[defect] a pin that no longer exists", "state": "open",
                 "labels": [{"name": "keel"}, {"name": "keel:defect"}],
                 "body": tracker.wrap("pin_9999", "orphaned body\n")}
        api.issues.append(stale)
        out = project(led, api)
        orphans = [i for i in out["items"] if i["action"] == "orphan"]
        self.assertEqual([o["issue"] for o in orphans], [77])
        self.assertEqual(api.issue(77)["state"], "open")
        self.assertEqual(api.issue(77)["body"], stale["body"])

    def test_a_hand_edited_region_is_reported_and_never_overwritten(self):
        led, api = a_ledger(), FakeGitHub()
        project(led, api)
        edited = api.issues[0]
        edited["body"] = edited["body"].replace("**Open question**", "**We decided opt_db in chat**")
        before = edited["body"]
        out = project(led, api)
        hand = [i for i in out["items"] if i["action"] == "hand_edited"]
        self.assertEqual(len(hand), 1)
        self.assertIn("put the change in the ledger", hand[0]["reasons"][0])
        self.assertEqual(api.issues[0]["body"], before, "the projection discarded a human's words")

    def test_text_outside_the_fence_survives_a_re_projection(self):
        led, api = a_ledger(), FakeGitHub()
        project(led, api)
        api.issues[0]["body"] = "## Team notes\n\nBlocked on legal.\n\n" + api.issues[0]["body"]
        api.issues[0]["title"] = "renamed"           # force an update
        project(led, api)
        self.assertIn("Blocked on legal.", api.issues[0]["body"])

    def test_a_label_this_projection_does_not_own_is_kept(self):
        led, api = a_ledger(), FakeGitHub()
        project(led, api)
        api.issues[0]["labels"].append({"name": "priority:p1"})
        api.issues[0]["title"] = "renamed"
        project(led, api)
        names = sorted(label_name(x) for x in api.issues[0]["labels"])
        self.assertIn("priority:p1", names)
        self.assertIn("keel", names)

    def test_two_issues_claiming_one_pin_keep_the_lower_number(self):
        led, api = a_ledger(), FakeGitHub()
        project(led, api)
        original = api.issues[0]
        api.issues.append(dict(original, number=500))
        out = diff(led, api)
        self.assertEqual(out["duplicates"][0]["kept"], original["number"])
        self.assertEqual(out["duplicates"][0]["duplicate"], 500)

    def test_diff_reports_the_same_plan_it_would_execute_and_writes_nothing(self):
        """One planner, two doors — the property that stops the drift report being clean about a
        surface nobody re-rendered."""
        led, api = a_ledger(), FakeGitHub()
        dry = diff(led, api)
        self.assertFalse(dry["in_sync"])
        self.assertEqual(dry["planned"].get("create"), 2)
        self.assertEqual([m for m, _u, _p in api.requests if m != "GET"], [])
        wet = project(led, api)
        self.assertEqual(dry["planned"], wet["planned"])


class TestItDegradesIntoAResult(unittest.TestCase):

    def test_no_token_is_a_structured_refusal_and_not_an_empty_tracker(self):
        out = tracker.project(a_ledger().data, REPO, token="", urlopen=FakeGitHub())
        self.assertFalse(out["available"])
        self.assertEqual(out["reason"], "no_token")
        self.assertIn("this is not an empty tracker", out["detail"])

    def test_the_token_is_read_from_either_env_var(self):
        self.assertEqual(tracker.token_from_env({"GH_TOKEN": "b"}), "b")
        self.assertEqual(tracker.token_from_env({"GITHUB_TOKEN": "a", "GH_TOKEN": "b"}), "a")
        self.assertEqual(tracker.token_from_env({}), "")

    def test_a_dead_network_is_a_reason_not_a_traceback(self):
        out = tracker.project(a_ledger().data, REPO, token="t",
                              urlopen=raising(urllib.error.URLError("no route to host")))
        self.assertEqual(out["reason"], "network")
        self.assertIn("says nothing about the ledger", out["detail"])

    def test_a_repo_that_is_not_owner_slash_name_is_refused_before_any_call(self):
        api = FakeGitHub()
        out = tracker.project(a_ledger().data, "../../etc", token="t", urlopen=api)
        self.assertEqual(out["reason"], "bad_repo")
        self.assertEqual(api.requests, [])

    def test_a_missing_repository_is_named_rather_than_read_as_no_issues(self):
        def _open(request, timeout=None):
            raise urllib.error.HTTPError(request.full_url, 404, "Not Found",
                                         {"x-ratelimit-remaining": "4999"},
                                         io.BytesIO(b'{"message":"Not Found"}'))
        out = tracker.project(a_ledger().data, REPO, token="t", urlopen=_open)
        self.assertEqual(out["reason"], "not_found")

    def test_it_stops_inside_the_rate_limit_reserve_and_says_where(self):
        led = a_ledger()
        api = FakeGitHub(remaining=tracker.RATE_LIMIT_RESERVE)
        out = project(led, api)
        self.assertEqual(out["stopped_early"]["reason"], "rate_limit")
        self.assertEqual(out["applied"], [])
        self.assertEqual(len(api.issues), 0)
        self.assertEqual(out["rate_limit"]["remaining"], tracker.RATE_LIMIT_RESERVE)

    def test_a_429_with_retry_after_stops_rather_than_retrying(self):
        """The docs warn that continuing while limited may get an integration banned, so the only
        correct behaviour is to stop — never sleep, never retry."""
        def _open(request, timeout=None):
            raise urllib.error.HTTPError(
                request.full_url, 429, "Too Many Requests",
                {"retry-after": "60", "x-ratelimit-remaining": "0"}, io.BytesIO(b"{}"))
        out = tracker.project(a_ledger().data, REPO, token="t", urlopen=_open)
        self.assertEqual(out["reason"], "rate_limit")
        self.assertEqual(out["retry_after"], 60)

    def test_an_unknown_budget_is_not_read_as_an_empty_one(self):
        """A host that sends no rate-limit header says nothing about the bucket. Treating silence
        as exhaustion would make this refuse to run against Enterprise, a proxy, or this fake."""
        api = FakeGitHub(remaining=None)
        out = project(a_ledger(), api)
        self.assertIsNone(out["stopped_early"])
        self.assertIsNone(out["rate_limit"]["remaining"])

    def test_labels_silently_dropped_stops_the_run_before_it_duplicates(self):
        """GitHub: 'Only users with push access can set labels for new issues. Labels are silently
        dropped otherwise.' The index is the label, so a 201 without it means the next run creates
        a second issue — and the run after that a third."""
        led, api = a_ledger(), FakeGitHub(drop_labels=True)
        out = project(led, api)
        self.assertEqual(out["stopped_early"]["reason"], "labels_dropped")
        self.assertEqual(len(api.issues), 1, "it kept creating after losing the index")
        self.assertIn("push access", out["stopped_early"]["detail"])

    def test_a_per_pin_validation_failure_does_not_end_the_run(self):
        """One unprojectable pin is not evidence about the other forty."""
        api = FakeGitHub()
        original = api._create

        def _first_fails(payload):
            api._create = original
            return FakeResponse(422, {"message": "Validation Failed"}, api._headers())
        api._create = _first_fails
        out = project(a_ledger(), api)
        statuses = sorted(a["status"] for a in out["applied"])
        self.assertEqual(statuses, [201, 422])
        self.assertIsNone(out["stopped_early"])

    def test_a_link_header_pointing_off_the_api_host_is_not_followed(self):
        """A `link` header is server-supplied input and every request carries a bearer token."""
        class Redirector(FakeGitHub):
            def _list(self, url):
                return FakeResponse(200, [], self._headers(
                    {"link": '<https://evil.example/repos/x/issues?page=2>; rel="next"'}))
        api = Redirector()
        project(a_ledger(), api)
        self.assertEqual([u for m, u, _p in api.requests if m == "GET" and "evil" in u], [])


class TestTheTrackerIsAWindowAndNotADoor(unittest.TestCase):
    """Structural, because a promise in a docstring is not an invariant.

    The single rule this module has to keep is that no path through it writes `ledger.json`. That is
    checkable without running anything: the module must never construct a `Ledger`, never call
    `save`, and never import a write door.
    """

    @classmethod
    def setUpClass(cls):
        cls.tree = ast.parse((RUNTIME / "tracker.py").read_text(encoding="utf-8"))

    def test_it_never_constructs_a_ledger_or_saves_one(self):
        called = set()
        for node in ast.walk(self.tree):
            if isinstance(node, ast.Call):
                func = node.func
                called.add(func.id if isinstance(func, ast.Name) else
                           getattr(func, "attr", ""))
        self.assertNotIn("Ledger", called, "the tracker constructed a ledger — it is a window")
        self.assertNotIn("save", called, "the tracker saved something; nothing here may write")

    def test_it_imports_only_the_read_half_of_the_schema(self):
        write_doors = {"Ledger", "decide", "accept", "defer", "resolve", "reopen", "add_pin"}
        imported = {alias.name for node in ast.walk(self.tree)
                    if isinstance(node, ast.ImportFrom) and node.module == "ledger"
                    for alias in node.names}
        self.assertEqual(imported & write_doors, set())
        self.assertTrue(imported, "the module reads no schema at all — that would be its own bug")

    def test_projecting_leaves_the_ledger_file_byte_identical(self):
        led, api = a_ledger(), FakeGitHub()
        before = pathlib.Path(led.path).read_bytes()
        project(led, api)
        project(led, api)
        self.assertEqual(pathlib.Path(led.path).read_bytes(), before)


# ── small readers over the fake, kept out of the assertions themselves ────────────────────────

def _actions(out: dict) -> list:
    return [i["action"] for i in out["items"] if i["action"] != "in_sync"]


def _payload_of(api: FakeGitHub, method: str) -> dict:
    for verb, _url, payload in reversed(api.requests):
        if verb == method:
            return payload or {}
    raise AssertionError(f"no {method} was ever sent")


if __name__ == "__main__":
    unittest.main()
