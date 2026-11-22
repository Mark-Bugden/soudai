"""Helpers for the offline tests: saved real responses (tests/fixtures/), and a client that serves them."""

import json
from pathlib import Path

import pytest

from soudai import http

FIXTURES = Path(__file__).parent / "fixtures"


def load(name):
    """A saved response as a Response, plus the request that got it."""
    record = json.loads((FIXTURES / name).read_text(encoding="utf-8"))
    content = json.dumps(record["response"], ensure_ascii=False).encode("utf-8")
    response = http.Response(record["url"], record["status"], content, record["content_type"], "", True)
    return record, response


def make_response(url, status, data=None, text=None, content_type="application/json", from_cache=False):
    content = (
        text.encode("utf-8") if text is not None else json.dumps(data, ensure_ascii=False).encode("utf-8")
    )
    return http.Response(url, status, content, content_type, "", from_cache)


class FakeClient:
    """Stands in for http.Client: answers requests from a dict of responses, and records what was asked."""

    def __init__(self, responses=()):
        self.responses = {}
        self.requests = []
        self.backend_version = None
        self.fetched_at = {}  # request key -> when the cached copy was fetched, for decisions.stale
        for key, response in responses:
            self.add(*key, response)

    def add(self, method, url, body, response):
        self.responses.setdefault(http.request_key(method, url, body), []).append(response)

    def fetch(self, method, url, body=None, refresh=False):
        self.requests.append((method, url, body, refresh))
        queue = self.responses[http.request_key(method, url, body)]
        return queue.pop(0) if len(queue) > 1 else queue[0]

    def get(self, url, params=None, refresh=False):
        return self.fetch("GET", http.with_params(url, params), refresh=refresh)

    def post(self, url, body, refresh=False):
        return self.fetch("POST", url, body, refresh=refresh)

    def cached(self, method, url, body=None):
        """What the cache holds for a request: here, only what a test put in `fetched_at`."""
        fetched_at = self.fetched_at.get(http.request_key(method, url, body))
        return None if fetched_at is None else http.Response(url, 200, b"", None, fetched_at, True)

    def set_backend_version(self, version):
        self.backend_version = version


@pytest.fixture
def fixture_client():
    """A FakeClient serving every saved JSON response in tests/fixtures/."""
    client = FakeClient()
    for path in FIXTURES.rglob("*.json"):
        record, response = load(path.relative_to(FIXTURES).as_posix())
        client.add(record["method"], record["url"], record["body"], response)
    return client
