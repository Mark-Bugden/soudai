"""Where the pipeline reads and writes, relative to the repository root."""

from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]

RAW = ROOT / "data" / "raw"  # the response cache and run logs: never committed, never deleted
CACHE = RAW / "cache.sqlite"
LOGS = RAW / "logs"
DERIVED = ROOT / "data" / "derived"  # tables from the parse steps, with no judges' names: committed
REFERENCE = ROOT / "reference"  # the hand-checked tables: committed
EXPORT = ROOT / "demo" / "public" / "data" / "soudai.json"  # the demo's data: committed
