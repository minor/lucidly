"""Quick script to test different parameter values and see ELO scores."""

from scoring import calculate_prompt_score

test_cases = [
    # (accuracy%, time_sec, cost$)
    ("Perfect, fast, cheap",              100, 10, 0.0005),
    ("Perfect, avg time, cheap",          100, 24, 0.0016),
    ("Perfect, slow, pricey",             100, 60, 0.01),
    ("Great accuracy, fast",              85, 15, 0.002),
    ("Good accuracy, avg",                70, 24, 0.003),
    ("Mediocre, slow",                    50, 45, 0.005),
    ("Low accuracy, fast",                25, 12, 0.001),
    ("Very low accuracy",                 10, 24, 0.0016),
    ("Zero accuracy",                      0, 24, 0.0016),
    ("Perfect but expensive",             100, 24, 0.10),
    ("50% accuracy, perfect else",        50, 12, 0.0001),
]

print(f"{'Description':<38} {'Acc%':>4} {'Time':>5} {'Cost':>8} │ {'ELO':>4}  Breakdown")
print("─" * 100)

for label, acc, time_s, cost in test_cases:
    score, bd = calculate_prompt_score(acc, time_s, cost)
    print(
        f"{label:<38} {acc:>4} {time_s:>5} ${cost:<7.4f} │ {score:>4}  "
        f"acc={bd['accuracy_contribution']:>+7.1f}  "
        f"time={bd['time_contribution']:>+6.1f}  "
        f"cost={bd['cost_contribution']:>+6.1f}"
    )

print()
print("─" * 100)
print()

# Interactive mode
print("Enter values to test (or 'q' to quit):")
while True:
    try:
        raw_input = input("\naccuracy% time_sec cost$ > ").strip()
        if raw_input.lower() in ('q', 'quit', 'exit', ''):
            break
        parts = raw_input.split()
        if len(parts) != 3:
            print("  Need 3 values: accuracy% time_sec cost$")
            continue
        acc, time_s, cost = float(parts[0]), float(parts[1]), float(parts[2])
        score, bd = calculate_prompt_score(acc, time_s, cost)
        print(f"  ELO: {score}")
        print(f"    accuracy:  {bd['accuracy_contribution']:>+7.1f}")
        print(f"    time:      {bd['time_contribution']:>+7.1f}")
        print(f"    cost:      {bd['cost_contribution']:>+7.1f}")
    except (ValueError, KeyboardInterrupt):
        break
