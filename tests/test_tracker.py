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
  * `TestCommentsAreSurfacedAndNeverActedOn` — the elected inbound path, which reads and stops.
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

    It implements only what the module calls — list issues, create one, patch one, read one
    thread — and records every request, because half of what these tests assert is about what was
    NOT sent (no second create, no write at all on a clean run, nothing after the reserve is
    reached, and no request at all against a thread the listing said was empty).
    """

    def __init__(self, issues=None, remaining=None, reset_at=1_700_000_000,
                 drop_labels=False, page_size=100, comments=None, report_counts=True):
        self.issues = [dict(i) for i in (issues or [])]
        self.requests: list = []
        self.remaining = remaining
        self.reset_at = reset_at
        self.drop_labels = drop_labels        # the documented no-push-access behaviour
        self.page_size = page_size
        #: `{issue_number: [comment, …]}`. Comments are a separate endpoint on GitHub and a
        #: separate store here, which is what makes "the empty thread costs no request" checkable.
        self.comments: dict = dict(comments or {})
        #: Whether the ISSUE listing stamps a `comments` count. GitHub's issue resource carries
        #: one; a host that does not send it must be read as *unknown* and fetched anyway, so both
        #: modes exist here rather than one being assumed.
        self.report_counts = report_counts
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

        if method == "GET" and "/comments?" in url:
            return self._thread(url)
        if method == "GET" and "/issues?" in url:
            return self._list(url)
        if method == "POST" and url.endswith("/issues"):
            return self._create(payload)
        if method == "PATCH" and "/issues/" in url:
            return self._patch(int(url.rsplit("/", 1)[1]), payload)
        raise AssertionError(f"the module made a call this fake does not implement: {method} {url}")

    def _thread(self, url: str):
        """`GET /repos/{repo}/issues/{n}/comments`. The number is parsed out of the path, so a
        module that built the URL off the issue's server-supplied `comments_url` instead of from
        the validated repo would land somewhere this fake cannot answer."""
        number = int(url.split("/issues/")[1].split("/")[0])
        return FakeResponse(200, [dict(c) for c in self.comments.get(number, [])], self._headers())

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
        # Copied, and stamped with the thread's size the way GitHub's issue resource is. The count
        # is what lets the module skip an empty thread; a fake that never sent one would make the
        # "no request against an empty thread" property untestable and the unknown-count path the
        # only one ever exercised.
        chunk = [dict(issue, **({"comments": len(self.comments.get(issue.get("number"), []))}
                                if self.report_counts else {}))
                 for issue in matching[start:start + self.page_size]]
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


def a_comment(body, author="dana", created_at="2026-08-13T09:00:00Z", cid=1) -> dict:
    """One issue comment, in GitHub's own shape: the author is nested under `user`."""
    return {"id": cid, "user": {"login": author}, "created_at": created_at, "body": body}


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

    def test_the_two_tools_open_a_ledger_and_call_no_writer_on_it(self):
        """The claim one layer up, which the module's own AST cannot carry.

        `plugins/keel-core/README.md` states the direction as a structural fact, and the shipped
        wording was *"neither tool constructs a `Ledger`"* — which is false at the tool boundary:
        `tracker_project` and `tracker_diff` both call `_open_existing`, and that ends
        `return Ledger(path)`. The narrower claim is the true one and it holds one layer down, so
        the AST gate above matched the module and nothing matched the tools — a `led.save()` added
        in `tools.py` tomorrow would leave every test green and the README still asserting it.

        So this is the tools' half of the same predicate: they may OPEN a ledger (reading pins is
        the whole job) and may call nothing that writes one. Same shape as
        `test_ledger.py::TestARuleIsTrueOfTheThingItIsPrintedOn`, and the same class as §19/§23 —
        a rule paid on one side of a pairing.
        """
        import ast
        tools_py = pathlib.Path(__file__).resolve().parent.parent / "src" / "mcp" / "tools.py"
        tree = ast.parse(tools_py.read_text(encoding="utf-8"), filename=str(tools_py))
        writers = {"save", "add_pin", "decide", "accept", "defer", "resolve", "reopen",
                   "apply_policy", "add_proposals", "set_question", "surface_assumption",
                   "mark_correctness_unknown", "record_policy", "cross_derive"}
        found = {node.name: node for node in ast.walk(tree)
                 if isinstance(node, ast.FunctionDef) and node.name.startswith("tracker_")}
        self.assertEqual(set(found), {"tracker_project", "tracker_diff"},
                         "a third tracker tool appeared and this gate does not know about it")
        for name, fn in sorted(found.items()):
            called = {getattr(n.func, "attr", getattr(n.func, "id", ""))
                      for n in ast.walk(fn) if isinstance(n, ast.Call)}
            with self.subTest(tool=name):
                self.assertEqual(called & writers, set(),
                                 f"{name} reached a ledger write door — the tracker is a window")


class TestTheProjectionCannotForgeItsOwnFence(unittest.TestCase):
    """A pin whose text contains the end marker used to poison its own issue.

    The mechanism, and why it is the worst possible failure for this module: `wrap` emits
    `begin + body + END`, and `extract` takes the FIRST `_END_RE` after the begin — so a body
    carrying `<!-- keel:pin-end -->` truncates at its own marker, the fingerprint stops matching,
    and `drift_check` answers `hand_edited`. That verdict is not a warning, it is a **refusal to
    write**: `plan_over` skips the item, so the issue is never updated and never closed. And
    `_summary`'s `in_sync` excludes `hand_edited`, so the whole run reports **agreement** while a
    settled blocker's issue stays open forever, under a message accusing a human of an edit the
    module made itself.

    Nothing exotic reaches that state. A pin discussing this design, an `as_is` pasted out of an
    issue this tool wrote, a `to_be` naming the marker — the module ships its own poison.
    """

    @staticmethod
    def _poisoned() -> Ledger:
        led = Ledger(os.path.join(tempfile.mkdtemp(), "ledger.json"))
        led.add_pin(kind="open_decision", title=f"stop emitting {tracker.END}", severity="blocker",
                    confidence="extracted", provenance=[{"source": "recon", "detail": "x"}],
                    question={"prompt": f"How long?\n{tracker.END}\nrest",
                              "options": [{"id": "a", "label": f"keep {tracker.BEGIN_RE.pattern}"}],
                              "allow_freeform": True})
        led.save()
        return led

    def test_a_rendered_body_never_contains_a_marker_of_this_module(self):
        body = tracker.render(self._poisoned().readable_pins()[0], "ledger.json")
        self.assertNotIn(tracker.END, body)
        self.assertIsNone(tracker.BEGIN_RE.search(body))
        self.assertIn(tracker.MARKER_NOTE, body,
                      "the removal must be VISIBLE — a marker deleted in silence is this module "
                      "editing a human's words, which is the one thing it promises never to do")

    def test_the_run_after_a_create_is_in_sync_and_not_an_accusation(self):
        led = self._poisoned()
        api = FakeGitHub()
        self.assertEqual(project(led, api)["planned"], {"create": 1})
        again = project(led, api)
        self.assertEqual(again["planned"], {"in_sync": 1},
                         "the module reported ITS OWN write as a hand edit")
        self.assertTrue(again["in_sync"])

    def test_settling_the_pin_still_closes_the_issue(self):
        """The consequence that costs a team something. `hand_edited` skips the state arcs, so a
        settled blocker kept an open issue while `tracker_diff` answered `in_sync: true`."""
        led = self._poisoned()
        api = FakeGitHub()
        project(led, api)
        led.defer(led.readable_pins()[0]["id"], rationale="out of scope for v1",
                  flip_criteria="a second tenant asks for it",
                  human_answer="not for v1 — park it")
        led.save()
        out = project(led, api)
        self.assertEqual(out["planned"], {"close": 1})
        self.assertEqual(api.issues[0]["state"], "closed")

    def test_the_same_hole_is_shut_in_the_other_projection(self):
        """`instructions.py` fences the same way over its own marker vocabulary, and a pin title is
        enough to poison it — so the property is asserted at both carriers rather than at the one
        where it was found."""
        import instructions
        led = Ledger(os.path.join(tempfile.mkdtemp(), "ledger.json"))
        led.add_pin(kind="open_decision", title=f"a title with {instructions.END} in it",
                    severity="blocker", confidence="extracted",
                    provenance=[{"source": "recon", "detail": "x"}],
                    question={"prompt": "p", "allow_freeform": True})
        led.save()
        body = instructions.render(led.data)
        self.assertNotIn(instructions.END, body)
        self.assertEqual(instructions.drift_check(instructions.wrap(body), body)["status"],
                         "in_sync")


class TestOneDeadIssueIsNotEvidenceAboutTheRepository(unittest.TestCase):
    """404 means two different things at two URLs, and `_raise_if_fatal` used to conflate them.

    `Client.request`'s docstring has always promised that *"404 on a single issue"* comes back as a
    status the caller decides about, and `Unavailable`'s that *"a per-issue refusal … is reported
    against that pin and the run continues, because one unprojectable pin is not evidence about the
    other forty."* The code raised on every 404.

    That the per-issue case is real was read on the endpoint rather than inferred: *Update an issue*
    documents 301 (*"transferred to another repository"*), 410 (*"deleted from a repository where
    the authenticated user has read access"*) and 404 — which *Get an issue* explains as *"the issue
    was transferred to or deleted from a repository where the authenticated user lacks read
    access"*. The index is a snapshot taken before the write, so all three sit between the listing
    and the PATCH. Both classes are asserted here, because the finding was that one rule was being
    applied to both.
    """

    class OneDeadIssue(FakeGitHub):
        def _patch(self, number, payload):
            if number == self.dead:
                raise urllib.error.HTTPError(
                    f"https://api.github.com/repos/{REPO}/issues/{number}", 404, "Not Found",
                    {"x-ratelimit-remaining": "4999"}, io.BytesIO(b'{"message":"Not Found"}'))
            return super()._patch(number, payload)

    def _run(self):
        led, api = a_ledger(), FakeGitHub()
        project(led, api)                                   # two issues now exist
        dead = api.issues[0]["number"]
        live = self.OneDeadIssue(issues=api.issues)
        live.dead = dead
        # Renamed OUTSIDE the fence, which is how a human actually drifts an issue: the managed
        # region still hashes to its marker, so the plan is `update` for both — a body edit would
        # have been `hand_edited`, which never reaches the transport and would have proved nothing.
        for issue in live.issues:
            issue["title"] = "a maintainer renamed this"
        return led, live, dead

    def test_the_repository_is_not_blamed_for_one_issue(self):
        led, api, dead = self._run()
        out = project(led, api)
        self.assertIsNone(out["stopped_early"],
                          "one dead issue ended the whole run and named the repository")
        failed = [a for a in out["applied"] if a["issue"] == dead]
        self.assertEqual([a["status"] for a in failed], [404])
        self.assertIn("not there to write to", failed[0]["detail"])

    def test_the_other_pins_are_still_projected(self):
        led, api, dead = self._run()
        out = project(led, api)
        healthy = [a for a in out["applied"] if a["issue"] != dead]
        self.assertTrue(healthy, "no other pin was even attempted")
        self.assertTrue(all(a["applied"] for a in healthy))

    def test_a_404_on_the_repository_itself_still_ends_the_run(self):
        """The half that must NOT change: the index and the create are repo-scoped, so their 404 is
        the repository's and stopping is correct. Asserted beside its opposite, because the whole
        finding was that one rule was being applied to both."""
        def _open(request, timeout=None):
            raise urllib.error.HTTPError(request.full_url, 404, "Not Found",
                                         {"x-ratelimit-remaining": "4999"},
                                         io.BytesIO(b'{"message":"Not Found"}'))
        out = tracker.project(a_ledger().data, REPO, token="t", urlopen=_open)
        self.assertEqual(out["reason"], "not_found")


class TestCommentsAreSurfacedAndNeverActedOn(unittest.TestCase):
    """The inbound path elected on 2026-08-13 — `docs/design/tracker-projection.md`.

    The election was *read-only surfacing*: a comment on a projected issue is listed under
    `awaiting_human_review` with the pin its issue carries, and nothing else ever happens to it.
    So the properties under test are one capability and three refusals — it surfaces; it does not
    report its own output as somebody waiting; it does not answer "nobody is waiting" about a
    tracker it never read; and it does not acquire a write path on either side while doing so.

    The last one is the load-bearing one. The two forks this election made moot (whose comment
    counts, what the ledger records as the source) are moot only for as long as no comment reaches
    a writer, and `TestTheTrackerIsAWindowAndNotADoor` proves that structurally for the module.
    What is asserted here is the end-to-end version at the new surface: a diff that read a thread
    sent no non-GET request and left `ledger.json` byte-identical.
    """

    def _seeded(self, comments=None, **kw):
        """A ledger projected into a fake tracker, with `comments` keyed by PIN rather than by
        issue number — the numbers are the fake's to allocate, and a test that hard-coded them
        would be asserting against the fixture's arithmetic instead of the module's attribution."""
        led, api = a_ledger(), FakeGitHub(**kw)
        project(led, api)
        for pin_id, thread in (comments or {}).items():
            number = [i["number"] for i in api.issues if pin_id in i["body"]][0]
            api.comments[number] = thread
        return led, api

    def test_a_comment_is_surfaced_against_the_pin_its_issue_carries(self):
        led = a_ledger()
        pin_id = led.readable_pins()[0]["id"]
        led, api = self._seeded({pin_id: [a_comment("we agreed on opt_db in standup", "dana")]})
        out = diff(led, api)
        waiting = out["awaiting_human_review"]
        self.assertEqual(len(waiting), 1)
        entry = waiting[0]
        self.assertEqual(entry["pin_id"], pin_id)
        self.assertEqual(entry["author"], "dana")
        self.assertEqual(entry["created_at"], "2026-08-13T09:00:00Z")
        self.assertIn("opt_db in standup", entry["excerpt"])
        self.assertEqual(entry["issue_number"],
                         [i["number"] for i in api.issues if pin_id in i["body"]][0])
        self.assertEqual(out["comments"]["surfaced"], 1)

    def test_the_projection_does_not_report_its_own_output_as_a_human_waiting(self):
        """A comment carrying this module's own fence is the projector talking to itself. Counting
        it would inflate the one number a maintainer acts on with the tool's own noise — the same
        class as a clean scan that did not run."""
        led = a_ledger()
        pin = led.readable_pins()[0]
        led, api = self._seeded({pin["id"]: [
            a_comment(tracker.wrap(pin["id"], tracker.render(pin)), "keel-bot"),
            a_comment("and a person, in the same thread", "dana", cid=2)]})
        out = diff(led, api)
        self.assertEqual([e["author"] for e in out["awaiting_human_review"]], ["dana"])
        self.assertEqual(out["comments"]["excluded_own"], 1)
        self.assertEqual(out["comments"]["comments_read"], 2, "the fence hid the comment beside it")

    def test_a_bare_begin_marker_is_own_output_too(self):
        """Half a fence is as much this module's output as a whole one — a truncated quote of a
        projected body still came from here, and `_defuse` guarantees nothing else emits one."""
        led = a_ledger()
        pin_id = led.readable_pins()[0]["id"]
        led, api = self._seeded({pin_id: [a_comment(f"<!-- keel:pin v1 id={pin_id} -->\ntrailing")]})
        self.assertEqual(diff(led, api)["awaiting_human_review"], [])

    def test_no_token_says_unavailable_rather_than_nobody_is_waiting(self):
        """The section is `null`, never `[]`. An empty list is the answer *nobody is waiting*, and
        a tracker that was never reached has not earned it — the same rule as `_open_existing`'s
        refusal to read a missing ledger as an empty one."""
        out = tracker.diff(a_ledger().data, REPO, token="", urlopen=FakeGitHub())
        self.assertFalse(out["available"])
        self.assertEqual(out["reason"], "no_token")
        self.assertIsNone(out["awaiting_human_review"])
        self.assertFalse(out["comments"]["available"])
        self.assertEqual(out["comments"]["reason"], "no_token")
        self.assertIn("nobody is waiting on you", out["comments"]["detail"])

    def test_a_dead_network_leaves_the_section_unanswered_too(self):
        out = tracker.diff(a_ledger().data, REPO, token="t",
                           urlopen=raising(urllib.error.URLError("no route to host")))
        self.assertIsNone(out["awaiting_human_review"])
        self.assertEqual(out["comments"]["reason"], "network")

    def test_reading_comments_writes_on_neither_side(self):
        """The end-to-end half of the window/door invariant, at the surface the election added."""
        led = a_ledger()
        pin_id = led.readable_pins()[0]["id"]
        led, api = self._seeded({pin_id: [a_comment("bumping this")]})
        before = pathlib.Path(led.path).read_bytes()
        api.requests.clear()
        out = diff(led, api)
        self.assertEqual([m for m, _u, _p in api.requests if m != "GET"], [],
                         "the read-only door sent a write")
        self.assertEqual(pathlib.Path(led.path).read_bytes(), before)
        self.assertTrue(out["awaiting_human_review"])

    def test_a_comment_never_moves_in_sync(self):
        """`in_sync` means the projection matches the ledger, and re-projecting is what clears it.
        Nothing this tool does clears a comment — only a human electing — so folding one into the
        flag would make it permanently false on any tracker a team actually talks in."""
        led = a_ledger()
        pin_id = led.readable_pins()[0]["id"]
        led, api = self._seeded({pin_id: [a_comment("still waiting on this")]})
        out = diff(led, api)
        self.assertTrue(out["in_sync"])
        self.assertEqual(len(out["awaiting_human_review"]), 1)

    def test_an_empty_thread_costs_no_request(self):
        """The listing's own `comments` count says the thread is empty, so nothing is fetched. This
        is the whole reason `tracker_diff` stays cheap on a tracker that is mostly quiet."""
        led, api = self._seeded()
        api.requests.clear()
        out = diff(led, api)
        self.assertEqual([u for _m, u, _p in api.requests if "/comments?" in u], [])
        self.assertEqual(out["comments"]["issues_read"], 0)
        self.assertEqual(out["awaiting_human_review"], [])

    def test_an_absent_count_is_unknown_and_is_read_rather_than_assumed_empty(self):
        """A host that sends no `comments` count says nothing about the thread. Reading silence as
        emptiness is the same error as reading a missing rate-limit header as an exhausted budget —
        and here it would silently drop every comment on Enterprise or behind a stripping proxy."""
        led = a_ledger()
        pin_id = led.readable_pins()[0]["id"]
        led, api = self._seeded({pin_id: [a_comment("read me")]}, report_counts=False)
        out = diff(led, api)
        self.assertEqual(out["comments"]["issues_read"], 2)
        self.assertEqual(len(out["awaiting_human_review"]), 1)

    def test_a_long_comment_is_clipped_and_the_clip_is_declared(self):
        led = a_ledger()
        pin_id = led.readable_pins()[0]["id"]
        led, api = self._seeded({pin_id: [a_comment("x " * 4000)]})
        excerpt = diff(led, api)["awaiting_human_review"][0]["excerpt"]
        self.assertLessEqual(len(excerpt), tracker.COMMENT_EXCERPT_MAX)
        self.assertIn("clipped", excerpt)

    def test_a_dead_thread_does_not_end_the_read_of_the_others(self):
        """One issue transferred or deleted between the index and the read is not evidence about
        the other forty threads — the same lesson `TestOneDeadIssueIsNotEvidenceAboutTheRepository`
        records one endpoint over, paid again at the endpoint the election added."""
        led = a_ledger()
        first, second = (p["id"] for p in led.readable_pins()[:2])
        led, api = self._seeded({first: [a_comment("this thread is gone")],
                                 second: [a_comment("this one is not")]})
        dead = [i["number"] for i in api.issues if first in i["body"]][0]

        original = api._thread

        def _one_is_dead(url):
            if f"/issues/{dead}/comments" in url:
                raise urllib.error.HTTPError(url, 404, "Not Found",
                                             {"x-ratelimit-remaining": "4999"},
                                             io.BytesIO(b'{"message":"Not Found"}'))
            return original(url)
        api._thread = _one_is_dead
        out = diff(led, api)
        self.assertTrue(out["available"], "one dead thread ended a read-only report")
        self.assertEqual([e["pin_id"] for e in out["awaiting_human_review"]], [second])
        self.assertEqual([t["issue"] for t in out["comments"]["threads_incomplete"]], [dead])

    def test_the_walk_stops_inside_the_rate_limit_reserve_and_says_so(self):
        """The drift plan is complete and the comment list is not, so the two facts are reported as
        two: `stopped` names what ended the walk, and the list is a floor rather than a total."""
        led = a_ledger()
        pin_id = led.readable_pins()[0]["id"]
        led, api = self._seeded({pin_id: [a_comment("nobody will read me this hour")]})
        api.remaining = tracker.RATE_LIMIT_RESERVE
        out = diff(led, api)
        self.assertEqual(out["comments"]["stopped"]["reason"], "rate_limit")
        self.assertEqual(out["awaiting_human_review"], [])
        self.assertEqual([u for _m, u, _p in api.requests if "/comments?" in u], [])

    def test_the_caller_can_ask_for_the_drift_plan_alone(self):
        led, api = self._seeded()
        out = tracker.diff(led.data, REPO, token="t0ken", urlopen=api, comments=False)
        self.assertIsNone(out["awaiting_human_review"])
        self.assertEqual(out["comments"]["reason"], "not_requested")

    def test_a_deleted_account_is_a_blank_author_and_not_a_traceback(self):
        """GitHub answers `"user": null` for a comment whose account is gone. This module's
        standing rule is that reading is never the operation that fails."""
        led = a_ledger()
        pin_id = led.readable_pins()[0]["id"]
        ghost = dict(a_comment("written by someone who left"), user=None)
        led, api = self._seeded({pin_id: [ghost]})
        self.assertEqual(diff(led, api)["awaiting_human_review"][0]["author"], "")

    def test_project_does_not_pay_for_the_read(self):
        """The election added a section to the READ door. `tracker_project` is the write door and
        its cost profile is unchanged — it fetches no thread, so a projection run is not quietly
        multiplied by a tracker's conversation volume."""
        led = a_ledger()
        pin_id = led.readable_pins()[0]["id"]
        led, api = self._seeded({pin_id: [a_comment("hello")]})
        api.issues[0]["title"] = "renamed, so there is something to write"
        api.requests.clear()
        out = project(led, api)
        self.assertEqual([u for _m, u, _p in api.requests if "/comments?" in u], [])
        self.assertNotIn("awaiting_human_review", out)


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
