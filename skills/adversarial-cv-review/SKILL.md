---
name: adversarial-cv-review
description: Adversarial CV/resume review — build the reject case instead of praising. Use whenever the user asks to "review this CV/resume", "find red flags", "why would they reject me", "poke holes in this", "screen this candidate", or wants a hiring committee's worst-case read of a resume or a PR that adds one.
---

# Adversarial CV Review

Goal: build the strongest honest case AGAINST the candidate. Assume a skeptical
hiring manager with 200 other CVs. Do not list strengths unless asked.

## Rules

1. Findings first, verdict last. No praise, no "but overall strong".
2. Every flag needs evidence from the CV text. No invented biography.
3. Judge against the TARGET ROLE, not against "is this a good engineer".
4. Absence is evidence. What a candidate omits is the finding.
5. Reviewing the user's own CV? This is a stress test, not an insult. Say so once, then be brutal.

## Steps

1. **Anchor.** Get today's date and the target role. Compute real tenure in
   months for every job. Without the date you will misjudge every "Present".

2. **Timeline audit.** Gaps between end and next start. Year-only dates hiding
   months. Overlapping jobs. Graduation-to-first-job gap. Tenure under 18
   months. Currently leaving a job started recently — that is the headline flag.

3. **Claim audit.** For the role-critical skill, find the actual months of
   experience. Is it one job? Is it the current job? A CV is often a rebrand:
   old work relabelled with new keywords.

4. **Evidence asymmetry.** Compare bullet density and numbers across sections.
   Numbers everywhere EXCEPT the section that matters most means the important
   work is small, unshipped, or unmeasured. Flag it explicitly.

5. **Depth probe.** For the headline skill, list what a real practitioner would
   name and the CV does not. Missing sub-skills prove shallow exposure better
   than anything present proves depth.

6. **Verifiability.** No GitHub / LinkedIn / papers / talks / releases means
   nothing is checkable. Research or founder roles with zero public output are
   a strong flag.

7. **Outcome omissions.** Startup with no exit or revenue. Research with no
   papers. Migration with no result. Missing outcomes are chosen omissions.

8. **Trajectory.** Titles over time. Flat seniority across many years. Contract
   or agency titles presented as client titles. Self-awarded founder titles.
   Leadership claimed in a skills list but supported by no bullet.

9. **Fit and discretion.** Domain distance from the target. Also: does the CV
   leak a current employer's internal architecture, security model, or client
   data? That predicts future leaks.

10. **Internal contradictions.** Summary vs. dates ("10+ years" over a 17-year
    history). Claimed primary language vs. the language most jobs used.
    Padding: skills lists of 40+ items, decade-old tech beside current tech.

## Report format

```
## <N>. <Flag title>
<evidence quoted or cited from the CV>
<why a hiring manager discounts it, 1-3 lines>

## Verdict
No hire / hire — and the 2 flags that decide it.
Supporting doubts: <one line>
If you interview anyway, make them answer: <3-6 questions>
```

Order by how much each flag actually moves the decision, not by CV order.

## Say honestly

A CV cannot prove competence, only its absence. Most flags here are unresolved
questions, not proven faults — an interview or a reference resolves them and
this review cannot. Say which findings are hard contradictions in the text
versus which are suspicions from what is missing.
