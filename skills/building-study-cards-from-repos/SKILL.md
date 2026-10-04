---
name: building-study-cards-from-repos
description: Use when the user wants to learn or review the concepts in a repo (course, lab, tutorial, docs, codebase) through slide-like study cards, flashcards, interview-prep questions, a quiz, or a page where Claude answers questions and quizzes them live.
---

# Building study cards from a repo

## Overview
A local web page that teaches a repo's concepts: slide cards, likely
questions, diagram walk-throughs, a multiple-choice quiz, and a side chat
where Claude Code (running in the repo, read-only) answers questions about
the current card, suggests better cards, draws a graph when asked, and
quizzes with graded free-text answers.

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
   For a phone on the same Wi-Fi: `HOST=0.0.0.0 python3 learn/server.py`
   and open the printed link. It holds a token; `TOKEN=...` keeps it the
   same between runs. Add `TLS=1` for HTTPS: the server makes a
   self-signed cert with `openssl`, and the browser warns once. Or pass
   your own with `CERT=cert.pem KEY=key.pem` (`mkcert` makes one the phone
   can trust). Without HTTPS, others on the Wi-Fi can read the traffic.

## Content recipe
Read the repo's own teaching material first (README, lesson folders,
cheat sheets, review questions, eval results). One lesson = one topic.

Per lesson, in this order. Write as many cards, questions, and quiz items
as the lesson needs:
- **First-principle card** (`fp: true`), at least one, first in the
  lesson: the root limit and "So: ...".
- **Concept cards**: title is a "Why ...?" or a claim. Body:
  `Problem: ... So: ... Evidence: <real number/output from the repo>`.
  One idea per card. Include the honest results (where the fancy method
  lost).
- **Likely questions** (`qa`): interview style. Answer starts from the
  root cause, then the idea, then one trade-off.
- **Quiz items**: each asks "why" or "what breaks if". Distractors are
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
| `cards.js` | `LESSONS` - cards + qa per lesson; a card may hold a code block (`<pre><code class="language-py">`) and a graph (`img` or `art`); optional `job`/`entry`/`uses` build the module map slide |
| `quiz.js` | `QUIZ` - multiple choice per lesson id |
| `diagrams.js` | `DIAGRAMS` - ordered steps; image or text drawing optional |
| `ask_prompt.md` / `quiz_prompt.md` | Claude's rules per chat mode |
| `extra-cards.json` | cards the learner approved from chat; commit it |
| `diagrams/` | graphs made in chat (made on first use); commit the ones a saved card uses |
| `history.js` | History button: the newest 200 chats, kept in the browser; "Export all" downloads them (ask and quiz) as one Markdown file; resumes a waiting chat after a page reload |
| `markdown.js` | renders chat replies: code blocks, inline code, bold, lists, tables |
| `highlight.js` | code colors in cards and the source popup, by highlight.js from a CDN; with no internet, code is plain text |
| `source.js` | makes `<code>path:line</code>` clickable; popup shows the file and a folding file tree (Files button), and can open in a new tab |
| `server.py` | static files, `/api/chat` (`claude -p --resume`, tools Read/Grep/Glob; keeps each result by message id), `/api/cards`, `/api/diagram` (draws a graph Claude wrote in chat: a local tool, or Claude's own SVG after a safety check), `/api/files` and `/api/source` (read-only: repo files git does not ignore, for the popup) |

## Verify
- `node -e` eval the three data files; every `a < o.length`.
- Open the page: step through one lesson, one diagram (Space), finish the quiz.
- Code references: each one names a real file and lines that exist. Click
  one: the popup opens at the marked lines.
- Files button: the popup shows the repo's files as a tree; a click opens
  or closes a folder, or opens a file; the filter shows a flat list of
  matches.
- Module map (if any): a jump button opens that lesson; an entry opens the
  popup.
- Ask mode: one question on a card; a suggestion shows Replace/Add buttons.
- Ask mode: "draw a diagram of this": the graph shows in the chat. "Add to
  this card" puts it under the card's text.
- Code colors: a file in the popup and a `<pre><code>` block in a card show
  colors; the popup's line numbers and marked lines still work.
- Quiz mode: first question is a "why" question.
- Drag the chat panel's left edge: the panel gets wider, the cards narrower.
- Reload while Claude is thinking: the chat comes back and the reply arrives.
- New chat while another chat waits: both replies arrive, each in its own chat.
- History: reload the page, open History, open the chat: the reply is there.
- History, "Export all": a `.md` file downloads with every saved chat,
  newest first.
- Reset `extra-cards.json` to `[]` and delete test graphs in `diagrams/`
  after test saves.

## Common mistakes
| Mistake | Fix |
|---|---|
| Cards define terms ("X is ...") | Lead with the limit that forces X |
| Quiz asks for numbers ("hit@5 was...") | Ask why the number came out that way |
| Right answer always in one slot | Template shuffles; keep it |
| Serving the whole repo for images | Only dirs in `ASSETS`; never repo root (.env) |
| Giving Claude write tools to edit cards | Claude proposes; the learner clicks; server writes |
| Giving Claude Bash or Write so it can draw | Claude writes the diagram source in its reply; the server draws it |
| Old server still running after edits | Prompts load at start: restart it |
| Code changed, references point at the wrong lines | Re-check the line numbers when the code moves |
