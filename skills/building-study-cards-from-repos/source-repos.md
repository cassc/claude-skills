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
line. Files under dot dirs, git-ignored files, and files over 1 MB do not open.

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
- `img` and `art` are optional. With neither, the step list is the whole
  slide.

## Diagram images
Use a drawing only when it helps. Try in this order and stop at the first
that works:
1. **Reuse** what the repo has: images, `.puml` files, a Structurizr
   `workspace.dsl`.
2. **Local tool**: check which is installed (`command -v`) and use the first
   one found. Write the source into `<web folder>/diagrams/` and render it
   next to itself. Prefer SVG; PNG only if the tool cannot make SVG.
   - PlantUML: `plantuml -tsvg learn/diagrams/*.puml`
   - Graphviz: `dot -Tsvg learn/diagrams/architecture.dot -o learn/diagrams/architecture.svg`
   - Mermaid CLI: `mmdc -i learn/diagrams/architecture.mmd -o learn/diagrams/architecture.svg`
     (labels missing in the page: render to `.png`)
   - D2: `d2 learn/diagrams/architecture.d2 learn/diagrams/architecture.svg`
   - Structurizr CLI, with a `workspace.dsl`: export to PlantUML
     (`structurizr-cli export -workspace workspace.dsl -format plantuml -output learn/diagrams`),
     then render with PlantUML.

   Make a box diagram for the architecture lesson, and a sequence diagram
   for the request trace if the tool has one.
3. **SVG you write yourself**, when no tool is installed. Save it in
   `<web folder>/diagrams/`.
   - Boxes, arrows, and short labels only. Put the boxes on a simple grid.
   - Each label fits inside its box.
   - No scripts, no links, no outside fonts or images.
   - Dark lines and text on a light background (the page shows images on
     white).
   - Open the slide and look at it. Fix overlaps.
4. **ASCII drawing**, when you cannot view the SVG to check it, or it still
   looks wrong after two fixes. Put it in the `art` field of the diagram
   entry: plain characters only, at most about 60 columns and 20 lines. The
   page shows `art` only when there is no `img`.
5. **Nothing**, when a drawing would not help. Say nothing; the map slide
   and step lists still work.

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
