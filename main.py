#!/usr/bin/env python3
"""PeakForm CLI — Weekly Fitness & Nutrition Intelligence Agent.

Usage:
    python main.py --mf-file data/macrofactor.xlsx --garmin-file data/garmin.csv
    python main.py --mf-file data/macrofactor.xlsx --garmin-file data/garmin.csv --week 2026-02-16
    python main.py --mf-file data/macrofactor.xlsx --garmin-file data/garmin.csv --output report.md
"""

import argparse
import sys
from pathlib import Path


def _parse_args():
    parser = argparse.ArgumentParser(
        prog="peakform",
        description="PeakForm — Weekly Fitness & Nutrition Intelligence Agent for Ben",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  # Analyze the current week (Mon–Sun):
  python main.py --mf-file exports/macrofactor.xlsx --garmin-file exports/garmin.csv

  # Analyze a specific week (any ISO date within the week):
  python main.py --mf-file exports/macrofactor.xlsx --garmin-file exports/garmin.csv --week 2026-02-16

  # Save report to a file:
  python main.py --mf-file exports/macrofactor.xlsx --garmin-file exports/garmin.csv --output weekly_report.md

  # Plain text output (no rich formatting):
  python main.py --mf-file exports/macrofactor.xlsx --garmin-file exports/garmin.csv --plain
        """,
    )

    parser.add_argument(
        "--mf-file",
        required=True,
        metavar="PATH",
        help="Path to MacroFactor XLSX export",
    )
    parser.add_argument(
        "--garmin-file",
        required=True,
        metavar="PATH",
        help="Path to Garmin Connect CSV export",
    )
    parser.add_argument(
        "--week",
        default=None,
        metavar="YYYY-MM-DD",
        help=(
            "Any ISO date within the target Mon–Sun week. "
            "Defaults to the current calendar week."
        ),
    )
    parser.add_argument(
        "--output",
        default=None,
        metavar="PATH",
        help="Write Markdown report to this file (default: print to stdout)",
    )
    parser.add_argument(
        "--plain",
        action="store_true",
        help="Print plain Markdown text without rich terminal rendering",
    )
    parser.add_argument(
        "--verbose",
        "-v",
        action="store_true",
        help="Print progress messages to stderr",
    )

    return parser.parse_args()


def _render_rich(markdown_text: str) -> None:
    """Render Markdown to terminal using rich."""
    from rich.console import Console
    from rich.markdown import Markdown

    console = Console()
    md = Markdown(markdown_text)
    console.print(md)


def main():
    args = _parse_args()

    # Validate input file paths
    mf_path = Path(args.mf_file)
    garmin_path = Path(args.garmin_file)

    if not mf_path.exists():
        print(f"Error: MacroFactor file not found: {mf_path}", file=sys.stderr)
        sys.exit(1)
    if not garmin_path.exists():
        print(f"Error: Garmin file not found: {garmin_path}", file=sys.stderr)
        sys.exit(1)

    # Run the agent
    try:
        from peakform.agent import run
        report_md = run(
            mf_filepath=str(mf_path),
            garmin_filepath=str(garmin_path),
            week=args.week,
            verbose=args.verbose,
        )
    except Exception as e:
        print(f"Error running analysis: {e}", file=sys.stderr)
        if args.verbose:
            import traceback
            traceback.print_exc()
        sys.exit(1)

    # Output
    if args.output:
        output_path = Path(args.output)
        output_path.write_text(report_md, encoding="utf-8")
        print(f"Report written to: {output_path}", file=sys.stderr)
    else:
        if args.plain:
            print(report_md)
        else:
            try:
                _render_rich(report_md)
            except ImportError:
                # rich not available — fall back to plain text
                print(report_md)


if __name__ == "__main__":
    main()
