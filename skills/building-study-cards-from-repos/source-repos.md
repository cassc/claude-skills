# Source code repos

No lessons or results to copy: find the topics yourself. Teach the parts
(one lesson per module) and the whole (architecture lesson, module map,
request trace).

Skip any part below that does not fit the repo. Do not tell the user what
you skipped.

## Lessons
- **Lesson** = one module or subsystem (auth, storage, request flow).
- **First principle** = the problem the design must handle (concurrency,
  latency, failure, scale).
- **Evidence** = code, a test, a benchmark, or a commit that shows why.
- **`{{SOURCES}}`**: core source dirs, README, ADRs/design docs. Not the whole
  repo on big codebases (chat gets slow).
- Every "why" cites code or a commit. If the reason is a guess, the card
  says so.

## Code references
Every concept card, likely-question answer, and quiz `e` cites 1-2 places as
`<code>src/auth/token.py:42-60</code>` (path from the repo root, then a line or
a range). The page makes these clickable: a popup shows the file at those
lines. Prefer a range that shows the whole idea (a function, a check) over one
line. Files under dot dirs or over 300 KB do not open.

## Architecture lesson
The first lesson, id `00`. Skip it for a repo with one module.
- `fp` card: what the system must do, and the root limit that shapes it.
- Where state lives (memory, disk, database, another service) and which
  module owns it.
- The 2-3 biggest design choices: what was picked, what it costs, and the
  code that shows it.
- Likely questions: "walk me through the architecture", "why is it split
  this way?".

## Module map
Give each module lesson (not `00`) three fields in `cards.js`:
- `job`: one line, what the module is for.
- `entry`: where to start reading, as `"path/file.ext:line"`.
- `uses`: ids of the lessons it depends on. Read this from the code (imports,
  calls). Do not guess.

The page then adds a "Module map" slide after the first card of the first
lesson: one row per module, a clickable entry, and a button that jumps to the
lesson. With no `job` fields there is no slide.

## Request trace
Follow one real request (or job, or event) from the entry point to the
response. Skip it for a repo with no request or data flow, like a pure
library.
- One `DIAGRAMS` entry under `"00"`, 5-9 steps in order.
- `s` = what happens. `n` = why it happens here, plus
  `<code>path/file.ext:12-30</code>`.
- `img` is optional. With no image the step list is the whole slide.

## Diagram images
Use an image only when it helps. Try in this order:
1. **Reuse** what the repo has: images, `.puml` files, a Structurizr
   `workspace.dsl`.
2. **PlantUML**, if `plantuml` is installed. Write the source into
   `<web folder>/diagrams/` and render it next to itself:
   `plantuml -tsvg learn/diagrams/*.puml`. Make a component diagram for the
   architecture lesson and a sequence diagram for the request trace.
3. **Structurizr**, only if the repo has a `workspace.dsl` or
   `structurizr-cli` is installed: export to PlantUML
   (`structurizr-cli export -workspace workspace.dsl -format plantuml -output learn/diagrams`),
   then render as in step 2.
4. **No tool**: no image. Say nothing; the map slide and step lists still
   work.

Rules:
- Never install a tool, pull a Docker image, or send code to a public render
  server without asking.
- Keep a diagram small: under about 10 boxes, named like the lesson titles.
- Set `img` to the repo-relative path, e.g. `"learn/diagrams/architecture.svg"`.
  The server already allows the web folder's own `diagrams/` dir.
- A diagram slide still needs steps: list the boxes in the order a request
  meets them.

## Quiz
- Per module: "what breaks if we remove X?", "why here and not in Y?".
- Structure (in lesson `00`): "where would you add X?", "which modules must
  change if Y changes?", "what breaks if module Z is gone?".
