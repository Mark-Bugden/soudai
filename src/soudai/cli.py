"""`uv run soudai <stage>`: the pipeline's stages, in the order they run.

The plan's later stages (decisions, senates, intake, sample, analyse, export) join as their milestones
are built.
"""

import argparse
import sys

from . import courts, events, status


def main(argv=None):
    # Court names are Czech, and Windows consoles default to a code page without č or ř.
    for stream in (sys.stdout, sys.stderr):
        stream.reconfigure(encoding="utf-8")
    parser = argparse.ArgumentParser(prog="soudai", description="The Judging the Journey data pipeline.")
    stages = parser.add_subparsers(dest="stage", required=True, metavar="<stage>")
    stage = stages.add_parser("courts", help="check reference/courts.csv against infosoud's court lists")
    stage.add_argument("--write", action="store_true", help="write reference/courts.csv afresh")
    stages.add_parser("events", help="refresh reference/events.csv's Czech labels from infosoud's app")
    stages.add_parser("status", help="report each stage's progress, from the cache and the tables")
    args = parser.parse_args(argv)
    if args.stage == "courts":
        return courts.run(write=args.write)
    if args.stage == "events":
        return events.run()
    return status.run()


if __name__ == "__main__":
    sys.exit(main())
