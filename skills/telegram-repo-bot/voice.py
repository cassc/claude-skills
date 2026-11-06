"""Speech to text and text to audio for the bots. Stdlib only; any Python 3 runs it.
  voice.py asr AUDIO [--pause 0.7] [--context WORDS] [--whisper small]   prints the text
  voice.py tts OUT.ogg [--limit 600] < TEXT                              writes a voice note (OUT - = stdout)
It talks to voice_server.py (local GPU models) and starts it when it is not running.
If the server fails, asr falls back to faster-whisper on the CPU (transcribe.py)."""
import argparse
import json
import os
import re
import subprocess
import sys
import time
import urllib.error
import urllib.parse
import urllib.request
from pathlib import Path

HERE = Path(__file__).parent
PY = Path(os.environ.get("TG_VOICE_PY", "~/.local/share/tg-voice/venv/bin/python")).expanduser()
WHISPER = Path(os.environ.get("TG_CLAUDE_WHISPER", "~/.local/share/tg-claude-bot/venv/bin/python")).expanduser()
PORT = int(os.environ.get("TG_VOICE_PORT", "8771"))
IDLE = os.environ.get("TG_VOICE_IDLE", "600")  # seconds the server (and the GPU) stays up after the last job
LOG = Path("~/.local/state/tg-voice.log").expanduser()


def call(path, data):
    """POST to the server; start it on the first refused connection and wait up to 60 s for it."""
    for i in range(60):
        try:
            req = urllib.request.Request(f"http://127.0.0.1:{PORT}{path}", data=data)
            with urllib.request.urlopen(req, timeout=900) as r:
                return r.read()
        except urllib.error.HTTPError as e:
            raise RuntimeError(json.load(e).get("error", e.code)) from None
        except urllib.error.URLError:
            if i == 0:
                if not PY.exists():
                    raise RuntimeError(f"voice server is not set up: no {PY} (see SKILL.md)")
                LOG.parent.mkdir(parents=True, exist_ok=True)
                subprocess.Popen([str(PY), "-I", str(HERE / "voice_server.py"), str(PORT), IDLE], start_new_session=True,
                                 stdin=subprocess.DEVNULL, stdout=LOG.open("a"), stderr=subprocess.STDOUT)
            time.sleep(1)
    raise RuntimeError(f"voice server did not start (see {LOG})")


def asr(a):
    try:
        q = urllib.parse.urlencode({"pause": a.pause, "context": a.context})
        return json.loads(call(f"/asr?{q}", Path(a.audio).read_bytes()))["text"]
    except RuntimeError as e:
        if not WHISPER.exists():
            raise
        r = subprocess.run([str(WHISPER), "-I", str(HERE / "transcribe.py"), a.whisper, a.audio, str(a.pause or 999)],
                           capture_output=True, text=True, timeout=900)
        if r.returncode:
            raise RuntimeError(f"{e}; CPU fallback failed too: {r.stderr.strip()[-300:]}") from None
        print(f"GPU voice failed: {e}", file=sys.stderr)
        return f"(CPU whisper) {r.stdout.strip()}"


def speakable(text, limit):
    """Markdown reply -> plain text worth hearing, cut at a sentence end near limit."""
    zh = re.search(r"[一-鿿]", text)
    text = re.sub(r"```.*?(```|$)", " (代码略) " if zh else " (code skipped) ", text, flags=re.S)
    text = re.sub(r"\[([^\]]*)\]\([^)]*\)", r"\1", text)
    text = re.sub(r"https?://\S+", "", text)
    text = re.sub(r"[`*_#>|~]", "", text)
    text = re.sub(r"\s+", " ", text).strip()
    if len(text) > limit:
        cut = max(text.rfind(p, 0, limit) for p in "。！？.!?")
        text = text[:cut + 1 if cut > limit // 2 else limit] + (" 其余见文字。" if zh else " The rest is in the text.")
    return text


def main():
    p = argparse.ArgumentParser()
    sub = p.add_subparsers(dest="cmd", required=True)
    a = sub.add_parser("asr")
    a.add_argument("audio")
    a.add_argument("--pause", type=float, default=0)
    a.add_argument("--context", default="")
    a.add_argument("--whisper", default="small")
    t = sub.add_parser("tts")
    t.add_argument("out")
    t.add_argument("--limit", type=int, default=600)
    args = p.parse_args()
    try:
        if args.cmd == "asr":
            print(asr(args))
        elif text := speakable(sys.stdin.read(), args.limit):
            ogg = call("/tts", text.encode())
            sys.stdout.buffer.write(ogg) if args.out == "-" else Path(args.out).write_bytes(ogg)
    except RuntimeError as e:
        sys.exit(str(e))


main()
