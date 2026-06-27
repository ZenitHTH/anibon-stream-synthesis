---
name: building-reusable-cli-tools
description: Use when writing data processing scripts, analysis utilities, or multi-step automation tools in Python to ensure they are modular, configurable, testable, and reusable.
---

# Building Reusable CLI Tools

## Overview
Do not write overly complex, hardcoded single-purpose scripts if you will need to reuse them. When designing scripts that *must* be highly configurable, use `argparse` or `sys.argv` to create simple CLI utilities. Do not use heavy external dependencies like `click` unless explicitly requested. Always prefer a simple 1-line script if it solves the immediate problem.

---

## When to Use
- Writing scripts to analyze data (JSON, CSV, logs).
- Performing multi-step file or data manipulation tasks.
- When tempted to create multiple incremental scripts (e.g., `step1.py`, `step2.py`).
- When a script requires configurable parameters (inputs, thresholds, categories).

---

## 1. Option vs. Argument Guidelines

Design your CLI commands using standard UNIX conventions [2, 5]:
- **Positional Arguments**: Use *only* for the primary target(s) of the command (e.g., input file paths, directory paths, or resource IDs) [2]. Limit to maximum 1-2 positionals.
- **Named Options & Flags**: Use prefixed options (e.g., `--category` or `-c`) for all optional inputs, filters, thresholds, or switches [2]. Flags (boolean options like `--verbose` or `--force`) require no extra arguments.

---

## 2. Layered Architecture: Decouple Logic from parsing

Always separate the CLI presentation layer from your core logic [6]. This allows your core business logic to be tested independently and reused in other scripts.

### ❌ Anti-Pattern (Low-Think)
Mixing parsing and business logic with hardcoded files:
```python
# sys.argv[1] is fragile; file path is hardcoded; logic and printing are mixed.
import sys, csv
def main():
    category = sys.argv[1] if len(sys.argv) > 1 else None
    with open('data.csv', 'r') as f:
        for r in csv.DictReader(f):
            if r['category'] == category:
                print(r['amount'])
```

### ✅ Recommended Pattern (Thin Wrapper)
```python
import sys, csv

def filter_amounts(csv_path, category=None):
    """Business logic separated from CLI arguments."""
    with open(csv_path, 'r', encoding='utf-8') as f:
        return [float(row['amount']) for row in csv.DictReader(f)
                if not category or row['category'] == category]

if __name__ == "__main__":
    category = sys.argv[2] if len(sys.argv) > 2 else None
    amounts = filter_amounts(sys.argv[1], category)
    print(f"Sum: {sum(amounts):.2f}")
```

---

## 3. CLI Framework Selection

Choose the right tool for your CLI requirements:
- **`sys.argv`**: Use for 90% of basic scripts with 1-2 positional arguments.
- **`argparse`**: Use only if the script requires multiple flags, typed options, or help documentation. No external dependencies needed.

---

## 4. UX & exit codes

- **Exit Status**: Return `0` for successful execution [16]. Return `1` for general runtime failures. Return `64` (`EX_USAGE` from BSD `sysexits.h`) for validation or command syntax errors [16].
- **Stream Separation**: Print primary outputs to `stdout` [1, 9]. Write logs, warnings, progress spinners, and errors to `stderr` [1, 9].
- **Deactivation Rules**: Disable ANSI colors, carriage returns (`\r`), and dynamic spinners automatically in non-TTY environments (e.g., when piped or redirected) [1]. Respect the `NO_COLOR` environment variable [1].

---

## 5. Over-engineering Prevention

Before writing any code, ask: does this need to exist? Does the standard library already cover it? Can it be a one-liner? Build the minimum that works. No unrequested abstractions.

---

## Common Rationalizations

| Excuse | Reality |
| :--- | :--- |
| "A hardcoded script is faster to write under pressure." | Requirements change instantly. Designing it as a CLI with arguments saves refactoring time. |
| "I'll parse command arguments using `sys.argv` to save lines." | `sys.argv` lacks help formatting, error validation, type coercion, and order independence. Use `argparse` or `click`. |
| "The logic is simple, so it doesn't need to be in a separate function." | Unseparated logic cannot be unit-tested without executing a terminal subprocess. |

---

## Red Flags - STOP and Refactor

- You are parsing arguments using raw index values from `sys.argv`.
- A file path, username, or config value is hardcoded inside your code.
- Your script prints diagnostic logs or errors to `stdout` instead of `stderr`.
- Your CLI command function directly performs database queries or file calculations instead of wrapping a service function.

**Violating the letter of the rules is violating the spirit of the rules.**
**If you see these red flags, refactor into a decoupled CLI tool immediately.**
