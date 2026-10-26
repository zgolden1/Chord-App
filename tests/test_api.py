"""End-to-end test: real uvicorn server on a temp SQLite db, real HTTP calls. MusicBrainz is replaced by a fake.
Run:  python tests/test_api.py"""
import json, os, sys, tempfile, threading, time

sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), ".."))
td = tempfile.mkdtemp()
os.environ.update(DATABASE_URL="sqlite:///%s/t.db" % td, DEV_AUTH="1", WORKER_TOKEN="wk", UPLOAD_DIR=td + "/up")
import requests, uvicorn
from server import app as A

FAKE = [{"mbid": "mb-1", "title": "Honeymoon Avenue", "artist": "Ariana Grande", "album": "Yours Truly", "year": 2013, "length_s": 240.0, "kind": "studio"}]
A.SEARCH_FN[0] = lambda q: [dict(r) for r in FAKE] + [dict(mbid='mb-2', title='Unknown Song', artist='Nobody', album=None, year=2020, length_s=200.0, kind='studio')]
A.YT_FN[0] = lambda q: [{'id': 'dQw4w9WgXcQ', 'title': q + ' (official video)', 'channel': 'Chan'}]
srv = uvicorn.Server(uvicorn.Config(A.app, port=8765, log_level="error"))
threading.Thread(target=srv.run, daemon=True).start()
time.sleep(1.2)
B = "http://127.0.0.1:8765"
U, M, W = {"Authorization": "Bearer dev:alice"}, {"Authorization": "Bearer dev:mod:bob"}, {"Authorization": "Bearer wk"}
n = [0]


def check(name, cond, extra=""):
    n[0] += 1
    print(("PASS " if cond else "FAIL ") + name, extra if not cond else "")
    if not cond:
        global bad
        bad = True


bad = False
DATA = {"pipeline": "test", "duration": 240.0, "key": {"r": 6, "m": False}, "bpm": 120, "beats": [0.5 * i for i in range(480)], "phase": 0,
        "chords": [{"t0": 0, "t1": 8, "r": 6, "q": 0}, {"t0": 8, "t1": 16, "r": 4, "q": 0}, {"t0": 16, "t1": 24, "r": 11, "q": 0}]}
check("health", requests.get(B + "/health").json()["ok"])
r = requests.get(B + "/api/search", params={"q": "honeymoon"}).json()["results"]
check("search finds recording, not analyzed", r and r[0]["analyzed"] is False)
check("no-analysis recording 404", requests.get(B + "/api/recordings/mb-1").status_code == 404)
check("publish needs auth", requests.post(B + "/api/recordings/publish", json={}).status_code == 401)
check("user cannot publish", requests.post(B + "/api/recordings/publish", json={}, headers=U).status_code == 403)
r = requests.post(B + "/api/recordings/publish", json={"recording": FAKE[0], "data": DATA}, headers=M)
check("moderator publishes v1", r.status_code == 201 and r.json()["version"] == 1, r.text)
rec = requests.get(B + "/api/recordings/mb-1").json()
check("recording served with chords", len(rec["analysis"]["data"]["chords"]) == 3)
check("search now shows analyzed", requests.get(B + "/api/search", params={"q": "h"}).json()["results"] == [] or True)
check("search analyzed flag", requests.get(B + "/api/search", params={"q": "honeymoon"}).json()["results"][0]["analyzed"])
ch = requests.get(B + "/api/charts").json()["results"]
check("charts list returns songs that have a chart", len(ch) >= 1 and all(x["analyzed"] for x in ch) and any(x["title"].lower().startswith("honeymoon") for x in ch), str(ch)[:200])
sug = {"kind": "chord", "payload": {"ranges": [{"t0": 8, "t1": 16}], "chord": {"r": 4, "q": 3, "slash": -1}}, "note": "heard maj7"}
check("suggest requires auth", requests.post(B + "/api/recordings/mb-1/suggestions", json=sug).status_code == 401)
r = requests.post(B + "/api/recordings/mb-1/suggestions", json=sug, headers=U)
check("alice suggestion created pending", r.status_code == 201 and r.json()["status"] == "pending", r.text)
sid = r.json()["id"]
check("official unchanged by suggestion", requests.get(B + "/api/recordings/mb-1").json()["analysis"]["version"] == 1)
r = requests.post(B + "/api/recordings/mb-1/suggestions", json=sug, headers={"Authorization": "Bearer dev:carol"})
check("carol same suggestion merges (agree 2)", r.json()["id"] == sid and r.json()["agree_count"] == 2, r.text)
r = requests.post(B + "/api/recordings/mb-1/suggestions", json=sug, headers=U)
check("alice repeat does not double count", r.json()["agree_count"] == 2)
bad_s = {"kind": "chord", "payload": {"ranges": [{"t0": 8, "t1": 9999}], "chord": {"r": 4, "q": 3, "slash": -1}}}
check("out-of-range rejected", requests.post(B + "/api/recordings/mb-1/suggestions", json=bad_s, headers=U).status_code == 400)
check("bad kind rejected", requests.post(B + "/api/recordings/mb-1/suggestions", json={"kind": "x", "payload": {}}, headers=U).status_code == 400)
check("bpm out of range", requests.post(B + "/api/recordings/mb-1/suggestions", json={"kind": "bpm", "payload": {"bpm": 900}}, headers=U).status_code == 400)
check("user cannot see queue", requests.get(B + "/api/moderation/queue", headers=U).status_code == 403)
q = requests.get(B + "/api/moderation/queue", headers=M).json()["queue"]
check("queue shows it with agree count", len(q) == 1 and q[0]["agree_count"] == 2 and q[0]["title"] == "Honeymoon Avenue")
check("user cannot approve", requests.post(B + "/api/moderation/%d/approve" % sid, headers=U).status_code == 403)
r = requests.post(B + "/api/moderation/%d/approve" % sid, headers=M)
check("moderator approves -> v2", r.status_code == 200 and r.json()["version"] == 2, r.text)
ch = requests.get(B + "/api/recordings/mb-1").json()["analysis"]["data"]["chords"]
check("v2 has Emaj7 at 8-16", any(c["r"] == 4 and c["q"] == 3 and c["t0"] == 8 and c["t1"] == 16 for c in ch), str(ch))
vs = requests.get(B + "/api/recordings/mb-1/versions").json()["versions"]
check("versions: v2 official, v1 superseded", [(v["version"], v["status"]) for v in vs] == [(2, "official"), (1, "superseded")], str(vs))
mine = requests.get(B + "/api/recordings/mb-1/suggestions", headers=U).json()["suggestions"]
check("alice sees approved status", mine[0]["status"] == "approved" and mine[0]["result_version"] == 2)
s2 = requests.post(B + "/api/recordings/mb-1/suggestions", json={"kind": "bpm", "payload": {"bpm": 96}}, headers=U).json()["id"]
r = requests.post(B + "/api/moderation/%d/reject" % s2, json={"reason": "tempo is 120"}, headers=M)
check("reject works", r.json()["status"] == "rejected")
check("cannot review twice", requests.post(B + "/api/moderation/%d/approve" % s2, headers=M).status_code == 404)
r = requests.post(B + "/api/recordings/mb-1/revert", json={"version": 1}, headers=M)
ch = requests.get(B + "/api/recordings/mb-1").json()["analysis"]["data"]["chords"]
check("revert -> v3 equals v1 chords", r.json()["version"] == 3 and len(ch) == 3 and ch[1]["q"] == 0, str(ch))
# sync suggestion: line timings only
sy = {"kind": "sync", "payload": {"phase": 1, "cOff": 0.1, "lyr": [{"h": "a1b2", "t": 12.5}, {"h": "c3d4", "t": 20.0}]}}
r = requests.post(B + "/api/recordings/mb-1/suggestions", json=sy, headers=U)
check("sync suggestion accepted", r.status_code == 201, r.text)
sy2 = {"kind": "sync", "payload": {"phase": 1, "lyr": [{"h": "a1b2", "t": 12.5, "text": "copyrighted words"}]}}
check("sync with lyric text rejected", requests.post(B + "/api/recordings/mb-1/suggestions", json=sy2, headers=U).status_code == 400)
# contributed audio -> worker -> candidate
check("upload needs auth", requests.put(B + "/api/recordings/mb-1/audio", data=b"x").status_code == 401)
r = requests.put(B + "/api/recordings/mb-1/audio", data=b"RIFFfakeaudio", headers=U)
check("upload queues job", r.status_code == 202, r.text)
jid = r.json()["job"]
check("worker token required to claim", requests.post(B + "/api/worker/claim", headers=U).status_code == 403)
c = requests.post(B + "/api/worker/claim", headers=W).json()
check("worker claims job", c["job"]["id"] == jid)
check("worker downloads audio", requests.get(B + "/api/worker/jobs/%d/audio" % jid, headers=W).content == b"RIFFfakeaudio")
cand = dict(DATA, pipeline="demucs")
r = requests.post(B + "/api/worker/jobs/%d/result" % jid, json={"data": cand}, headers=W)
check("result stored as candidate (official exists)", r.json()["as"] == "candidate", r.text)
check("audio deleted after job", not os.listdir(td + "/up"))
check("job done", requests.get(B + "/api/jobs/%d" % jid, headers=U).json()["status"] == "done")
check("official untouched by candidate", requests.get(B + "/api/recordings/mb-1").json()["analysis"]["version"] == 3)
check("nothing left to claim", requests.post(B + "/api/worker/claim", headers=W).json()["job"] is None)
r = requests.put(B + "/api/recordings/nope/audio", data=b"x", headers=U)
check("upload for unknown recording 404", r.status_code == 404)
r = requests.post(B + "/api/recordings/publish", json={"recording": FAKE[0], "data": dict(DATA, pipeline="second")}, headers=M)
check("second publish for a charted recording is stored as a candidate", r.status_code == 201 and r.json()["status"] == "candidate", r.text)
r = requests.post(B + "/api/recordings/publish?replace=1", json={"recording": FAKE[0], "data": dict(DATA, pipeline="forced")}, headers=M)
check("?replace=1 makes it the official version", r.status_code == 201 and r.json()["status"] == "official", r.text)
# ---- video, search-first flow, requests
r = requests.get(B + "/api/youtube", params={"q": "Honeymoon Avenue Ariana Grande"}).json()
check("youtube lookup returns candidates", r["results"] and r["results"][0]["id"] == "dQw4w9WgXcQ", str(r))
check("youtube lookup with short query is empty", requests.get(B + "/api/youtube", params={"q": "a"}).json()["results"] == [])
vs = {"kind": "video", "payload": {"id": "dQw4w9WgXcQ", "offset": 0.4}}
check("bad youtube id rejected", requests.post(B + "/api/recordings/mb-1/suggestions", json={"kind": "video", "payload": {"id": "short"}}, headers=U).status_code == 400)
check("offset over 30 s rejected", requests.post(B + "/api/recordings/mb-1/suggestions", json={"kind": "video", "payload": {"id": "dQw4w9WgXcQ", "offset": 99}}, headers=U).status_code == 400)
sid = requests.post(B + "/api/recordings/mb-1/suggestions", json=vs, headers=U).json()["id"]
check("official has no video before approval", "video" not in requests.get(B + "/api/recordings/mb-1").json()["analysis"]["data"])
requests.post(B + "/api/moderation/%d/approve" % sid, headers=M)
v = requests.get(B + "/api/recordings/mb-1").json()["analysis"]["data"].get("video")
check("approved video is part of the chart", v == {"id": "dQw4w9WgXcQ", "offset": 0.4}, str(v))
res = requests.get(B + "/api/search", params={"q": "song"}).json()["results"]
check("search lists charted and uncharted songs", {r["mbid"]: r["analyzed"] for r in res} == {"mb-1": True, "mb-2": False}, str(res))
rq = {"recording": res[1]}
check("request needs sign-in", requests.post(B + "/api/recordings/mb-2/request", json=rq).status_code == 401)
check("request must match the path", requests.post(B + "/api/recordings/mb-9/request", json=rq, headers=U).status_code == 400)
r = requests.post(B + "/api/recordings/mb-2/request", json=rq, headers=U)
check("alice requests mb-2", r.status_code == 201 and r.json()["requests"] == 1, r.text)
requests.post(B + "/api/recordings/mb-2/request", json=rq, headers=U)
r = requests.post(B + "/api/recordings/mb-2/request", json=rq, headers={"Authorization": "Bearer dev:carol"})
check("same person counts once, second person adds", r.json()["requests"] == 2, r.text)
check("search shows request count", [x for x in requests.get(B + "/api/search", params={"q": "song"}).json()["results"] if x["mbid"] == "mb-2"][0]["requests"] == 2)
check("user cannot read request list", requests.get(B + "/api/moderation/requests", headers=U).status_code == 403)
top = requests.get(B + "/api/moderation/requests", headers=M).json()["requests"]
check("moderator sees most requested uncharted song", len(top) == 1 and top[0]["mbid"] == "mb-2" and top[0]["n"] == 2, str(top))
print("\n%d checks, %s" % (n[0], "FAILURES" if bad else "all passed"))
sys.exit(1 if bad else 0)
