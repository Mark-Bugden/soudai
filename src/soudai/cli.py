"""`uv run soudai <stage>`: the pipeline's stages, in the order they run."""

import argparse
import sys
from datetime import date

from . import courts, decisions, events, export, intake, journey, model, official, sample, senates, status
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
    stage = stages.add_parser(
        "sample", help="fetch the timelines of a random sample of cases, and parse them"
    )
    stage.add_argument("--parse-only", action="store_true", help="parse what's cached, fetching nothing")
    stages.add_parser("official", help="compare intake with the Ministry's official statistics, S_AS_40")
    stages.add_parser("analyse", help="compute the journey numbers, for all courts and for each court")
    stages.add_parser("model", help="fit the remaining-time forecasts on the earlier cases and score them")
    stages.add_parser("export", help="write the demo's data, demo/public/data/soudai.json")
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
        if args.stage == "sample":
            return sample.run(parse_only=args.parse_only)
        if args.stage == "official":
            return official.run()
        if args.stage == "analyse":
            return journey.run()
        if args.stage == "model":
            return model.run()
        if args.stage == "export":
            return export.run()
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
