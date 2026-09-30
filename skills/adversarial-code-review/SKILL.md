---
name: adversarial-code-review
description: Adversarial code review — hunt for bugs instead of approving. Use whenever the user asks to "review this code", "check for bugs", "is this correct", "before I merge", or right after you wrote non-trivial code and the user wants it verified.
---

# Adversarial Code Review

Goal: find defects, not assess quality. Assume at least one bug exists.

## Rules

1. No verdict first, no praise. Findings only; verdict last.
2. Judge against the spec (what the code SHOULD do), not the code's intent.
3. If reviewing code you wrote yourself: ignore your earlier reasoning, list the assumptions you made while writing — check those first.

## Steps

1. **State the contract** (1-2 lines): expected inputs, outputs, error behavior. Unclear? Ask — that's a finding.
2. **Hostile read** — for each risky line ask "how do I break this?" Check: empty/null/zero/negative/max inputs; failed calls and swallowed errors; shared-state mutation and races; unclosed resources; injection/unvalidated input; unverified library assumptions.
3. **Falsify** — for the 2-3 riskiest spots, construct a concrete input that produces a wrong result and trace it. Can't? Say what you tried.
4. **Run real checks** if environment allows: execute the failing input, run tests/type checker/linter. Say which you ran vs. only reasoned about.

## Report format

```
## Findings (sorted by severity)
1. [BUG|RISK|SMELL] title — file:line
   Trigger: <concrete input>
   Fix: <one line>

## Unverified assumptions
## Checks: ran ✅ / reasoned only ❌
```

BUG = wrong behavior now. RISK = breaks later. SMELL = style. Don't pad with SMELLs.

## Say honestly

Same-model review can't catch a misunderstood requirement or wrong library belief — the same blind spot reviews itself. Tests and type checkers are the uncorrelated checks; recommend them.
