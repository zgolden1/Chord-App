#!/usr/bin/env python3
"""Optional background worker for contributed audio. Run on any computer that has analyze.py's requirements.
It polls the API, downloads a queued file, runs analyze.py, uploads the result and the API deletes the audio.
Env: CATALOG_URL, WORKER_TOKEN.   Stop with Ctrl-C."""
import json, os, subprocess, sys, tempfile, time

import requests

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.join(HERE, ".."))
from server.convert import from_analysis_file          # noqa: E402

ANALYZE = os.environ.get("ANALYZE_PY", os.path.join(HERE, "analyze.py"))


def once(base, H, model="htdemucs"):
    c = requests.post(base + "/api/worker/claim", headers=H, timeout=30).json()
    if not c.get("job"):
        return False
    jid = c["job"]["id"]
    try:
        with tempfile.TemporaryDirectory() as td:
            src = os.path.join(td, "in.audio")
            with requests.get("%s/api/worker/jobs/%d/audio" % (base, jid), headers=H, stream=True, timeout=120) as r:
                r.raise_for_status()
                with open(src, "wb") as f:
                    for ch in r.iter_content(1 << 20):
                        f.write(ch)
            out = os.path.join(td, "out.json")
            subprocess.run([sys.executable, ANALYZE, src, "--model", model, "--out", out], check=True, timeout=3600)
            data = from_analysis_file(json.load(open(out)), model)
        requests.post("%s/api/worker/jobs/%d/result" % (base, jid), json={"data": data}, headers=H, timeout=60).raise_for_status()
    except Exception as e:
        requests.post("%s/api/worker/jobs/%d/result" % (base, jid), json={"error": str(e)}, headers=H, timeout=60)
    return True


if __name__ == "__main__":
    base = os.environ.get("CATALOG_URL", "http://localhost:8000").rstrip("/")
    H = {"Authorization": "Bearer " + os.environ["WORKER_TOKEN"]}
    while True:
        if not once(base, H):
            time.sleep(15)
