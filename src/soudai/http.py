"""The cached, paced HTTP client that every request in the pipeline goes through.

- **Cache.** Every response the server gives, including not-found responses, goes into
  data/raw/cache.sqlite: the request key, URL, body, status, the response gzipped and the fetch time.
  A request that's cached is never fetched again unless the caller asks to refresh it.
- **Pacing.** At most one request a second across the whole project, not per process. The time of
  the last request is kept in the cache and claimed inside a write transaction, so two processes
  share the budget rather than doubling it.
- **Backoff.** On a connection error, a timeout or a 5xx, wait 30, 60, then 90 s and retry. More
  than 5 failures in a row, or any 429, stop the run.
- **Identification.** User-Agent soudai/<version> (+https://github.com/Mark-Bugden/soudai).
- **Run log.** Each run is a row in the cache's `runs` table, and logs every request to
  data/raw/logs/<stage>-<start time>.log.

    with Client("courts") as client:
        courts = client.get("https://infosoud.gov.cz/api/v1/organizace/lov").json()
"""

import gzip
import hashlib
import json
import logging
import sqlite3
import sys
import time
from dataclasses import dataclass
from datetime import UTC, datetime
from importlib.metadata import version
from urllib.parse import urlencode

import requests

from . import paths

VERSION = version("soudai")
USER_AGENT = f"soudai/{VERSION} (+https://github.com/Mark-Bugden/soudai)"
INTERVAL = 1.0  # seconds between requests, across the whole project (decided 2026-11-22)
BACKOFF = (30, 60, 90)  # seconds to wait after the 1st, 2nd and 3rd failure in a row; later ones wait 90
MAX_FAILURES = 5  # more failures in a row than this stop the run
TIMEOUT = 30  # seconds to wait for a response
# Connection errors, timeouts, and connections reset partway through a response.
RETRIED = (requests.ConnectionError, requests.Timeout, requests.exceptions.ChunkedEncodingError)

SCHEMA = """
CREATE TABLE IF NOT EXISTS responses (
    key TEXT PRIMARY KEY,       -- request_key(method, url, body)
    method TEXT NOT NULL,
    url TEXT NOT NULL,
    body TEXT,                  -- the request's JSON body, canonical, or NULL
    status INTEGER NOT NULL,
    content BLOB NOT NULL,      -- the response body, gzipped
    content_type TEXT,
    fetched_at TEXT NOT NULL,   -- UTC, ISO 8601
    run_id INTEGER
);
CREATE TABLE IF NOT EXISTS runs (
    id INTEGER PRIMARY KEY,
    stage TEXT NOT NULL,
    version TEXT NOT NULL,      -- this package's version
    started_at TEXT NOT NULL,
    ended_at TEXT,
    outcome TEXT,               -- finished, stopped: <why>, interrupted or failed: <error>
    backend_version TEXT,       -- infosoud's backendVerze, for runs that use infosoud
    requests INTEGER NOT NULL DEFAULT 0,
    cache_hits INTEGER NOT NULL DEFAULT 0,
    failures INTEGER NOT NULL DEFAULT 0
);
CREATE TABLE IF NOT EXISTS pacing (
    id INTEGER PRIMARY KEY CHECK (id = 1),
    last_request REAL NOT NULL  -- Unix time of the last request from any process
);
"""


class StopRun(Exception):
    """The server pushed back (a 429, or too many failures in a row). Stop, and record it in the plan."""


class UnexpectedResponse(Exception):
    """A source answered in a way the pipeline doesn't know: our request is wrong, or the API changed."""


@dataclass(frozen=True)
class Response:
    url: str
    status: int
    content: bytes
    content_type: str | None
    fetched_at: str
    from_cache: bool

    @property
    def text(self):
        return self.content.decode("utf-8")

    def json(self):
        return json.loads(self.content)


def canonical(body):
    """A JSON body as text with sorted keys, so the same body always gives the same cache key."""
    if body is None:
        return None
    return json.dumps(body, sort_keys=True, ensure_ascii=False, separators=(",", ":"))


def request_key(method, url, body=None):
    text = f"{method.upper()} {url}\n{canonical(body) or ''}"
    return hashlib.sha256(text.encode("utf-8")).hexdigest()


def with_params(url, params):
    return f"{url}?{urlencode(params)}" if params else url


def utc_now():
    return datetime.now(UTC).isoformat(timespec="seconds")


def connect(path=paths.CACHE):
    """Open the cache, creating it if it's missing."""
    path.parent.mkdir(parents=True, exist_ok=True)
    db = sqlite3.connect(path, timeout=60, isolation_level=None)
    db.execute("PRAGMA journal_mode=WAL")  # so `soudai status` can read while a stage writes
    db.executescript(SCHEMA)
    return db


class Client:
    """A run of one stage: the cache, the pacing, the backoff and the run's log.

    `session`, `clock` and `sleep` are there for the tests.
    """

    def __init__(
        self,
        stage,
        cache=paths.CACHE,
        logs=paths.LOGS,
        session=None,
        clock=time.time,
        sleep=time.sleep,
        interval=INTERVAL,
    ):
        self.stage = stage
        self.cache = cache
        self.logs = logs
        self.session = session or requests.Session()
        self.session.headers["User-Agent"] = USER_AGENT
        self.clock = clock
        self.sleep = sleep
        self.interval = interval
        self.requests = self.cache_hits = self.failures = self.failures_in_a_row = 0

    def __enter__(self):
        self.db = connect(self.cache)
        started = utc_now()
        self.run_id = self.db.execute(
            "INSERT INTO runs (stage, version, started_at) VALUES (?, ?, ?)", (self.stage, VERSION, started)
        ).lastrowid
        self.log = self._open_log(started)
        self.log.info(f"Run {self.run_id}: {self.stage}, soudai {VERSION}")
        return self

    def __exit__(self, kind, error, traceback):
        if error is None:
            outcome = "finished"
        elif isinstance(error, StopRun):
            outcome = f"stopped: {error}"
        elif isinstance(error, KeyboardInterrupt):
            outcome = "interrupted"
        else:
            outcome = f"failed: {type(error).__name__}: {error}"
        self._save_counts(ended_at=utc_now(), outcome=outcome)
        self.log.info(
            f"Run {self.run_id} {outcome}: {self.requests} requests, {self.cache_hits} from the cache, "
            f"{self.failures} failures"
        )
        for handler in list(self.log.handlers):
            handler.close()
            self.log.removeHandler(handler)
        self.db.close()
        return False

    def get(self, url, params=None, refresh=False):
        return self.fetch("GET", with_params(url, params), refresh=refresh)

    def post(self, url, body, refresh=False):
        return self.fetch("POST", url, body, refresh=refresh)

    def cached(self, method, url, body=None):
        """The cached response to a request, or None, without fetching anything."""
        row = self.db.execute(
            "SELECT status, content, content_type, fetched_at FROM responses WHERE key = ?",
            (request_key(method, url, body),),
        ).fetchone()
        if row is None:
            return None
        status, content, content_type, fetched_at = row
        return Response(url, status, gzip.decompress(content), content_type, fetched_at, from_cache=True)

    def fetch(self, method, url, body=None, refresh=False):
        """The response to a request: from the cache if it's there, unless `refresh`, else from the server."""
        if not refresh and (response := self.cached(method, url, body)) is not None:
            self.cache_hits += 1
            return response
        while True:
            self._wait_turn()
            self.requests += 1
            started = time.perf_counter()
            try:
                reply = self.session.request(method, url, json=body, timeout=TIMEOUT)
            except RETRIED as error:
                self._failure(method, url, type(error).__name__)
                continue
            elapsed = time.perf_counter() - started
            sent = canonical(body) or ""
            self.log.debug(f"{method} {url} {sent} -> {reply.status_code} in {elapsed:.2f} s")
            if reply.status_code == 429:
                raise StopRun(f"HTTP 429 on {method} {url}")
            if reply.status_code >= 500:
                self._failure(method, url, f"HTTP {reply.status_code}")
                continue
            self.failures_in_a_row = 0
            response = Response(
                url, reply.status_code, reply.content, reply.headers.get("Content-Type"), utc_now(), False
            )
            self._store(method, body, response)
            return response

    def set_backend_version(self, backend_version):
        self.db.execute("UPDATE runs SET backend_version = ? WHERE id = ?", (backend_version, self.run_id))
        self.log.info(f"Backend version {backend_version}")

    def _wait_turn(self):
        """Claim the next request slot: `interval` after the last request from any process."""
        self.db.execute("BEGIN IMMEDIATE")  # other processes queue here until this one commits
        try:
            row = self.db.execute("SELECT last_request FROM pacing WHERE id = 1").fetchone()
            if row is not None:
                # Never more than one interval, in case the clock has jumped back.
                wait = min(row[0] + self.interval - self.clock(), self.interval)
                if wait > 0:
                    self.sleep(wait)
            self.db.execute("INSERT OR REPLACE INTO pacing (id, last_request) VALUES (1, ?)", (self.clock(),))
            self.db.execute("COMMIT")
        except BaseException:
            self.db.execute("ROLLBACK")
            raise

    def _failure(self, method, url, reason):
        self.failures += 1
        self.failures_in_a_row += 1
        self.log.warning(f"{method} {url}: {reason} ({self.failures_in_a_row} in a row)")
        self._save_counts()
        if self.failures_in_a_row > MAX_FAILURES:
            raise StopRun(f"{self.failures_in_a_row} failures in a row, the last on {method} {url}: {reason}")
        wait = BACKOFF[min(self.failures_in_a_row, len(BACKOFF)) - 1]
        self.log.info(f"Waiting {wait} s before retrying")
        self.sleep(wait)

    def _store(self, method, body, response):
        self.db.execute(
            "INSERT OR REPLACE INTO responses VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)",
            (
                request_key(method, response.url, body),
                method,
                response.url,
                canonical(body),
                response.status,
                gzip.compress(response.content),
                response.content_type,
                response.fetched_at,
                self.run_id,
            ),
        )
        self._save_counts()

    def _save_counts(self, **fields):
        fields |= {"requests": self.requests, "cache_hits": self.cache_hits, "failures": self.failures}
        columns = ", ".join(f"{name} = ?" for name in fields)
        self.db.execute(f"UPDATE runs SET {columns} WHERE id = ?", (*fields.values(), self.run_id))

    def _open_log(self, started):
        """A logger writing every request to the run's log file, and progress to the console."""
        self.logs.mkdir(parents=True, exist_ok=True)
        stamp = started.replace(":", "").replace("-", "").replace("+0000", "Z")
        self.log_path = self.logs / f"{self.stage}-{stamp}.log"
        log = logging.getLogger(f"soudai.run{self.run_id}.{id(self)}")
        log.setLevel(logging.DEBUG)
        log.propagate = False
        file_handler = logging.FileHandler(self.log_path, encoding="utf-8")
        file_handler.setFormatter(logging.Formatter("%(asctime)s %(levelname)s %(message)s"))
        console = logging.StreamHandler(sys.stderr)
        console.setLevel(logging.INFO)
        console.setFormatter(logging.Formatter("%(message)s"))
        log.addHandler(file_handler)
        log.addHandler(console)
        return log
