"""Command-line entry point for CogniPrime.

Runs a single Agentic-OS tick against whatever layers and monitor are wired up.
By default it is inert (no API key, deny-all approval) — it prints the control
flow so you can see the operating system's cycle without acting on anything.
"""

from __future__ import annotations

import argparse
import sys

from cogniprime.config import CogniPrimeConfig
from cogniprime.orchestrator import CogniPrime


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(prog="cogniprime", description=__doc__)
    parser.add_argument("--model", default=CogniPrimeConfig().model, help="Claude model ID")
    parser.add_argument(
        "--effort",
        default="high",
        choices=["low", "medium", "high", "xhigh", "max"],
        help="Default reasoning effort",
    )
    parser.add_argument(
        "--no-launch",
        action="store_true",
        help="Skip venture spin-off during the tick",
    )
    args = parser.parse_args(argv)

    config = CogniPrimeConfig(model=args.model, effort=args.effort)
    if config.api_key is None:
        print(
            "No ANTHROPIC_API_KEY configured — CogniPrime needs credentials to reason.\n"
            "Set ANTHROPIC_API_KEY or run `ant auth login`, then re-run.",
            file=sys.stderr,
        )
        return 1

    os = CogniPrime(config)
    result = os.tick(launch_ventures=not args.no_launch)
    for line in result.trace:
        print(line)
    return 0


if __name__ == "__main__":  # pragma: no cover
    raise SystemExit(main())
