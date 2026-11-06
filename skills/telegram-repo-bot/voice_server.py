"""Local voice server, run by the tg-voice venv: voice_server.py PORT IDLE_SECONDS.
Qwen3-ASR (speech to text) and VoxCPM2 (text to audio) on the GPU. voice.py starts it on demand;
it exits after IDLE_SECONDS without work, so the GPU can sleep again.
POST /asr?pause=0.7&context=... (audio bytes) -> {"text"}. POST /tts (UTF-8 text) -> audio/ogg."""
import json
import os
import re
import subprocess
import sys
import tempfile
import threading
import time
import urllib.parse
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer

os.environ.setdefault("PYTORCH_CUDA_ALLOC_CONF", "expandable_segments:True")
os.environ.setdefault("TQDM_DISABLE", "1")
import numpy as np
import soundfile as sf
import torch

PORT, IDLE = int(sys.argv[1]), float(sys.argv[2])
ASR = os.environ.get("TG_VOICE_ASR", "Qwen/Qwen3-ASR-0.6B")
TTS = os.environ.get("TG_VOICE_TTS", "openbmb/VoxCPM2")
STEPS = int(os.environ.get("TG_VOICE_STEPS", "10"))
gpu = threading.Lock()  # one job at a time on the GPU
models = {}
last = time.time()


def model(kind):
    if kind not in models:
        if kind == "asr":  # the aligner (pause marks) runs on the CPU: both GPU models only just fit in 8 GB
            from qwen_asr import Qwen3ASRModel
            models[kind] = Qwen3ASRModel.from_pretrained(ASR, dtype=torch.bfloat16, device_map="cuda:0",
                                                         forced_aligner="Qwen/Qwen3-ForcedAligner-0.6B",
                                                         forced_aligner_kwargs={"device_map": "cpu"})
        else:
            from voxcpm import VoxCPM
            models[kind] = VoxCPM.from_pretrained(TTS, load_denoiser=False, optimize=False, device="cuda")
    return models[kind]


def asr(path, pause, context):
    r = model("asr").transcribe(path, context=context, return_time_stamps=pause > 0)[0]
    text = r.text
    if not r.time_stamps:
        return text
    out, i, end = [], 0, 0.0
    for w in r.time_stamps.items:  # words in order; put [pause Ns] before a word after a long silence
        j = text.find(w.text, i)
        if j < 0:
            continue
        out.append(text[i:j])
        if w.start_time - end >= pause:
            out.append(f" [pause {w.start_time - end:.1f}s] ")
        out.append(w.text)
        i, end = j + len(w.text), w.end_time
    return re.sub(r" {2,}", " ", "".join(out) + text[i:]).strip()


def tts(text):
    """Chunks of whole sentences up to ~200 chars, joined with short silences."""
    m = model("tts")
    sr = m.tts_model.sample_rate
    chunks, cur = [], ""
    for s in re.findall(r".+?(?:[。！？!?；;]|[.](?=\s)|$)", text.replace("\n", " ")):
        if cur and len(cur) + len(s) > 200:
            chunks.append(cur)
            cur = ""
        cur += s
    wavs = [w for c in chunks + [cur] if c.strip() for w in (m.generate(text=c.strip(), normalize=True, inference_timesteps=STEPS),
                                                            np.zeros(int(sr * 0.25), dtype=np.float32))]
    with tempfile.NamedTemporaryFile(suffix=".wav") as f:
        sf.write(f.name, np.concatenate(wavs), sr)
        return subprocess.run(["ffmpeg", "-loglevel", "error", "-i", f.name, "-c:a", "libopus", "-b:a", "32k", "-f", "ogg", "-"],
                              capture_output=True, check=True).stdout


class Handler(BaseHTTPRequestHandler):
    def do_POST(self):
        global last
        url = urllib.parse.urlparse(self.path)
        q = dict(urllib.parse.parse_qsl(url.query))
        body = self.rfile.read(int(self.headers["Content-Length"]))
        try:
            with gpu:
                last = time.time()
                if url.path == "/asr":
                    with tempfile.NamedTemporaryFile(suffix=".audio") as f:
                        f.write(body)
                        f.flush()
                        out, ctype = json.dumps({"text": asr(f.name, float(q.get("pause", 0)), q.get("context", ""))}).encode(), "application/json"
                else:
                    out, ctype = tts(body.decode()), "audio/ogg"
                torch.cuda.empty_cache()
                last = time.time()
            code = 200
        except Exception as e:
            out, code, ctype = json.dumps({"error": f"{type(e).__name__}: {e}"[-500:]}).encode(), 500, "application/json"
        self.send_response(code)
        self.send_header("Content-Type", ctype)
        self.send_header("Content-Length", str(len(out)))
        self.end_headers()
        self.wfile.write(out)

    def log_message(self, fmt, *args):
        print(time.strftime("%F %T"), fmt % args, flush=True)


def idle_exit():
    while True:
        time.sleep(10)
        if not gpu.locked() and time.time() - last > IDLE:
            os._exit(0)  # frees the GPU so it can sleep


threading.Thread(target=idle_exit, daemon=True).start()
ThreadingHTTPServer(("127.0.0.1", PORT), Handler).serve_forever()
