"""Command-line entry point. Prints a plan unless --execute is supplied."""
import argparse
from workflow import Workflow


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--config", default="pipeline/configs/codex.toml")
    parser.add_argument("--run-dir", help="Resume an existing run with the same config")
    parser.add_argument("--execute", action="store_true", help="Run stages, including live model calls")
    parser.add_argument("--judge-start", type=int, default=1,
                        help="One-based judge pair to resume from; earlier results remain in reports")
    args = parser.parse_args()
    workflow = Workflow(args.config, args.run_dir)
    workflow.plan()
    if args.execute:
        workflow.prepare()
        workflow.fill()
        workflow.rank()
        workflow.filter()
        workflow.judge(start_pair=args.judge_start)
        workflow.analyze()


if __name__ == "__main__":
    main()
