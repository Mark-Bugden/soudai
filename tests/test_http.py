"""The cached, paced client, against a fake server: caching, pacing, backoff and the stop rules."""

import gzip
import sqlite3

import pytest
import requests

from soudai import http


class FakeClock:
    """Time that only moves when the client sleeps, or when a test moves it."""

    def __init__(self):
        self.now = 1_000_000.0
        self.sleeps = []

    def __call__(self):
        return self.now

    def sleep(self, seconds):
        self.sleeps.append(seconds)
        self.now += seconds


class FakeReply:
    def __init__(self, status, content=b"{}", content_type="application/json"):
        self.status_code = status
        self.content = content
        self.headers = {"Content-Type": content_type}


class FakeSession:
    """Answers each request with the next item of `replies`: a FakeReply, or an exception to raise."""

    def __init__(self, replies):
        self.replies = list(replies)
        self.calls = []
        self.headers = {}

    def request(self, method, url, json=None, timeout=None):
        self.calls.append((method, url, json))
        reply = self.replies.pop(0)
        if isinstance(reply, Exception):
            raise reply
        return reply


@pytest.fixture
def clock():
    return FakeClock()


@pytest.fixture
def make_client(tmp_path, clock):
    def make(replies):
        session = FakeSession(replies)
        client = http.Client(
            "test", tmp_path / "cache.sqlite", tmp_path / "logs", session, clock=clock, sleep=clock.sleep
        )
        return client, session

    return make


def runs(tmp_path):
    db = sqlite3.connect(tmp_path / "cache.sqlite")
    db.row_factory = sqlite3.Row
    return [dict(row) for row in db.execute("SELECT * FROM runs ORDER BY id")]


def test_a_cached_request_is_not_fetched_again(make_client):
    client, session = make_client([FakeReply(200, b'{"a": 1}')])
    with client:
        first = client.get("https://example.test/x")
        second = client.get("https://example.test/x")
    assert first.json() == second.json() == {"a": 1}
    assert not first.from_cache and second.from_cache
    assert len(session.calls) == 1


def test_the_cache_outlives_the_run(make_client):
    client, _ = make_client([FakeReply(200, b"[1]")])
    with client:
        client.get("https://example.test/x")
    client, session = make_client([])
    with client:
        assert client.get("https://example.test/x").json() == [1]
    assert session.calls == []


def test_refresh_fetches_again_and_replaces_the_cached_response(make_client):
    client, session = make_client([FakeReply(200, b"[1]"), FakeReply(200, b"[2]")])
    with client:
        client.get("https://example.test/x")
        assert client.get("https://example.test/x", refresh=True).json() == [2]
        assert client.get("https://example.test/x").json() == [2]
    assert len(session.calls) == 2


def test_a_not_found_400_is_cached(make_client):
    client, session = make_client([FakeReply(400, b'{"message": "RIZENI_0000#..."}')])
    with client:
        assert client.post("https://example.test/case", {"bcVec": 9999}).status == 400
        assert client.post("https://example.test/case", {"bcVec": 9999}).from_cache
    assert len(session.calls) == 1


def test_the_cache_key_ignores_the_order_of_the_body_keys():
    assert http.request_key("POST", "u", {"a": 1, "b": 2}) == http.request_key("post", "u", {"b": 2, "a": 1})
    assert http.request_key("POST", "u", {"a": 1}) != http.request_key("POST", "u", {"a": 2})
    assert http.request_key("GET", "u") != http.request_key("POST", "u")


def test_the_cache_holds_the_url_body_status_gzipped_response_and_fetch_time(tmp_path, make_client):
    client, _ = make_client([FakeReply(200, b"hello", "text/plain")])
    with client:
        client.post("https://example.test/case", {"b": 2, "a": 1})
    db = sqlite3.connect(tmp_path / "cache.sqlite")
    method, url, body, status, content, content_type, fetched_at = db.execute(
        "SELECT method, url, body, status, content, content_type, fetched_at FROM responses"
    ).fetchone()
    assert (method, url, body, status) == ("POST", "https://example.test/case", '{"a":1,"b":2}', 200)
    assert gzip.decompress(content) == b"hello"
    assert content_type == "text/plain"
    assert fetched_at.endswith("+00:00")


def test_requests_are_spaced_by_the_interval(make_client, clock):
    client, _ = make_client([FakeReply(200)] * 3)
    with client:
        client.get("https://example.test/1")
        clock.now += 0.25  # the caller spends a quarter of a second between requests
        client.get("https://example.test/2")
        client.get("https://example.test/3")
    assert clock.sleeps == [0.75, 1.0]


def test_pacing_is_shared_through_the_cache_across_clients(make_client, clock):
    first, _ = make_client([FakeReply(200)])
    second, _ = make_client([FakeReply(200)])
    with first, second:
        first.get("https://example.test/1")
        second.get("https://example.test/2")
    assert clock.sleeps == [1.0]


def test_cached_responses_skip_the_pacing(make_client, clock):
    client, _ = make_client([FakeReply(200)])
    with client:
        client.get("https://example.test/1")
        client.get("https://example.test/1")
    assert clock.sleeps == []


def test_the_user_agent_names_the_project(make_client):
    _, session = make_client([])
    assert session.headers["User-Agent"].startswith("soudai/")
    assert session.headers["User-Agent"].endswith("(+https://github.com/Mark-Bugden/soudai)")


def test_connection_errors_back_off_30_60_then_90_seconds(make_client, clock):
    errors = [requests.ConnectionError("reset"), requests.Timeout("slow"), requests.ConnectionError("reset")]
    client, session = make_client([*errors, FakeReply(200, b"[1]")])
    with client:
        assert client.get("https://example.test/x").json() == [1]
    assert [s for s in clock.sleeps if s >= 30] == [30, 60, 90]
    assert len(session.calls) == 4


def test_a_connection_reset_partway_through_a_response_backs_off_too(make_client, clock):
    client, _ = make_client([requests.exceptions.ChunkedEncodingError("reset"), FakeReply(200)])
    with client:
        assert client.get("https://example.test/x").status == 200
    assert 30 in clock.sleeps


def test_server_errors_back_off_too(make_client, clock):
    client, _ = make_client([FakeReply(503), FakeReply(200)])
    with client:
        assert client.get("https://example.test/x").status == 200
    assert 30 in clock.sleeps


def test_server_errors_are_not_cached(tmp_path, make_client):
    client, _ = make_client([FakeReply(503)] * 6)
    with pytest.raises(http.StopRun):
        with client:
            client.get("https://example.test/x")
    db = sqlite3.connect(tmp_path / "cache.sqlite")
    assert db.execute("SELECT count(*) FROM responses").fetchone()[0] == 0


def test_a_408_backs_off_and_isnt_cached(make_client, clock):
    client, session = make_client([FakeReply(408), FakeReply(200, b"[1]")])
    with client:
        assert client.get("https://example.test/x").json() == [1]
    assert 30 in clock.sleeps and len(session.calls) == 2


def test_a_success_resets_the_failures_in_a_row(make_client, clock):
    reset = requests.ConnectionError("reset")
    client, _ = make_client([reset, FakeReply(200), reset, FakeReply(200)])
    with client:
        client.get("https://example.test/1")
        client.get("https://example.test/2")
    assert [s for s in clock.sleeps if s >= 30] == [30, 30]


def test_more_than_five_failures_in_a_row_stop_the_run(tmp_path, make_client, clock):
    client, session = make_client([requests.ConnectionError("reset")] * 6 + [FakeReply(200)])
    with pytest.raises(http.StopRun, match="6 failures in a row"):
        with client:
            client.get("https://example.test/x")
    assert len(session.calls) == 6
    assert [s for s in clock.sleeps if s >= 30] == [30, 60, 90, 90, 90]
    [run] = runs(tmp_path)
    assert run["outcome"].startswith("stopped: 6 failures in a row")
    assert run["failures"] == 6


def test_a_429_stops_the_run_at_once(tmp_path, make_client, clock):
    client, session = make_client([FakeReply(429), FakeReply(200)])
    with pytest.raises(http.StopRun, match="429"):
        with client:
            client.get("https://example.test/x")
    assert len(session.calls) == 1
    assert [s for s in clock.sleeps if s >= 30] == []
    assert runs(tmp_path)[0]["outcome"].startswith("stopped: HTTP 429")


def test_a_403_stops_the_run_at_once(tmp_path, make_client):
    client, session = make_client([FakeReply(403), FakeReply(200)])
    with pytest.raises(http.StopRun, match="403"):
        with client:
            client.get("https://example.test/x")
    assert len(session.calls) == 1


def must_be_a_list(response):
    if not isinstance(response.json(), list):
        raise http.UnexpectedResponse("not a list")
    return response.json()


def test_parsed_fetches_a_cached_response_that_doesnt_parse_again_once(make_client):
    client, session = make_client([FakeReply(200, b'{"maintenance": true}'), FakeReply(200, b"[1]")])
    with client:
        client.get("https://example.test/x")  # an outage page gets cached
        assert http.parsed(client, must_be_a_list, "GET", "https://example.test/x") == [1]
        assert http.parsed(client, must_be_a_list, "GET", "https://example.test/x") == [1]
    assert len(session.calls) == 2


def test_parsed_raises_on_a_fresh_response_that_doesnt_parse(make_client):
    client, session = make_client([FakeReply(200, b"{}")])
    with pytest.raises(http.UnexpectedResponse):
        with client:
            http.parsed(client, must_be_a_list, "GET", "https://example.test/x")
    assert len(session.calls) == 1


def test_each_run_is_recorded_with_its_counts_and_a_log(tmp_path, make_client):
    client, _ = make_client([FakeReply(200), FakeReply(200)])
    with client:
        client.get("https://example.test/1")
        client.get("https://example.test/1")
        client.get("https://example.test/2")
        client.set_backend_version("1.2.3")
    [run] = runs(tmp_path)
    assert run["stage"] == "test"
    assert run["outcome"] == "finished"
    assert (run["requests"], run["cache_hits"], run["failures"]) == (2, 1, 0)
    assert run["backend_version"] == "1.2.3"
    assert run["ended_at"] >= run["started_at"]
    log = client.log_path.read_text(encoding="utf-8")
    assert "GET https://example.test/2" in log


def test_an_error_in_the_stage_is_recorded_as_the_outcome(tmp_path, make_client):
    client, _ = make_client([])
    with pytest.raises(ValueError):
        with client:
            raise ValueError("bad page")
    assert runs(tmp_path)[0]["outcome"] == "failed: ValueError: bad page"
