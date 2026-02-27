#!/usr/bin/env python3
"""
Scoring Model Test Script
=========================
Run with no args to see all preset scenarios.
Run with args to test custom parameters.

Usage:
  python test_scoring.py
  python test_scoring.py --accuracy 67 --time 137 --turns 1 --cost 0.032
  python test_scoring.py -a 67 -t 137 -n 1 -c 0.032

Interactive mode:
  python test_scoring.py -i
"""

import argparse
import sys

from scoring import calculate_prompt_score


# ── Display helpers ──────────────────────────────────────────────────────────

CYAN = "\033[96m"
GREEN = "\033[92m"
YELLOW = "\033[93m"
RED = "\033[91m"
BOLD = "\033[1m"
DIM = "\033[2m"
RESET = "\033[0m"


def score_color(score):
    if score >= 750:
        return GREEN
    elif score >= 500:
        return YELLOW
    else:
        return RED


def component_bar(value, width=20):
    """Render a -1 to +1 value as a visual bar centered at 0."""
    mid = width // 2
    filled = round(abs(value) * mid)
    if value >= 0:
        left = " " * mid
        right = "█" * filled + "░" * (mid - filled)
        return f"{DIM}{left}{RESET}{GREEN}{right}{RESET}"
    else:
        padding = mid - filled
        left = "░" * padding + "█" * filled
        right = " " * mid
        return f"{RED}{left}{RESET}{DIM}{right}{RESET}"


def print_detailed(accuracy, time_seconds, num_turns, cost_dollars):
    """Print a full detailed breakdown for one set of parameters."""
    score, bk = calculate_prompt_score(accuracy, time_seconds, cost_dollars, num_turns)
    raw = bk["raw_components"]
    color = score_color(score)

    print(f"\n  {BOLD}{'─' * 56}{RESET}")
    print(f"  {BOLD}  INPUTS{RESET}")
    print(f"  {BOLD}{'─' * 56}{RESET}")
    print(f"    Accuracy:  {accuracy}%")
    print(f"    Time:      {int(time_seconds // 60)}:{int(time_seconds % 60):02d}")
    print(f"    Turns:     {num_turns}")
    print(f"    Cost:      ${cost_dollars:.4f}")
    print(f"  {BOLD}{'─' * 56}{RESET}")
    print(f"  {BOLD}  SCORE: {color}{score}{RESET}")
    print(f"  {BOLD}{'─' * 56}{RESET}")
    print(f"  {BOLD}  COMPONENT BREAKDOWN{RESET}")
    print(f"  {'─' * 56}")

    labels = [
        ("Accuracy (60%)", "accuracy", bk["accuracy_contribution"]),
        ("Time     (15%)", "time",     bk["time_contribution"]),
        ("Cost     (15%)", "cost",     bk["cost_contribution"]),
        ("Turns    (10%)", "turns",    bk["turns_contribution"]),
    ]
    for label, key, contrib in labels:
        rv = raw[key]
        bar = component_bar(rv)
        print(f"    {label}  {bar}  {rv:>+.3f}  ({contrib:>+7.1f} pts)")

    if bk["low_accuracy_penalty_multiplier"] < 1.0:
        print(f"\n    {RED}⚠ Low accuracy penalty: ×{bk['low_accuracy_penalty_multiplier']:.3f}{RESET}")

    print(f"  {'─' * 56}\n")


def print_table(scenarios):
    """Print a compact comparison table."""
    header = f"  {BOLD}{'SCENARIO':<42} {'SCORE':>5}  {'ACC':>5} {'TIME':>5} {'COST':>5} {'TURN':>5}{RESET}"
    sep = f"  {'─' * 72}"
    print(sep)
    print(header)
    print(sep)
    for name, acc, time_s, turns, cost in scenarios:
        score, bk = calculate_prompt_score(acc, time_s, cost, turns)
        raw = bk["raw_components"]
        color = score_color(score)
        print(
            f"  {name:<42} {color}{score:>5}{RESET}"
            f"  {raw['accuracy']:>+.2f} {raw['time']:>+.2f} {raw['cost']:>+.2f} {raw['turns']:>+.2f}"
        )
    print(sep)


# ── Preset scenarios ─────────────────────────────────────────────────────────

PRESETS = [
    # (label, accuracy%, time_s, turns, cost$)
    ("Perfect (100%, 30s, 1t, $0.005)",       100, 30,  1, 0.005),
    ("Great (90%, 45s, 1t, $0.01)",            90, 45,  1, 0.01),
    ("Good (80%, 60s, 2t, $0.02)",             80, 60,  2, 0.02),
    ("Above avg (67%, 137s, 1t, $0.032)",      67, 137, 1, 0.032),
    ("Average (67%, 90s, 3t, $0.05)",          67, 90,  3, 0.05),
    ("Below avg (50%, 120s, 4t, $0.10)",       50, 120, 4, 0.10),
    ("Poor (30%, 180s, 4t, $0.20)",            30, 180, 4, 0.20),
    ("Awful (10%, 300s, 4t, $0.50)",           10, 300, 4, 0.50),
    ("Fast but wrong (20%, 15s, 1t, $0.003)",  20, 15,  1, 0.003),
    ("Slow but right (95%, 240s, 2t, $0.15)",  95, 240, 2, 0.15),
    ("Cheap & quick (75%, 30s, 1t, $0.003)",   75, 30,  1, 0.003),
    ("Expensive (85%, 60s, 2t, $0.50)",        85, 60,  2, 0.50),
]


# ── Interactive mode ─────────────────────────────────────────────────────────

def interactive_mode():
    print(f"\n  {BOLD}Interactive Scoring Test{RESET}")
    print(f"  Type 'q' to quit, 'presets' to show preset table.\n")

    while True:
        try:
            line = input(f"  {CYAN}Enter accuracy% time_s turns cost${RESET} > ").strip()
        except (EOFError, KeyboardInterrupt):
            print()
            break

        if not line or line.lower() == "q":
            break
        if line.lower() == "presets":
            print_table(PRESETS)
            continue

        parts = line.split()
        if len(parts) != 4:
            print(f"  {RED}Need 4 values: accuracy% time_seconds turns cost_dollars{RESET}")
            print(f"  {DIM}Example: 67 137 1 0.032{RESET}")
            continue

        try:
            acc = float(parts[0])
            time_s = float(parts[1])
            turns = int(parts[2])
            cost = float(parts[3])
        except ValueError:
            print(f"  {RED}Invalid numbers. Example: 67 137 1 0.032{RESET}")
            continue

        print_detailed(acc, time_s, turns, cost)


# ── Main ─────────────────────────────────────────────────────────────────────

def main():
    parser = argparse.ArgumentParser(
        description="Test the prompt scoring model",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="Examples:\n"
               "  python test_scoring.py                              # show all presets\n"
               "  python test_scoring.py -a 67 -t 137 -n 1 -c 0.032  # test specific params\n"
               "  python test_scoring.py -i                           # interactive mode\n",
    )
    parser.add_argument("-a", "--accuracy", type=float, help="Accuracy (0-100%%)")
    parser.add_argument("-t", "--time", type=float, help="Time in seconds")
    parser.add_argument("-n", "--turns", type=int, help="Number of turns (1-4)")
    parser.add_argument("-c", "--cost", type=float, help="Cost in dollars")
    parser.add_argument("-i", "--interactive", action="store_true", help="Interactive mode")

    args = parser.parse_args()

    if args.interactive:
        interactive_mode()
    elif all(v is not None for v in [args.accuracy, args.time, args.turns, args.cost]):
        print_detailed(args.accuracy, args.time, args.turns, args.cost)
    elif any(v is not None for v in [args.accuracy, args.time, args.turns, args.cost]):
        print(f"  {RED}Provide all four: --accuracy, --time, --turns, --cost{RESET}")
        sys.exit(1)
    else:
        print(f"\n  {BOLD}Preset Scenarios{RESET}")
        print_table(PRESETS)
        print(f"\n  {DIM}Run with -i for interactive mode, or -a/-t/-n/-c for custom params.{RESET}\n")


if __name__ == "__main__":
    main()