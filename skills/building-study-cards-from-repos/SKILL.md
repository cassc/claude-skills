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
3. Add repo-relative image dirs to `ASSETS` in `server.py`, if any (the
   folder's own `diagrams/` is already there).
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
**Read `source-repos.md` (next to this file) first.** It covers: one lesson
per module, clickable code references, an architecture lesson, a module map
slide, a request trace, and PlantUML/Structurizr images.

## Quick reference
| File | Role |
|---|---|
| `cards.js` | `LESSONS` - cards + qa per lesson; optional `job`/`entry`/`uses` build the module map slide |
| `quiz.js` | `QUIZ` - multiple choice per lesson id |
| `diagrams.js` | `DIAGRAMS` - ordered steps, image optional |
| `ask_prompt.md` / `quiz_prompt.md` | Claude's rules per chat mode |
| `extra-cards.json` | cards the learner approved from chat; commit it |
| `markdown.js` | renders chat replies: code blocks, inline code, bold, lists, tables |
| `source.js` | makes `<code>path:line</code>` clickable; popup shows the file |
| `server.py` | static files, `/api/chat` (`claude -p --resume`, tools Read/Grep/Glob), `/api/cards`, `/api/source` (read-only repo files for the popup) |

## Verify
- `node -e` eval the three data files; every `a < o.length`.
- Open the page: step through one lesson, one diagram (Space), finish the quiz.
- Code references: each one names a real file and lines that exist. Click
  one: the popup opens at the marked lines.
- Module map (if any): a jump button opens that lesson; an entry opens the
  popup.
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
| Code changed, references point at the wrong lines | Re-check the line numbers when the code moves |
