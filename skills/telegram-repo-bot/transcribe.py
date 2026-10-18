"""Run by the whisper venv's Python: transcribe.py MODEL AUDIO PAUSE_MIN. Prints the text with [pause Ns] marks."""
import sys
from faster_whisper import WhisperModel

model, path, pause_min = sys.argv[1], sys.argv[2], float(sys.argv[3])
segments, _ = WhisperModel(model, compute_type="int8").transcribe(path, word_timestamps=True)
out, last = [], 0.0
for w in (w for s in segments for w in s.words):
    if w.start - last >= pause_min:
        out.append(f" [pause {w.start - last:.1f}s]")
    out.append(w.word)
    last = w.end
print("".join(out).strip())
