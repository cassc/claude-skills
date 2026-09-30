---
name: play-prod-access
description: Draft answers for the Google Play Console "Apply for access to production" questionnaire (closed-test recruitment, tester engagement, feedback summary, intended audience, app value, expected installs, changes made, production readiness). Use when the user is filling out Play Store production access, app review, or closed-test application questions and wants honest, concise answers within character/word limits, grounded in their git history.
---

# Google Play production access answers

Help the user answer the Play Console production-access questionnaire. Answers must be honest, concrete, and within the stated limit (Google often uses a 300-character cap, sometimes 300 words — confirm which).

## Workflow

1. **Confirm the limit.** Ask or check whether the question caps at 300 characters or 300 words. Always state your draft's count in parentheses after it.
2. **Ground in git history.** Read recent commits and tags to learn what the app actually does and what changed:
   - `git log --since="N days ago" --pretty=format:"%h %ad %s" --date=short`
   - `git tag --sort=-creatordate | head` — the latest tag is usually the latest closed-test build; later commits may be unreleased.
3. **Be honest, not inflated.** Disclose paid testers, sample data, single-country testers, etc. Hiding is riskier than disclosing. Modest install estimates are safer than big ones.
4. **One app at a time.** Production access is granted per app — each app needs its own form. Offer a separately tailored version if the user has multiple apps.
5. **Plain text, copy-paste ready** when asked. No markdown, no preamble.

## Question playbook

| Question | What to cover |
|---|---|
| How did you recruit testers? | Truthful channels: friends/family, communities, tester-exchange groups, paid provider (name it). |
| Describe tester engagement | Which features were used (core flows most, advanced less); whether usage matched real users. Note differences: paid testers use sample data in short sessions vs. real users entering genuine data, returning over months. |
| Summarize feedback + how collected | Collection method (DMs, chats, provider reports) + key praise + suggestions you acted on. |
| Intended audience | Who the app is for, in plain terms. |
| How app provides value | Core benefit + standout features. |
| Expected first-year installs | Realistic range. New indie/no marketing: 100–1,000. Don't overpromise. |
| Changes made from closed test | Concrete feedback-driven fixes, pulled from commit history. |
| How you decided it's ready | Stability, core flows work, feedback fixes done, real value shown. |

## Style

- Lead with the answer; cut filler.
- Prefer specific features over vague claims.
- Keep paid-tester honesty consistent across all answers (don't claim deep real-world usage in one answer then disclose sample data in another).
