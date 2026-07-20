"""Tests for runtime/domain.py — the business entry-point detector (study item C3).

Pins: HTTP routes / CLI / tasks / events / cron are found from decorators + __main__ via `ast`
(a fact), routes carry their path, a non-router `.get` decorator is NOT a false HTTP hit, and the
scan is deterministic. The Domain -> Flow -> Step hierarchy stays the agent's job.
"""
from __future__ import annotations

import os
import pathlib
import sys
import tempfile
import unittest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "src", "runtime"))

import domain  # noqa: E402

FIXTURE = '''\
import click

router = APIRouter()


@router.get("/users")
def list_users():
    return []


@app.post("/login")
async def login():
    return {}


@click.command()
def cli():
    pass


@celery.task
def send_email():
    pass


@app.on_event("startup")
def startup():
    pass


@cache.get
def not_a_route():
    pass


if __name__ == "__main__":
    cli()
'''


class TestScan(unittest.TestCase):
    def setUp(self):
        self._d = tempfile.TemporaryDirectory()
        self.root = pathlib.Path(self._d.name)
        (self.root / "svc.py").write_text(FIXTURE, encoding="utf-8")
        self.res = domain.scan_entry_points(self.root)
        self.by_handler = {e["handler"]: e for e in self.res["entry_points"]}

    def tearDown(self):
        self._d.cleanup()

    def test_http_routes_with_paths(self):
        self.assertEqual(self.by_handler["list_users"]["kind"], "http")
        self.assertEqual(self.by_handler["list_users"]["route"], "/users")
        self.assertEqual(self.by_handler["login"]["kind"], "http")
        self.assertEqual(self.by_handler["login"]["route"], "/login")

    def test_cli_task_event(self):
        self.assertEqual(self.by_handler["cli"]["kind"], "cli")
        self.assertEqual(self.by_handler["send_email"]["kind"], "task")
        self.assertEqual(self.by_handler["startup"]["kind"], "event")

    def test_main_guard_is_cli(self):
        self.assertIn("__main__", self.by_handler)
        self.assertEqual(self.by_handler["__main__"]["kind"], "cli")

    def test_non_router_get_is_not_http(self):
        # @cache.get is a decorator whose receiver is not a router → must not be a false HTTP hit
        self.assertNotIn("not_a_route", self.by_handler)

    def test_by_kind_and_determinism(self):
        import json
        self.assertEqual(self.res["by_kind"].get("http"), 2)
        again = domain.scan_entry_points(self.root)
        self.assertEqual(json.dumps(self.res), json.dumps(again))


if __name__ == "__main__":
    unittest.main()
