// Cards per lesson. fp = first-principle card (one per lesson, first). Concept: t, b (HTML). Likely question: q, a.
// Optional on a card or a likely question, shown under its text: img: "learn/diagrams/x.svg" (repo-relative) or art: "a plain text drawing".
// Card shape: root problem -> idea that follows -> evidence from the repo.
// Source repos, optional per lesson (builds the module map slide): job: "one line", entry: "path/file.ext:12", uses: ["02"].
const LESSONS = [
  {
    id: "01", title: "Example lesson",
    cards: [
      { fp: true, t: "Why X exists", b: "The root limit is ... It can't ...<br><b>So:</b> X. Every other part follows from this." },
      { t: "Why step Y?", b: "<b>Problem:</b> ...<br><b>So:</b> ...<br><b>Evidence:</b> numbers or output from the repo." },
    ],
    qa: [
      { q: "What problem does X solve, from first principles?", a: "Start from the root limit, then why X follows, then one trade-off." },
    ],
  },
];
