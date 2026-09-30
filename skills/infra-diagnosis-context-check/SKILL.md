---
name: infra-diagnosis-context-check
description: Diagnose infrastructure, Kubernetes, Helm, Terraform, CI/CD, and cloud issues without producing confident-but-wrong answers. Audits what context is actually present, then returns competing hypotheses each paired with a cheap discriminating check instead of one authoritative-sounding diagnosis. Use whenever the user describes anything broken, misconfigured, drifting, or "suspected infra" — failing pods, ingress not routing, unexpected terraform apply, env-specific breakage, DNS/TLS problems, chart values not taking effect, permissions errors, works-in-staging-not-prod — and when they paste logs, manifests, or .tf files asking why something happens. Trigger even for a single pasted error where the user seems to want a quick answer, since a quick confident answer is the exact failure mode this prevents.
---

# Infra Diagnosis: Context Check

A model cannot tell "I have this information" from "I don't." Missing context gets silently filled with the most common configuration — a typical chart, a typical VPC, default provider behavior — and the answer reads just as fluently as a correct one. So fluency carries no signal about sufficiency. Gaps must be made structurally visible in the output.

Two infra-specific traps: **source ≠ reality** (repos describe intent; drift and manual changes mean deployed state differs), and in multi-repo orgs **the file the user pasted is often not the file that caused the behavior**.

## 1. Audit context first

Every time, including when the answer seems obvious. Check what is actually known vs. substituted with a default:

- **What changed and when** — commits, deploy history, last known-good. Infra failures are overwhelmingly change-induced; without this, every hypothesis is plausible and none is testable.
- **Rendered state, not source** — `helm get manifest`, not `values.yaml`; `terraform plan` / `state show`, not `.tf`.
- **Exact error text with timestamps** — paraphrase destroys the detail that would have discriminated.
- **Versions** — chart, provider, module, k8s, CLI. Version-dependent behavior is a top cause of confidently wrong answers.
- **Scope** — which env/cluster/namespace; one replica or all; regression or new; intermittent or constant.
- **Their access level** — establish this before requesting anything. Many people can see only the symptom, a CloudWatch/console view, or a CI log, with no `kubectl`, `helm`, or `terraform` in prod. Asking for output they cannot produce wastes a round trip and pushes them toward guessing.

`references/context-packs.md` has the read-only commands producing each of these per stack, plus console-only and symptom-only substitutes. Read it when telling the user what to collect.

## 2. Gate on the audit

If a gap would change the conclusion, say so and name the **exact command** needed — never "can you share more about your setup," which pushes the diagnostic work back onto someone who doesn't know which detail matters. Ask for 1–3 commands max, ranked by information gained per effort.

If gaps remain but partial reasoning still helps, give it marked provisional. Don't stall when something can be narrowed with what's present.

## 2b. When they can't run the check

Limited access does not license a more confident answer — it demands a wider hypothesis set. The temptation runs the other way: less evidence means more gaps filled with plausible defaults. Resist it explicitly.

Work down this ladder for each hypothesis:

1. **Substitute an observable at their level** — CloudWatch Logs Insights query instead of `kubectl logs`; console resource view instead of `terraform state show`; CI job log instead of `helm get values`; APM/Grafana instead of `top pods`. The reference file lists these.
2. **Infer from symptom shape** — status code, exact timeout duration, intermittent-vs-constant, which requests fail. This narrows honestly but rarely resolves; say which hypotheses remain live.
3. **Write the escalation ask** — when nothing at their level discriminates, say so plainly and draft the exact request for whoever has access: the specific command, why it's needed, and what each possible output would mean. A well-formed ask they can forward is a real deliverable, not a failure.

Never let a hypothesis stay unresolved *and* unlabeled. If the evidence to test it is out of reach, mark it that way rather than quietly ranking it low.

## 3. Answer as differential diagnosis

```
## What I can see
[only what was actually supplied or retrieved]

## What I don't have
[gaps that matter, and why]

## Hypotheses
### H1 — [name] (most likely)
Mechanism: [why this produces exactly these symptoms]
Doesn't explain: [any symptom it fails to cover]
Check: `[one command]` → confirms if X, rules out if Y

### H2 / H3 — same fields

## Do this next
[cheapest check that splits the hypothesis space most]
```

- Every hypothesis needs a check whose output **differs** between hypotheses. A claim with no verifying command, file, or log line is a guess — label it one.
- Order checks by information gained, not by likelihood. Eliminating two hypotheses beats confirming the leading one.
- Prefer read-only inspection over trying a change. A speculative fix can cause a second incident on top of the first.
- Don't manufacture three hypotheses when evidence supports one. Say so, and still give the confirming check.
- Label claims **Verified** (visible in supplied artifacts), **Inferred**, or **Assumed** (default substituted — state what breaks if wrong).

## 4. Check the draft before sending

- Does it name a resource, field, flag, or file the user never mentioned? That was invented.
- Would it fit any company's setup? Then it isn't grounded in theirs.
- Does it explain **every** symptom, including the small odd one? A diagnosis that quietly skips one detail is usually wrong, and that detail is usually the cause. Surface it under "Doesn't explain."
- Was the user's own theory accepted uncritically? Their framing is a hypothesis, not evidence. Same for agreement carried by conversational momentum — earlier turns aren't evidence.

## 5. Iterating

State which hypotheses new evidence killed rather than silently pivoting to a new theory — a quiet pivot hides that the earlier confidence was unwarranted.

When a suggestion fails, ask what it output; that output is often more diagnostic than anything prior. **After two failed fixes, stop generating fixes** — the model of the problem is wrong. Restart from observation and point the user at primary sources (logs, provider docs, upstream chart). Convincing prose creates sunk cost and can burn hours on a plausible-but-wrong branch.
