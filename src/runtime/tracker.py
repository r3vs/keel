"""Issue-tracker carrier — project the open ledger into the place a team already looks.

The gap this closes, and why it is the same gap `instructions.py` closes
------------------------------------------------------------------------
`instructions.py` exists because the ledger is the single source of truth and **no coding agent
loads it**. This module exists because of the other half of that sentence: **no human's team loads
it either.** A project can hold a fully elected design, a `blocker` fork nobody has answered and
three `defect` pins, and the tracker the team actually stands in front of every morning shows none
of it. The decisions do not reach the standup, so they get re-made there — in a thread, verbally,
with nothing written back — which is the divergence this package exists to find, occurring in the
one surface the package had no carrier for.

So the tracker gets the same treatment `AGENTS.md` got, with the same four properties, because they
are what make a projection safe rather than a second source of truth:

  * **one source** — the ledger. Nothing here reads an issue to learn what is true.
  * **a generated projection** — the issue body's managed region is rendered from the pin, never
    authored. Byte-identical on an unchanged pin, which is what lets drift mean something.
  * **a round-trip drift check** — `diff` answers *is the tracker still what the ledger projects*
    without writing anything, and it is computed by the same planner `project` executes.
  * **managed markers** — everything outside the fence is preserved byte for byte, and the same is
    true one axis over for **labels**: a maintainer's `priority:p1` survives a projection, because
    only the `keel:`-namespaced labels belong to us.

A window, not a door
--------------------
**Nothing in this module writes the ledger, and that is structural rather than promised.** It
imports the read half of `ledger` — `pin_read`, `read_collection`, the state sets, `severity_rank`
— and never constructs a `Ledger`. There is no path from an issue back into `ledger.json`, so a
tracker that has been edited, vandalised, or migrated cannot change what this project decided. The
one direction that WOULD be worth having — an issue comment as a reopen signal — is designed and
deliberately unbuilt; `docs/design/tracker-projection.md` records it as an open decision with the
three questions that have to be elected first. Building it on a hunch would put an unauthenticated
comment box on the write path of the single source of truth.

The four host facts this design rests on, each read at GitHub's own docs
-----------------------------------------------------------------------
Verified at the consumer, quoted, and none of them inferred from the others:

1. **"GitHub's REST API considers every pull request an issue, but not every issue is a pull
   request."** So the index skips any entry carrying a `pull_request` key. Without that, a PR whose
   body someone pasted a fence into becomes an issue this module thinks it owns.
2. **"Only users with push access can set labels for new issues. Labels are silently dropped
   otherwise."** This is the failure that would quietly break idempotency, so it is checked rather
   than trusted: after a create, the index label is read back off the response, and a run that lost
   it **stops** — see `_verify_index_label`. A projection that silently fails to label is a
   projection that creates a duplicate issue on every subsequent run, forever.
3. **Rate limits are reported in `x-ratelimit-remaining` / `x-ratelimit-reset` ("in UTC epoch
   seconds"), and on 403/429 "if the `retry-after` response header is present, you should not retry
   your request until after that many seconds has elapsed"** — with the docs' own warning that
   *"continuing to make requests while you are rate limited may result in the banning of your
   integration."* So this stops early and says so; it never sleeps and never retries. A partial
   projection that reports itself partial is strictly better than a complete one that gets the
   user's token banned.
4. **Pagination is the `link` header's `rel="next"`, followed rather than reconstructed** ("the
   query parameters in the `link` URLs may differ between endpoints"). The one thing added on top
   is that a `next` URL is server-supplied input and our token rides on the request, so a link
   pointing anywhere but the API host is refused rather than followed.

Why the index is a label and not a search query
-----------------------------------------------
The obvious idempotency key is the search API (`q=repo:x "keel:pin id=…" in:body`), and it is the
wrong one: GitHub's search index is **eventually consistent**, so an issue created seconds ago is
not findable yet. That fails exactly when it costs most — two projections in quick succession, a
retry after a partial run — and its failure mode is a duplicate issue per pin, which is the one
outcome an idempotent projection may not produce. The index is therefore built from a *listing*
(`GET /issues?state=all&labels=keel`), which is read-your-writes against the same store, and the
`keel` label is the key that makes that listing cheap.

Degradation is a result, never a traceback
------------------------------------------
The runtime's standing rule (`AGENTS.md`: *degrade gracefully when a tool/source is missing; never
hard-fail*) is sharper here than anywhere else in this package, because this is the only module
that talks to a network. No token, no network, a 404 on the repo, an exhausted budget: each is a
structured `{"available": False, "reason": …}` that an agent can read and act on. The one thing
this module must never do is raise a `URLError` into a tool call and leave the caller unable to
tell "the tracker is unreachable" from "the ledger is empty" — which is the same wrong answer
`_open_existing` refuses one layer up.
"""
from __future__ import annotations

import hashlib
import json
import os
import re
import urllib.error
import urllib.parse
import urllib.request
from typing import Any, Callable, Optional

#: The API root. Also the allowlist for pagination: a `link` header naming any other host is
#: server-supplied input pointing our token somewhere we did not choose, so it is refused.
API = "https://api.github.com"

#: The env vars a token is read from, in order. `GITHUB_TOKEN` is what Actions injects and
#: `GH_TOKEN` is what `gh auth` exports; a user who has either has already made the grant, and a
#: third name would be one this package invented for them.
TOKEN_ENV = ("GITHUB_TOKEN", "GH_TOKEN")

#: The label every projected issue carries. It is the **idempotency key of the whole design** — the
#: index is a listing filtered by it — which is why its absence after a create stops the run.
INDEX_LABEL = "keel"

#: The namespace this projection owns. A label starting with it is ours to set and unset; every
#: other label on the issue is the team's and is carried through untouched, which is the label-axis
#: twin of "everything outside the fence is preserved byte for byte".
LABEL_PREFIX = "keel:"

MARKER_VERSION = 1
BEGIN_RE = re.compile(
    r"<!--\s*keel:pin(?:\s+v(?P<v>\d+))?\s+id=(?P<id>[A-Za-z0-9_.:@-]+)"
    r"(?:\s+sha256=(?P<sha>[0-9a-f]{12}))?\s*-->")
END = "<!-- keel:pin-end -->"
_END_RE = re.compile(r"<!--\s*keel:pin-end\s*-->")

#: `owner/name`, and nothing else is accepted. A repo string reaches this module from an agent's
#: arguments and is interpolated into a URL; `../` or a query fragment in it would point an
#: authenticated write at a repository nobody named. Validated at the boundary, once.
_REPO_RE = re.compile(r"^[A-Za-z0-9._-]+/[A-Za-z0-9._-]+$")

#: HYPOTHESIS, tunable — seconds before a single HTTP call is abandoned. The claim that a timeout
#: must EXIST has a carrier (a socket with no deadline hangs a tool call until the host kills the
#: session, and the host's timeout is not ours to know); the value 10 does not. It is chosen to be
#: longer than any p99 this API is documented to target and short enough that a stalled call fails
#: inside one agent turn, not measured.
TIMEOUT = 10.0

#: HYPOTHESIS, tunable — requests left in the hour's budget below which this stops issuing writes.
#: The reserve exists because the rate limit is the USER's, shared with their `gh` CLI, their CI and
#: every other tool on their token: spending it to the last request would make this package the
#: reason something else of theirs failed. 20 is a cushion, not a measurement.
RATE_LIMIT_RESERVE = 20

#: HYPOTHESIS, tunable — the issue title's character budget. GitHub enforces a title maximum that
#: its REST docs do not state (UNVERIFIED — see the design doc), so this is not derived from it: it
#: is the width at which a title still reads in a list view, well inside any plausible cap. The clip
#: is DECLARED with an ellipsis, for the reason every clip in this package is: a shortened line that
#: looks complete is the same lie as a clean report from a scan that did not run.
TITLE_MAX = 120

#: HYPOTHESIS, tunable — characters per rendered `as_is`/`to_be` payload before the block is clipped
#: (again, declared). The pin is the place to read the whole thing; the issue is an index into it,
#: exactly as the `AGENTS.md` region is.
PAYLOAD_MAX = 1200


class Unavailable(Exception):
    """The tracker could not be reached or refused the whole run. Carries `reason` + `detail`.

    Raised only for conditions that end the RUN — no token, no network, bad repo, auth, an
    exhausted budget. A per-issue refusal (a 422 on one pin's labels) is deliberately not one of
    these: it is reported against that pin and the run continues, because one unprojectable pin is
    not evidence about the other forty.
    """

    def __init__(self, reason: str, detail: str, **extra: Any) -> None:
        super().__init__(f"{reason}: {detail}")
        self.reason = reason
        self.detail = detail
        self.extra = extra

    def as_result(self, **more: Any) -> dict:
        out = {"available": False, "reason": self.reason, "detail": self.detail}
        out.update(self.extra)
        out.update(more)
        return out


# ── the projection: pure, deterministic, and the half that needs no network ──────────────────

def _fingerprint(body: str) -> str:
    return hashlib.sha256(body.encode("utf-8")).hexdigest()[:12]


def _clip(text: str, limit: int, hint: str) -> str:
    """`text`, never longer than `limit`, with any loss stated in the text itself."""
    if len(text) <= limit:
        return text
    return text[: max(limit - len(hint), 1)].rstrip() + hint


def _payload(value: Any) -> str:
    """A pin's free-form `as_is` / `to_be` as a deterministic fenced block, or `""`.

    JSON rather than prose, `sort_keys=True` rather than insertion order: the shape is free-form per
    kind (the schema declares `as_is` as `object`), so there is nothing to format it against — and
    a projection whose bytes depend on dict ordering re-renders differently for an unchanged pin,
    which would make every drift check a false positive.
    """
    if value in (None, "", [], {}):
        return ""
    if isinstance(value, str):
        return _clip(value.strip(), PAYLOAD_MAX, " …*(clipped — read the pin)*")
    try:
        dumped = json.dumps(value, indent=2, sort_keys=True, ensure_ascii=False)
    except (TypeError, ValueError):
        dumped = repr(value)
    return "```json\n" + _clip(dumped, PAYLOAD_MAX, "\n… (clipped — read the pin)") + "\n```"


def title(pin: dict) -> str:
    """The issue title: the pin's kind and its own words, clipped and declared.

    Through `pin_read`, like every other field this module indexes — a `title` that is an object
    met `.strip()` in the `AGENTS.md` projection and took the whole render down, and the lesson
    transfers unchanged to a surface that also has no human standing beside it when it runs.
    """
    from ledger import pin_read
    read = pin_read(pin)
    kind = pin.get("kind") or "other"
    text = read["title"].strip() or "(untitled pin)"
    return _clip(f"[{kind}] {text}", TITLE_MAX, " …")


def labels(pin: dict) -> list:
    """The labels this projection owns for a pin: the index label, its kind and its state.

    Deliberately not severity. A label per severity is a fourth axis on a surface that already has
    three, and severity is the field most likely to be re-elected — every change would be a write
    against the API for a fact the body already carries.
    """
    from ledger import pin_read
    read = pin_read(pin)
    out = [INDEX_LABEL]
    kind = str(pin.get("kind") or "other")
    if kind:
        out.append(f"{LABEL_PREFIX}{kind}")
    if read["state"]:
        out.append(f"{LABEL_PREFIX}{read['state']}")
    return out


def render(pin: dict, ledger_path: str = "ledger.json") -> str:
    """The managed region's body for one pin — markers excluded.

    What it carries and what it refuses is the same bargain the `AGENTS.md` region makes. It
    carries: where the truth lives, the pin's identity, the delta (`as_is` / `to_be`), the fork
    still open on it (`question`), the outcome if one was elected, and the provenance — with
    `agent_assumption` called out, because a pin an agent assumed into existence is exactly the one
    a human reading a tracker should veto rather than schedule.

    It refuses the remediation list, the verification envelope, the premortem and the dependency
    edges. Those are the working state of a loop that runs against the ledger; restating them here
    would make the issue a second place to look for them, and the moment there are two, a reader
    has to know which is stale.
    """
    from ledger import pin_read
    read = pin_read(pin)
    kind = pin.get("kind") or "other"
    if kind == "other" and pin.get("kind_detail"):
        kind = f"other:{pin['kind_detail']}"

    lines = [
        f"*Generated by Keel from `{ledger_path}`, which is the single source of truth. This issue "
        f"is a **projection** of one pin — a window, not a door: nothing written here is read back "
        f"into the ledger. Elect the answer in the interview (`interview_next`, then "
        f"`ledger_record_decision`) and re-run `tracker_project`. Text OUTSIDE this fence is yours "
        f"and is never touched.*",
        "",
        f"- **pin** `{read['id'] or '?'}` · kind `{kind}` · severity "
        f"`{read['severity'] or 'unstated'}` · state `{read['state'] or 'unstated'}`",
    ]

    # `provenance` entries are objects (`{"source": …, "detail": …}`), and the SOURCE is what a
    # reader weighs — `str()` on the whole entry would put a Python dict repr in a human's tracker.
    # A bare string is accepted too, because `pin_read` guarantees the list and not its members.
    provenance = []
    for entry in read["provenance"]:
        name = str(entry.get("source") or "").strip() if isinstance(entry, dict) else str(entry)
        if name.strip():
            provenance.append(name.strip())
    if provenance:
        lines.append(f"- **provenance** {', '.join(f'`{p}`' for p in provenance)}")
    if "agent_assumption" in provenance:
        lines.append("- ⚠️ **This pin is an agent's assumption, not an elected decision.** It is "
                     "surfaced so it can be vetoed; do not schedule it as agreed work.")

    for label, value in (("As-is", read.get("as_is")), ("To-be", read.get("to_be"))):
        block = _payload(value)
        if block:
            lines += ["", f"**{label}**", "", block]

    question = read["question"]
    prompt = str(question.get("prompt") or "").strip() if isinstance(question, dict) else ""
    if prompt:
        lines += ["", "**Open question**", "", prompt]
        options = question.get("options") if isinstance(question, dict) else None
        for option in options if isinstance(options, list) else []:
            if not isinstance(option, dict):
                continue
            oid = str(option.get("id") or "?")
            olabel = str(option.get("label") or "").strip()
            implication = str(option.get("implication") or "").strip()
            lines.append(f"- `{oid}` — {olabel}" + (f" *({implication})*" if implication else ""))
        if question.get("allow_freeform"):
            lines.append("- *(an answer in the human's own words is allowed on this fork)*")
        lines.append("")
        lines.append("**Only the human elects.** Answering in a comment here decides nothing — no "
                     "tool reads it.")

    outcome = read["decision"].get("outcome") if isinstance(read["decision"], dict) else None
    if outcome:
        lines += ["", f"**Elected outcome** `{outcome}`"]

    return "\n".join(lines).rstrip() + "\n"


def wrap(pin_id: str, body: str) -> str:
    """Body → the fenced region, the begin marker carrying the pin id and the body's fingerprint.

    Two facts in one marker, for the two questions a reader of an issue has to be able to answer
    mechanically: *which pin is this* (the idempotency key — an issue is found by it, never by its
    title, which a human may rewrite) and *is this still what the ledger rendered* (the fingerprint,
    which is what separates a hand-edited region from a merely stale one — `drift_check`).
    """
    return (f"<!-- keel:pin v{MARKER_VERSION} id={pin_id} sha256={_fingerprint(body)} -->\n"
            f"{body}{END}\n")


def extract(text: Optional[str]) -> Optional[dict]:
    """The managed region found in `text`, or None. `{'pin_id','body','recorded','start','end'}`."""
    begin = BEGIN_RE.search(text or "")
    if not begin:
        return None
    end = _END_RE.search(text or "", begin.end())
    if not end:
        return None
    body = (text or "")[begin.end():end.start()].lstrip("\n")
    return {"pin_id": begin.group("id"), "body": body, "recorded": begin.group("sha"),
            "start": begin.start(), "end": end.end()}


def apply(text: Optional[str], pin_id: str, body: str) -> str:
    """`text` with the managed region set to `body`; everything outside it preserved byte for byte.

    An absent region is APPENDED rather than prepended, and unlike the `AGENTS.md` case the reason
    is not host behaviour but human behaviour: an issue people have been discussing has context at
    the top that they wrote, and pushing it down on every projection would be this tool rearranging
    their thread.
    """
    region = wrap(pin_id, body)
    if not text:
        return region
    found = extract(text)
    if found:
        return text[: found["start"]] + region.rstrip("\n") + text[found["end"]:]
    sep = "" if text.endswith("\n\n") else ("\n" if text.endswith("\n") else "\n\n")
    return text + sep + region


def drift_check(text: Optional[str], body: str) -> dict:
    """Is this issue's managed region what the ledger currently projects?

    The same four statuses as `instructions.drift_check`, with the same meanings, deliberately — a
    reader who has learned one projection's vocabulary has learned both:

      - `absent`      — no region (or no issue): the carrier was never written.
      - `hand_edited` — the body no longer hashes to what the marker recorded. Someone wrote into
                        the projection. **Reported, never healed**: regenerating would discard it,
                        and what they wrote may be the only copy of a real decision. The fix is to
                        put it in the ledger.
      - `stale`       — intact, but the ledger has moved: re-project.
      - `in_sync`     — nothing to do.
    """
    found = extract(text or "")
    if not found:
        return {"status": "absent", "in_sync": False,
                "detail": "no keel managed region in this issue body"}
    actual = _fingerprint(found["body"])
    if found["recorded"] and found["recorded"] != actual:
        return {"status": "hand_edited", "in_sync": False, "recorded": found["recorded"],
                "actual": actual,
                "detail": "the managed region was edited by hand. Its content is a projection: put "
                          "the change in the ledger (a pin, a decision), then re-project — "
                          "re-projecting now would discard it, so this issue is left alone."}
    if found["body"].rstrip("\n") != body.rstrip("\n"):
        return {"status": "stale", "in_sync": False,
                "detail": "the ledger has moved since this issue was written — re-project"}
    return {"status": "in_sync", "in_sync": True, "detail": ""}


# ── the transport: stdlib urllib, an injectable opener, and no retries ────────────────────────

def token_from_env(env: Optional[dict] = None) -> str:
    """The first non-empty token in `TOKEN_ENV`, or `""`. Never raises, never logs the value."""
    source = os.environ if env is None else env
    for name in TOKEN_ENV:
        value = str(source.get(name) or "").strip()
        if value:
            return value
    return ""


def _header(headers: Any, name: str) -> str:
    """One header, case-insensitively, off whatever the transport handed back.

    `http.client.HTTPMessage.get` is already case-insensitive; a plain `dict` — which is what a test
    double naturally is — is not. Reading `x-ratelimit-remaining` off a dict keyed
    `X-RateLimit-Remaining` returns None, and this module would then believe it had an unlimited
    budget on every response. So the case-folding lives here rather than in the caller's memory.
    """
    getter = getattr(headers, "get", None)
    if getter is None:
        return ""
    for key in (name, name.lower(), name.upper()):
        value = getter(key)
        if value not in (None, ""):
            return str(value)
    items = getattr(headers, "items", None)
    if callable(items):
        for key, value in items():
            if str(key).lower() == name.lower() and value not in (None, ""):
                return str(value)
    return ""


class Client:
    """A GitHub REST client over an injectable `urlopen`, so the whole module is testable offline.

    `urlopen` is a parameter and not an import for one reason: **every test in this repo runs with
    no network**, and a module whose only path to correctness is a live API is a module whose tests
    assert nothing. The callable takes `(request, timeout=…)` and returns something with `.status`,
    `.headers` and `.read()` — which is `urllib.request.urlopen`'s contract and also
    `urllib.error.HTTPError`'s, which is why an error response is handled as a response below
    rather than as an exception.
    """

    def __init__(self, repo: str, token: str, urlopen: Optional[Callable] = None,
                 timeout: float = TIMEOUT) -> None:
        if not _REPO_RE.match(repo or ""):
            raise Unavailable("bad_repo", f"{repo!r} is not `owner/name`. Refusing to build a URL "
                                          f"out of it — an unvalidated repo string is an "
                                          f"authenticated write pointed somewhere nobody named.")
        if not token:
            raise Unavailable(
                "no_token",
                f"no token in {' or '.join(TOKEN_ENV)}. The tracker projection needs a token with "
                f"push access to {repo} (labels are silently dropped without it). Nothing was "
                f"written and nothing was read — this is not an empty tracker.")
        self.repo = repo
        self.token = token
        self.timeout = timeout
        self._urlopen = urlopen or urllib.request.urlopen
        self.calls = 0
        self.remaining: Optional[int] = None
        self.reset_at: Optional[int] = None
        self.retry_after: Optional[int] = None

    # -- budget ---------------------------------------------------------------------------------

    def _note_budget(self, headers: Any) -> None:
        remaining = _header(headers, "x-ratelimit-remaining")
        if remaining.isdigit():
            self.remaining = int(remaining)
        reset = _header(headers, "x-ratelimit-reset")
        if reset.isdigit():
            self.reset_at = int(reset)          # "in UTC epoch seconds", per the docs
        retry = _header(headers, "retry-after")
        self.retry_after = int(retry) if retry.isdigit() else None

    def exhausted(self) -> bool:
        """Is the remaining budget inside the reserve? Unknown budget is NOT exhausted.

        A response that carried no rate-limit header says nothing about the bucket, and treating
        silence as empty would make this module refuse to work against any host that does not send
        the header — a GitHub Enterprise instance, a proxy that strips it, a test double. Unknown is
        unknown; the run proceeds and the result reports `remaining: null`.
        """
        return self.remaining is not None and self.remaining <= RATE_LIMIT_RESERVE

    def budget(self) -> dict:
        return {"remaining": self.remaining, "reset_at": self.reset_at, "requests": self.calls}

    # -- one call -------------------------------------------------------------------------------

    def request(self, method: str, url: str, payload: Optional[dict] = None) -> tuple:
        """`(status, data, headers)`. Raises `Unavailable` only for run-ending conditions.

        Everything else — 400, 404 on a single issue, 422 — comes back as a status the caller
        decides about, because the caller is the only thing that knows whether one pin failing ends
        the run (it does not) or the repo being absent does (it does).
        """
        body = None
        if payload is not None:
            body = json.dumps(payload).encode("utf-8")
        request = urllib.request.Request(url, data=body, method=method, headers={
            "Authorization": f"Bearer {self.token}",
            "Accept": "application/vnd.github+json",
            "X-GitHub-Api-Version": "2022-11-28",
            "Content-Type": "application/json",
            "User-Agent": "keel-tracker",
        })
        self.calls += 1
        try:
            response = self._urlopen(request, timeout=self.timeout)
        except urllib.error.HTTPError as exc:
            response = exc                      # an HTTPError IS the response: status/headers/read
        except (urllib.error.URLError, TimeoutError, OSError) as exc:
            raise Unavailable("network", f"{type(exc).__name__}: {exc}. The tracker was not "
                                         f"reached; this says nothing about the ledger.") from None

        status = int(getattr(response, "status", 0) or getattr(response, "code", 0) or 0)
        headers = getattr(response, "headers", {}) or {}
        try:
            raw = response.read() or b""
        except OSError as exc:
            raise Unavailable("network", f"response body unreadable: {exc}") from None
        self._note_budget(headers)

        data: Any = None
        if raw.strip():
            try:
                data = json.loads(raw)
            except (ValueError, UnicodeDecodeError):
                data = None                     # a non-JSON body is reported by status, not guessed
        self._raise_if_fatal(status, data)
        return status, data, headers

    def _raise_if_fatal(self, status: int, data: Any) -> None:
        message = (data or {}).get("message") if isinstance(data, dict) else None
        if status in (403, 429) and (self.retry_after is not None or self.remaining == 0):
            raise Unavailable(
                "rate_limit",
                f"GitHub rate-limited this token ({status}). Stopping rather than retrying: the "
                f"docs warn that continuing while limited may get an integration banned.",
                retry_after=self.retry_after, reset_at=self.reset_at)
        if status == 401:
            raise Unavailable("auth", f"the token was rejected (401). {message or ''}".strip())
        if status == 403:
            raise Unavailable("forbidden", f"the token lacks access to {self.repo} (403). "
                                           f"{message or ''}".strip())
        if status == 404:
            raise Unavailable("not_found", f"no such repository, or the token cannot see it: "
                                           f"{self.repo} (404).")
        if status >= 500:
            raise Unavailable("server_error", f"GitHub answered {status}. Nothing was retried.")

    # -- pagination -----------------------------------------------------------------------------

    def _next_link(self, headers: Any) -> str:
        """The `rel="next"` URL, if it points at this API host. Otherwise "".

        The allowlist is the point. A `link` header is a value the server chose, and every request
        this client makes carries a bearer token; following an arbitrary host out of one would hand
        that token to whoever wrote the header. Refusing is silent by design — a legitimate `next`
        always names the API host, so a refusal here means something was wrong, and the run simply
        stops paginating rather than leaking.
        """
        for part in _header(headers, "link").split(","):
            bits = part.split(";")
            if len(bits) < 2 or 'rel="next"' not in part:
                continue
            url = bits[0].strip().strip("<>")
            if url.startswith(API + "/"):
                return url
        return ""

    def paginate(self, path: str, params: dict, page_cap: int = 20) -> tuple:
        """Every entry across pages, plus whether the walk was cut short and why.

        `page_cap` is a signature default rather than a module constant on purpose: it is a
        structural guard against an endless `link` cycle, not a tuning of how much data is wanted.
        The cap and the budget are both DECLARED in the return, because a truncated index would
        otherwise read as "these pins have no issue" and the next run would duplicate every one of
        them — the single worst thing an idempotent projection can be quietly wrong about.
        """
        url = f"{API}/repos/{self.repo}{path}?{urllib.parse.urlencode(params)}"
        out: list = []
        pages = 0
        while url:
            status, data, headers = self.request("GET", url)
            if status != 200 or not isinstance(data, list):
                return out, {"reason": "unexpected_response", "status": status}
            out += [e for e in data if isinstance(e, dict)]
            pages += 1
            url = self._next_link(headers)
            if url and pages >= page_cap:
                return out, {"reason": "page_cap", "pages": pages}
            if url and self.exhausted():
                return out, {"reason": "rate_limit", "remaining": self.remaining,
                             "reset_at": self.reset_at}
        return out, {}


# ── the plan: computed once, executed by `project`, reported by `diff` ────────────────────────

def _order(pin: dict) -> tuple:
    """Severity then id, through `ledger.severity_rank` — the package's ONE severity ordering.

    Stable ordering matters here for the same reason it does in the `AGENTS.md` projection and for
    one more: the plan is executed against a rate-limited API and may stop early, so the order
    decides WHICH pins reach the tracker when the budget runs out. Blockers first is not cosmetic.
    """
    from ledger import pin_read, severity_rank
    read = pin_read(pin)
    return (severity_rank(read["severity"]), read["id"])


def _index(client: Client) -> tuple:
    """`pin_id -> issue`, built from a listing rather than a search. Plus duplicates and notes.

    Two entries claiming one pin id happens when someone copies an issue body, and the resolution is
    the conservative one: the LOWEST issue number wins (the original), the rest are reported and
    never touched. Closing them automatically would be this tool resolving a human's mistake by
    destroying evidence of it.
    """
    # `per_page: 100` is the API's own documented maximum ("Results per page, max 100"), asked for
    # so the index costs the fewest requests against a budget the user shares with every other tool
    # on their token. A ceiling somebody else set, written where it is used rather than kept as a
    # module constant that would read as a number this package chose.
    issues, truncated = client.paginate(
        "/issues", {"state": "all", "labels": INDEX_LABEL, "per_page": 100})
    index: dict = {}
    duplicates: list = []
    for issue in issues:
        # "GitHub's REST API considers every pull request an issue, but not every issue is a pull
        # request." A PR is not a projection target and must not be closed by one.
        if "pull_request" in issue:
            continue
        found = extract(issue.get("body") or "")
        if not found:
            continue
        pin_id = found["pin_id"]
        current = index.get(pin_id)
        if current is None:
            index[pin_id] = issue
            continue
        keep, drop = sorted((current, issue), key=lambda i: int(i.get("number") or 0))
        index[pin_id] = keep
        duplicates.append({"pin": pin_id, "kept": keep.get("number"),
                           "duplicate": drop.get("number"),
                           "detail": "two issues carry this pin's marker; the lower number is "
                                     "treated as the projection and the other is left untouched"})
    return index, duplicates, truncated


def _issue_labels(issue: dict) -> list:
    out = []
    for label in issue.get("labels") or []:
        name = label.get("name") if isinstance(label, dict) else label
        if isinstance(name, str) and name:
            out.append(name)
    return out


def _merged_labels(issue: Optional[dict], wanted: list) -> list:
    """Ours, plus every label that is not ours, kept.

    The label-axis twin of the managed region: a team's `priority:p1`, `sprint-14` or `good first
    issue` is theirs, and a projection that replaced the label set wholesale would delete their
    triage on every run. Sorted so an unchanged pin produces an unchanged payload.
    """
    theirs = [n for n in _issue_labels(issue or {})
              if n != INDEX_LABEL and not n.startswith(LABEL_PREFIX)]
    return sorted(set(theirs) | set(wanted))


def projection(data: dict, ledger_path: str = "ledger.json") -> list:
    """Every pin rendered into what its issue should say — **pure, and computed before the network.**

    Split out of `plan` rather than inlined, and the ordering is the point: this is where every
    field of every pin is indexed (`render`, `title`, `labels`, `_order`), so it is where a ledger
    this runtime cannot read has to fail or degrade. Running it first means "the tracker is
    unreachable" can never be the answer that HIDES an unreadable ledger — the two are different
    facts and a caller is entitled to both. It also makes the offline half of this module
    exercisable on its own, which is what `tests/test_mcp_tools.py`'s hostile corpus walks: a tool
    that reached the transport first would answer `no_token` on all hundred malformed pins and
    prove nothing about any of them.
    """
    from ledger import OPEN_STATES, pin_read, read_collection
    out: list = []
    for pin in sorted(read_collection(data, "pins"), key=_order):
        read = pin_read(pin)
        out.append({"pin": read["id"], "open": read["state"] in OPEN_STATES,
                    "state": read["state"], "title": title(pin), "labels": labels(pin),
                    "body": render(pin, ledger_path)})
    return out


def plan(data: dict, index: dict, ledger_path: str = "ledger.json") -> list:
    """What the tracker would have to change to equal the ledger. Writes nothing, ever."""
    return plan_over(projection(data, ledger_path), index)


def plan_over(rendered: list, index: dict) -> list:
    """The plan, from an already-rendered projection and the tracker's index.

    **One planner, two doors** — `project` executes this list and `diff` prints it. That sharing is
    the same rule `tools._instructions_render` states for the generate/diff pair: two functions that
    answer "what should the projection be" in two places are two answers waiting to disagree, and
    the disagreement shows up as a drift report that is clean about a surface nobody re-rendered.

    One action vocabulary, and it is imperative because it is a plan: `create` · `update` ·
    `reopen` · `close` · `in_sync` · `hand_edited` · `orphan` · `ignored`.

    The one rule worth stating outright: a SETTLED pin with no issue is `ignored`, not `create`.
    Opening an issue in order to close it in the same run would fill a team's tracker with the
    history of a ledger they never asked to mirror.
    """
    out: list = []
    seen: set = set()

    for entry in rendered:
        pin_id, body = entry["pin"], entry["body"]
        if not pin_id:
            # A pin with no id cannot be keyed, so it cannot be projected idempotently. Reported
            # rather than skipped in silence — `pin_read` substitutes `""` and `nonconforming`
            # already says why, and a projection that quietly drops pins is a projection that
            # tells a team there is less here than there is.
            out.append({"pin": "", "action": "ignored", "issue": None,
                        "reasons": ["no id — nothing to key an issue on"]})
            continue
        seen.add(pin_id)
        wanted_title, wanted_labels = entry["title"], entry["labels"]
        issue = index.get(pin_id)
        is_open = entry["open"]

        if issue is None:
            out.append({"pin": pin_id, "action": "create" if is_open else "ignored",
                        "issue": None, "body": body, "title": wanted_title,
                        "labels": wanted_labels,
                        "reasons": ["no issue carries this pin"] if is_open
                        else ["settled, and never projected — an issue is not opened to close it"]})
            continue

        number = issue.get("number")
        check = drift_check(issue.get("body") or "", body)
        if check["status"] == "hand_edited":
            out.append({"pin": pin_id, "action": "hand_edited", "issue": number,
                        "reasons": [check["detail"]]})
            continue

        reasons = []
        if not check["in_sync"]:
            reasons.append(f"body {check['status']}")
        if (issue.get("title") or "") != wanted_title:
            reasons.append("title differs")
        merged = _merged_labels(issue, wanted_labels)
        if sorted(_issue_labels(issue)) != merged:
            reasons.append("labels differ")

        issue_open = (issue.get("state") or "open") == "open"
        action = "update" if reasons else "in_sync"
        # The state arcs outrank a body edit, because one PATCH carries both: an issue that must
        # close AND has drifted is closed with the corrected body in the same request, so the arc
        # names the action and the drift stays in `reasons`.
        if is_open and not issue_open:
            action = "reopen"
            reasons.append("pin is open; issue is closed")
        elif not is_open and issue_open:
            action = "close"
            reasons.append(f"pin settled as `{entry['state']}`")

        out.append({"pin": pin_id, "action": action, "issue": number, "body": body,
                    "title": wanted_title, "labels": merged, "reasons": reasons})

    for pin_id, issue in sorted(index.items()):
        if pin_id in seen:
            continue
        # Reported, never closed and never deleted. An issue whose pin is gone may mean the pin was
        # dropped from the ledger — or that this run was pointed at the wrong ledger, which is the
        # case where deleting would destroy a team's work on the strength of a mistyped path.
        out.append({"pin": pin_id, "action": "orphan", "issue": issue.get("number"),
                    "reasons": ["this issue names a pin the ledger does not hold — reported, not "
                                "touched. Check the ledger path before doing anything about it."]})
    return out


def _counts(items: list) -> dict:
    out: dict = {}
    for item in items:
        out[item["action"]] = out.get(item["action"], 0) + 1
    return out


def _summary(items: list, ledger_path: str, repo: str, truncated: dict) -> dict:
    """The shared report shape for both doors.

    `in_sync` is the one field a caller acts on without reading anything else, so it carries the
    strictest rule in this module: **a partial index can never produce agreement.** Nothing else is
    honest — a plan computed against pages nobody walked reports every unseen issue's pin as
    `create`, and on a run where the seen pins happened to match it would otherwise have answered
    "in sync" about a tracker it could not read.
    """
    return {"available": True, "repo": repo, "ledger": ledger_path,
            "planned": _counts(items),
            "in_sync": not truncated and not any(
                i["action"] in ("create", "update", "reopen", "close") for i in items),
            "items": [{k: v for k, v in i.items() if k != "body"} for i in items]}


def diff(data: dict, repo: str, token: Optional[str] = None, urlopen: Optional[Callable] = None,
         timeout: float = TIMEOUT, ledger_path: str = "ledger.json") -> dict:
    """Is the tracker still what the ledger projects? **Writes nothing, on either side.**

    The read-only twin of `project`, and the one to run first — it costs the index request and
    nothing else, and it answers the question a team actually has ("what has drifted?") without
    touching a tracker they may not have agreed to have written to yet.

    The ledger is rendered BEFORE the transport is touched (see `projection`), so an unreachable
    tracker still reports how many pins the projection could read — an unavailable result never
    doubles as an unnoticed failure to read the source.
    """
    rendered = projection(data, ledger_path)
    try:
        client = Client(repo, token if token is not None else token_from_env(), urlopen, timeout)
        index, duplicates, truncated = _index(client)
    except Unavailable as exc:
        return exc.as_result(repo=repo, ledger=ledger_path, pins=len(rendered))
    items = plan_over(rendered, index)
    out = _summary(items, ledger_path, repo, truncated)
    out["duplicates"] = duplicates
    out["index_truncated"] = truncated or None
    out["rate_limit"] = client.budget()
    return out


def _verify_index_label(issue: Any, pin_id: str) -> Optional[dict]:
    """After a create: did the index label actually land? A `dict` when it did not, else None.

    This is the check that keeps idempotency honest, and it exists because of a documented
    behaviour rather than a suspected one: *"Only users with push access can set labels for new
    issues. Labels are silently dropped otherwise."* A token without push access therefore creates
    a perfectly good-looking issue that the index cannot see — so the next run creates another, and
    the run after that a third. Silent, unbounded duplication from a 201.
    """
    if not isinstance(issue, dict):
        return {"reason": "unreadable_response",
                "detail": "the create returned no issue object; cannot confirm the index label"}
    if INDEX_LABEL in _issue_labels(issue):
        return None
    return {"reason": "labels_dropped", "issue": issue.get("number"), "pin": pin_id,
            "detail": f"the created issue carries no `{INDEX_LABEL}` label. GitHub's docs: 'Only "
                      f"users with push access can set labels for new issues. Labels are silently "
                      f"dropped otherwise.' Without it the index cannot find this issue and the "
                      f"next run would create a duplicate, so the run stopped here. Use a token "
                      f"with push access."}


def project(data: dict, repo: str, token: Optional[str] = None, urlopen: Optional[Callable] = None,
            timeout: float = TIMEOUT, ledger_path: str = "ledger.json") -> dict:
    """Project the ledger's open pins into the repository's issues. WRITES ISSUES.

    Idempotent by pin id: run it twice against an unchanged ledger and the second run writes
    nothing. Settling a pin closes its issue; reopening one reopens it. It never deletes an issue,
    never edits outside the managed region, never replaces a label it does not own, and never — on
    any path — writes the ledger.

    Stops early, and says so, in four cases: the index could not be read in full (nothing is
    written at all — see below), the rate-limit reserve is reached, a create came back without the
    index label, or the transport failed mid-run. A partial projection that reports itself partial
    is the honest outcome; the alternative is a run that looks complete while half the blockers are
    missing from the board.
    """
    rendered = projection(data, ledger_path)
    try:
        client = Client(repo, token if token is not None else token_from_env(), urlopen, timeout)
        index, duplicates, truncated = _index(client)
    except Unavailable as exc:
        return exc.as_result(repo=repo, ledger=ledger_path, pins=len(rendered))

    items = plan_over(rendered, index)
    applied: list = []
    stopped: Optional[dict] = None

    if truncated:
        # The index is incomplete, so "no issue carries this pin" is not a fact — it is an artifact
        # of a walk that stopped. Creating on that reading is exactly the duplication this design
        # exists to prevent, so nothing is written at all.
        # The walk's own reason is nested rather than merged: `truncated` carries a `reason` of its
        # own (`rate_limit`, `page_cap`, `unexpected_response`) and flattening it here overwrote
        # this one, so a run that wrote nothing because its index was short reported itself as
        # merely rate-limited. Two facts, kept as two.
        stopped = {"reason": "index_truncated", "index": truncated,
                   "detail": "the issue index could not be read in full, so an absent pin may "
                             "simply be on a page nobody walked — and creating on that reading "
                             "duplicates it forever. Nothing was written, and the plan below is "
                             "computed against a partial index: read it as a question, not an "
                             "answer."}
        # The plan is REPORTED unchanged, deliberately. Dropping the write actions from it (the
        # first draft did) made `planned` empty and `in_sync` **true** — a run that could not read
        # the tracker telling the caller the tracker matched. Nothing executes either way: the loop
        # below skips every item while `stopped` is set, which is the guard that actually holds.

    for item in items:
        action = item["action"]
        if stopped or action in ("in_sync", "hand_edited", "orphan", "ignored"):
            continue
        if client.exhausted():
            stopped = {"reason": "rate_limit", "detail": "stopped inside the reserve rather than "
                                                         "spending the user's last requests",
                       "remaining": client.remaining, "reset_at": client.reset_at}
            break
        payload = {"title": item["title"], "body": apply(None, item["pin"], item["body"]),
                   "labels": item["labels"]}
        try:
            if action == "create":
                status, issue, _ = client.request("POST", f"{API}/repos/{repo}/issues", payload)
                if status not in (200, 201):
                    applied.append({**_bare(item), "applied": False, "status": status})
                    continue
                item["issue"] = issue.get("number") if isinstance(issue, dict) else None
                problem = _verify_index_label(issue, item["pin"])
                if problem:
                    applied.append({**_bare(item), "applied": True, "status": status})
                    stopped = problem
                    break
            else:
                existing = index.get(item["pin"]) or {}
                payload["body"] = apply(existing.get("body") or "", item["pin"], item["body"])
                if action == "close":
                    payload.update({"state": "closed", "state_reason": "completed"})
                elif action == "reopen":
                    payload.update({"state": "open", "state_reason": "reopened"})
                status, _issue, _ = client.request(
                    "PATCH", f"{API}/repos/{repo}/issues/{item['issue']}", payload)
                if status != 200:
                    applied.append({**_bare(item), "applied": False, "status": status})
                    continue
        except Unavailable as exc:
            stopped = exc.as_result()
            break
        applied.append({**_bare(item), "applied": True, "status": status})

    out = _summary(items, ledger_path, repo, truncated)
    out["applied"] = applied
    out["stopped_early"] = stopped
    out["duplicates"] = duplicates
    out["index_truncated"] = truncated or None
    out["rate_limit"] = client.budget()
    out["note"] = ("The ledger is the source of truth. These issues are a projection of it: an "
                   "answer written in a comment decides nothing, and a hand-edited managed region "
                   "is reported rather than overwritten.")
    return out


def _bare(item: dict) -> dict:
    """An item without its rendered body — the body is the payload, not the report."""
    return {k: v for k, v in item.items() if k != "body"}
