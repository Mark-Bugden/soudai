"""`uv run soudai <stage>`: the pipeline's stages, in the order they run.

The plan's later stages (sample, analyse, export) join as their milestones are built.
"""

import argparse
import sys
from datetime import date

from . import courts, decisions, events, intake, senates, status
from .http import NotCached, StopRun, UnexpectedResponse


def main(argv=None):
    # Court names are Czech, and Windows consoles default to a code page without č or ř.
    for stream in (sys.stdout, sys.stderr):
        stream.reconfigure(encoding="utf-8")
    parser = argparse.ArgumentParser(prog="soudai", description="The Judging the Journey data pipeline.")
    stages = parser.add_subparsers(dest="stage", required=True, metavar="<stage>")
    stage = stages.add_parser("courts", help="check reference/courts.csv against infosoud's court lists")
    stage.add_argument("--write", action="store_true", help="write reference/courts.csv afresh")
    stages.add_parser("events", help="refresh reference/events.csv's Czech labels from infosoud's app")
    stage = stages.add_parser("decisions", help="list rozhodnuti's published decisions, and parse them")
    stage.add_argument("--until", type=date.fromisoformat, help="the last day to list (default: yesterday)")
    stage.add_argument("--parse-only", action="store_true", help="parse what's cached, fetching nothing")
    stages.add_parser("senates", help="find each court's senates for each year, 2020-2025")
    stages.add_parser("intake", help="count the cases each senate registered each year")
    stages.add_parser("status", help="report each stage's progress, from the cache and the tables")
    args = parser.parse_args(argv)
    try:
        if args.stage == "courts":
            return courts.run(write=args.write)
        if args.stage == "events":
            return events.run()
        if args.stage == "decisions":
            return decisions.run(until=args.until, parse_only=args.parse_only)
        if args.stage == "senates":
            return senates.run()
        if args.stage == "intake":
            return intake.run()
        return status.run()
    except StopRun as error:
        print(f"Stopped: {error}. Record it in docs/plan.md before running again.", file=sys.stderr)
        return 3
    except UnexpectedResponse as error:
        print(f"Unexpected response: {error}", file=sys.stderr)
        return 4
    except NotCached as error:
        print(f"Not in the cache: {error}. Run the stage without --parse-only first.", file=sys.stderr)
        return 5


if __name__ == "__main__":
    sys.exit(main())
