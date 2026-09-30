---
name: building-study-cards-from-repos
description: Use when the user wants to learn or review the concepts in a repo (course, lab, tutorial, docs, codebase) through slide-like study cards, flashcards, interview-prep questions, a quiz, or a page where Claude answers questions and quizzes them live.
---

# Building study cards from a repo

## Overview
A local web page that teaches a repo's concepts: slide cards, likely
questions, diagram walk-throughs, a multiple-choice quiz, and a side chat
where Claude Code (running in the repo, read-only) answers questions about
the current card, suggests better cards, and quizzes with graded free-text
answers.

**Core principle: first principles.** Every technique exists because of a
root limit. Teach the limit first, then show the idea as its consequence,
then the evidence. Test the *reason*, never recall of names or numbers.

## Setup
1. Copy `template/` (next to this file) into the repo, e.g. `learn/`.
   The server treats the folder's parent as the repo root.
2. Replace `{{TITLE}}` (index.html, both prompts) and `{{SOURCES}}` (both
   prompts: the doc paths Claude should read).
3. Set `ASSETS` in `server.py` to repo-relative image dirs, if any.
4. Write content (below) into `cards.js`, `quiz.js`, `diagrams.js`.
5. Run `python3 learn/server.py`, open http://127.0.0.1:8765.
   `PORT=8766` runs a second copy. Cards and quiz also work from `file://`
   (no chat).

## Content recipe
Read the repo's own teaching material first (README, lesson folders,
cheat sheets, review questions, eval results). One lesson = one topic.

Per lesson, in this order:
- **1 first-principle card** (`fp: true`): the root limit and "So: ...".
- **4-7 concept cards**: title is a "Why ...?" or a claim. Body:
  `Problem: ... So: ... Evidence: <real number/output from the repo>`.
  Under ~60 words. Include the honest results (where the fancy method lost).
- **4-5 likely questions** (`qa`): interview style. Answer starts from the
  root cause, then the idea, then one trade-off.
- **3-4 quiz items**: each asks "why" or "what breaks if". Distractors are
  plausible wrong causes. `e` = one-line cause.
- **Diagrams** (only if the repo has them): list the steps in order with a
  short "why" note each; mark repeated steps `loop: true`. The step list is
  the clean view; the image is the reference.

Use plain, simple English and short sentences.

## Source code repos
No lessons or results to copy: find the topics yourself.
- **Lesson** = one module or subsystem (auth, storage, request flow).
- **First principle** = the problem the design must handle (concurrency,
  latency, failure, scale).
- **Evidence** = `file:line`, a test, a benchmark, or a commit that shows why.
- **Diagrams**: usually none; use a step list for one request or data flow.
- **`{{SOURCES}}`**: core source dirs, README, ADRs/design docs. Not the whole
  repo on big codebases (chat gets slow).
- **Quiz**: "what breaks if we remove X?", "why here and not in Y?".
- Every "why" cites code or a commit. If the reason is a guess, the card says so.

## Quick reference
| File | Role |
|---|---|
| `cards.js` | `LESSONS` - cards + qa per lesson |
| `quiz.js` | `QUIZ` - multiple choice per lesson id |
| `diagrams.js` | `DIAGRAMS` - image + ordered steps |
| `ask_prompt.md` / `quiz_prompt.md` | Claude's rules per chat mode |
| `extra-cards.json` | cards the learner approved from chat; commit it |
| `server.py` | static files, `/api/chat` (`claude -p --resume`, tools Read/Grep/Glob), `/api/cards` |

## Verify
- `node -e` eval the three data files; every `a < o.length`.
- Open the page: step through one lesson, one diagram (Space), finish the quiz.
- Ask mode: one question on a card; a suggestion shows Replace/Add buttons.
- Quiz mode: first question is a "why" question.
- Reset `extra-cards.json` to `[]` after test saves.

## Common mistakes
| Mistake | Fix |
|---|---|
| Cards define terms ("X is ...") | Lead with the limit that forces X |
| Quiz asks for numbers ("hit@5 was...") | Ask why the number came out that way |
| Right answer always in one slot | Template shuffles; keep it |
| Serving the whole repo for images | Only dirs in `ASSETS`; never repo root (.env) |
| Giving Claude write tools to edit cards | Claude proposes; the learner clicks; server writes |
| Old server still running after edits | Prompts load at start: restart it |
