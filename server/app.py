"""ChordFlow catalog API (Starlette).  Run:  uvicorn server.app:app --port 8000
Public:     GET  /api/search?q=...                       find recordings (MusicBrainz + catalog status)
            GET  /api/recordings/{mbid}                  recording + official transcription
            GET  /api/recordings/{mbid}/versions         version history
Signed in:  POST /api/recordings/{mbid}/suggestions      send a correction (never applied directly)
            GET  /api/recordings/{mbid}/suggestions      your own suggestions for this recording
            PUT  /api/recordings/{mbid}/audio            contribute a file for background analysis (optional)
            GET  /api/jobs/{id}
Moderator:  GET  /api/moderation/queue
            POST /api/moderation/{id}/approve | reject
            POST /api/recordings/{mbid}/revert           body {"version": n}
            POST /api/recordings/{mbid}/publish          body = transcription JSON (from publish.py)
Worker:     POST /api/worker/claim, GET /api/worker/jobs/{id}/audio, POST /api/worker/jobs/{id}/result"""
import json, os, tempfile, time, uuid
from datetime import datetime, timezone

from starlette.applications import Starlette
from starlette.middleware import Middleware
from starlette.middleware.cors import CORSMiddleware
from starlette.responses import FileResponse, JSONResponse
from starlette.routing import Route

from . import logic, search
from .auth import identify
from .db import DB

db = None
UPLOAD_DIR = os.environ.get("UPLOAD_DIR", os.path.join(tempfile.gettempdir(), "chordflow_uploads"))
MAX_UPLOAD = int(float(os.environ.get("MAX_UPLOAD_MB", "60")) * 1024 * 1024)
AUTO_APPROVE_MIN_AGREE = int(os.environ.get("AUTO_APPROVE_MIN_AGREE", "0"))     # 0 = moderators only
SEARCH_FN = [search.musicbrainz]                                                 # replaced in tests
YT_FN = [search.youtube]                                                         # replaced in tests


def now():
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


def get_db():
    global db
    if db is None:
        db = DB()
    return db


def err(msg, code=400):
    return JSONResponse({"error": msg}, status_code=code)


def need(request, *roles):
    who = identify(request)
    if not who or (roles and who["role"] not in roles):
        return None, err("not allowed", 401 if not who else 403)
    return who, None


def official(mbid):
    row = get_db().one("SELECT * FROM analyses WHERE mbid=? AND status='official'", (mbid,))
    if row:
        row["data"] = json.loads(row["data"])
    return row


def new_version(mbid, data, source, by):
    """Writes `data` as the new official version; the previous official becomes 'superseded'."""
    d = get_db()
    with d.tx():
        cur = d.one("SELECT MAX(version) AS v FROM analyses WHERE mbid=?", (mbid,))
        v = (cur["v"] or 0) + 1
        d.run("UPDATE analyses SET status='superseded' WHERE mbid=? AND status='official'", (mbid,))
        d.run("INSERT INTO analyses (mbid,version,status,source,data,created_at,created_by) VALUES (?,?,?,?,?,?,?)",
              (mbid, v, "official", source, json.dumps(data), now(), by))
    return v


def ensure_recording(rec):
    d = get_db()
    if not d.one("SELECT mbid FROM recordings WHERE mbid=?", (rec["mbid"],)):
        d.run("INSERT INTO recordings (mbid,title,artist,album,year,length_s,kind,created_at) VALUES (?,?,?,?,?,?,?,?)",
              (rec["mbid"], rec.get("title", ""), rec.get("artist", ""), rec.get("album"), rec.get("year"), rec.get("length_s"), rec.get("kind"), now()))


# ---------------------------------------------------------------- public
async def health(request):
    return JSONResponse({"ok": True})


async def api_search(request):
    q = request.query_params.get("q", "").strip()
    if len(q) < 2:
        return JSONResponse({"results": []})
    try:
        res = SEARCH_FN[0](q)
    except Exception as e:
        res = []
        local = get_db().all("SELECT * FROM recordings WHERE title LIKE ? OR artist LIKE ? LIMIT 10", ("%" + q + "%", "%" + q + "%"))
        for r in local:
            res.append({k: r[k] for k in ("mbid", "title", "artist", "album", "year", "length_s", "kind")})
    d = get_db()
    have = {r["mbid"]: r for r in d.all("SELECT mbid, version FROM analyses WHERE status='official'")}
    reqs = {r["mbid"]: r["n"] for r in d.all("SELECT mbid, COUNT(*) AS n FROM song_requests GROUP BY mbid")}
    for r in res:
        r["requests"] = reqs.get(r["mbid"], 0)
        r["analyzed"] = r["mbid"] in have
        r["version"] = have[r["mbid"]]["version"] if r["mbid"] in have else None
    res.sort(key=lambda r: (not r["analyzed"],))
    return JSONResponse({"results": res})


async def api_recording(request):
    mbid = request.path_params["mbid"]
    rec = get_db().one("SELECT * FROM recordings WHERE mbid=?", (mbid,))
    if not rec:
        return err("unknown recording", 404)
    a = official(mbid)
    return JSONResponse({"recording": rec, "analysis": ({"version": a["version"], "source": a["source"], "created_at": a["created_at"], "data": a["data"]} if a else None)})


async def api_versions(request):
    rows = get_db().all("SELECT version,status,source,created_at,created_by FROM analyses WHERE mbid=? ORDER BY version DESC", (request.path_params["mbid"],))
    return JSONResponse({"versions": rows})


# ---------------------------------------------------------------- suggestions
async def api_suggest(request):
    who, e = need(request, "user", "moderator")
    if e:
        return e
    mbid = request.path_params["mbid"]
    if request.method == "GET":
        rows = get_db().all("SELECT id,kind,payload,note,status,reason,created_at,result_version FROM suggestions WHERE mbid=? AND by_user=? ORDER BY id DESC", (mbid, who["id"]))
        for r in rows:
            r["payload"] = json.loads(r["payload"])
        return JSONResponse({"suggestions": rows})
    a = official(mbid)
    if not a:
        return err("this recording has no transcription yet", 404)
    try:
        body = await request.json()
    except Exception:
        return err("body must be JSON")
    kind, p = body.get("kind"), body.get("payload")
    bad = logic.validate(kind, p, float(a["data"].get("duration") or 0) or 1e9)
    if bad:
        return err(bad)
    d = get_db()
    # rate limit: 60 suggestions per user per day
    n = d.one("SELECT COUNT(*) AS n FROM suggestions WHERE by_user=? AND created_at>?", (who["id"], datetime.fromtimestamp(time.time() - 86400, timezone.utc).isoformat()))["n"]
    if n >= 60:
        return err("daily limit reached", 429)
    canon = logic.canonical(kind, p)
    dup = None
    for r in d.all("SELECT id,payload FROM suggestions WHERE mbid=? AND kind=? AND status='pending'", (mbid, kind)):
        if logic.canonical(kind, json.loads(r["payload"])) == canon:
            dup = r["id"]; break
    note = (body.get("note") or "")[:200]
    if dup:
        if not d.one("SELECT 1 AS x FROM suggestion_votes WHERE suggestion_id=? AND user_id=?", (dup, who["id"])):
            d.run("INSERT INTO suggestion_votes (suggestion_id,user_id) VALUES (?,?)", (dup, who["id"]))
            d.run("UPDATE suggestions SET agree_count=agree_count+1 WHERE id=?", (dup,))
        sid = dup
    else:
        sid = d.run("INSERT INTO suggestions (mbid,base_version,kind,payload,note,by_user,status,created_at) VALUES (?,?,?,?,?,?,?,?)",
                    (mbid, a["version"], kind, json.dumps(p), note, who["id"], "pending", now()))
        d.run("INSERT INTO suggestion_votes (suggestion_id,user_id) VALUES (?,?)", (sid, who["id"]))
    row = d.one("SELECT agree_count FROM suggestions WHERE id=?", (sid,))
    if AUTO_APPROVE_MIN_AGREE and row["agree_count"] >= AUTO_APPROVE_MIN_AGREE:
        cands = [json.loads(x["data"]) for x in d.all("SELECT data FROM analyses WHERE mbid=? AND status='candidate'", (mbid,))]
        if logic.evidence(kind, p, a["data"], cands).get("independent_analyses_agree", 0) >= 1:
            _approve(sid, "auto")
    return JSONResponse({"id": sid, "status": d.one("SELECT status FROM suggestions WHERE id=?", (sid,))["status"], "agree_count": row["agree_count"]}, status_code=201)


# ---------------------------------------------------------------- moderation
def _approve(sid, reviewer):
    d = get_db()
    s = d.one("SELECT * FROM suggestions WHERE id=?", (sid,))
    a = official(s["mbid"])
    data = logic.apply_suggestion(s["kind"], json.loads(s["payload"]), a["data"])
    v = new_version(s["mbid"], data, "suggestion:%d" % sid, reviewer)
    d.run("UPDATE suggestions SET status='approved', reviewed_by=?, reviewed_at=?, result_version=? WHERE id=?", (reviewer, now(), v, sid))
    return v


async def api_queue(request):
    who, e = need(request, "moderator")
    if e:
        return e
    d = get_db()
    rows = d.all("""SELECT s.*, r.title, r.artist FROM suggestions s JOIN recordings r ON r.mbid=s.mbid
                    WHERE s.status='pending' ORDER BY s.agree_count DESC, s.id""")
    for s in rows:
        s["payload"] = json.loads(s["payload"])
        a = official(s["mbid"])
        cands = [json.loads(x["data"]) for x in d.all("SELECT data FROM analyses WHERE mbid=? AND status='candidate'", (s["mbid"],))]
        s["stale"] = bool(a and a["version"] != s["base_version"])
        s["evidence"] = logic.evidence(s["kind"], s["payload"], a["data"], cands) if a else {}
    return JSONResponse({"queue": rows})


async def api_review(request):
    who, e = need(request, "moderator")
    if e:
        return e
    sid, action = int(request.path_params["id"]), request.path_params["action"]
    d = get_db()
    s = d.one("SELECT * FROM suggestions WHERE id=?", (sid,))
    if not s or s["status"] != "pending":
        return err("not pending", 404)
    if action == "approve":
        return JSONResponse({"status": "approved", "version": _approve(sid, who["id"])})
    body = {}
    try:
        body = await request.json()
    except Exception:
        pass
    d.run("UPDATE suggestions SET status='rejected', reviewed_by=?, reviewed_at=?, reason=? WHERE id=?", (who["id"], now(), (body.get("reason") or "")[:200], sid))
    return JSONResponse({"status": "rejected"})


async def api_revert(request):
    who, e = need(request, "moderator")
    if e:
        return e
    mbid = request.path_params["mbid"]
    body = await request.json()
    old = get_db().one("SELECT data FROM analyses WHERE mbid=? AND version=?", (mbid, body.get("version")))
    if not old:
        return err("no such version", 404)
    v = new_version(mbid, json.loads(old["data"]), "revert:%s" % body["version"], who["id"])
    return JSONResponse({"version": v})


async def api_publish(request):
    """A moderator (or the publish.py script run with a moderator token) puts a transcription into the catalog."""
    who, e = need(request, "moderator", "worker")
    if e:
        return e
    body = await request.json()
    rec, data = body.get("recording"), body.get("data")
    if not rec or not rec.get("mbid") or not isinstance(data, dict) or not data.get("chords"):
        return err("need recording and data.chords")
    ensure_recording(rec)
    mbid = rec["mbid"]
    if request.query_params.get("as") == "candidate":
        d = get_db()
        v = (d.one("SELECT MAX(version) AS v FROM analyses WHERE mbid=?", (mbid,))["v"] or 0) + 1
        d.run("INSERT INTO analyses (mbid,version,status,source,data,created_at,created_by) VALUES (?,?,?,?,?,?,?)", (mbid, v, "candidate", "pipeline:" + data.get("pipeline", "?"), json.dumps(data), now(), who["id"]))
        return JSONResponse({"version": v, "status": "candidate"}, status_code=201)
    v = new_version(mbid, data, "pipeline:" + data.get("pipeline", "?"), who["id"])
    return JSONResponse({"version": v, "status": "official"}, status_code=201)


# ---------------------------------------------------------------- contribute audio -> job
async def api_audio_put(request):
    who, e = need(request, "user", "moderator")
    if e:
        return e
    mbid = request.path_params["mbid"]
    if not get_db().one("SELECT mbid FROM recordings WHERE mbid=?", (mbid,)):
        return err("unknown recording; publish or search for it first", 404)
    os.makedirs(UPLOAD_DIR, exist_ok=True)
    path, size = os.path.join(UPLOAD_DIR, uuid.uuid4().hex + ".bin"), 0
    with open(path, "wb") as f:
        async for chunk in request.stream():
            size += len(chunk)
            if size > MAX_UPLOAD:
                f.close(); os.remove(path)
                return err("file too large", 413)
            f.write(chunk)
    jid = get_db().run("INSERT INTO jobs (mbid,status,pipeline,upload_path,by_user,created_at) VALUES (?,?,?,?,?,?)", (mbid, "queued", "demucs+basicpitch", path, who["id"], now()))
    return JSONResponse({"job": jid, "status": "queued"}, status_code=202)


async def api_job(request):
    who, e = need(request, "user", "moderator", "worker")
    if e:
        return e
    j = get_db().one("SELECT id,mbid,status,error,created_at,finished_at FROM jobs WHERE id=?", (int(request.path_params["id"]),))
    return JSONResponse(j) if j else err("no such job", 404)


async def worker_claim(request):
    who, e = need(request, "worker")
    if e:
        return e
    d = get_db()
    with d.tx():
        j = d.one("SELECT id,mbid,pipeline FROM jobs WHERE status='queued' ORDER BY id LIMIT 1")
        if not j:
            return JSONResponse({"job": None})
        d.run("UPDATE jobs SET status='running', started_at=? WHERE id=?", (now(), j["id"]))
    rec = d.one("SELECT * FROM recordings WHERE mbid=?", (j["mbid"],))
    return JSONResponse({"job": j, "recording": rec})


async def worker_audio(request):
    who, e = need(request, "worker")
    if e:
        return e
    j = get_db().one("SELECT upload_path FROM jobs WHERE id=?", (int(request.path_params["id"]),))
    if not j or not j["upload_path"] or not os.path.exists(j["upload_path"]):
        return err("no audio", 404)
    return FileResponse(j["upload_path"])


async def worker_result(request):
    who, e = need(request, "worker")
    if e:
        return e
    jid = int(request.path_params["id"])
    d = get_db()
    j = d.one("SELECT * FROM jobs WHERE id=?", (jid,))
    if not j:
        return err("no such job", 404)
    body = await request.json()
    if j["upload_path"] and os.path.exists(j["upload_path"]):
        os.remove(j["upload_path"])                              # audio is never kept
    if body.get("error"):
        d.run("UPDATE jobs SET status='failed', error=?, upload_path=NULL, finished_at=? WHERE id=?", (str(body["error"])[:300], now(), jid))
        return JSONResponse({"status": "failed"})
    data = body["data"]
    status = "candidate"
    if not official(j["mbid"]):
        new_version(j["mbid"], data, "pipeline:" + data.get("pipeline", "?"), "worker"); status = "official"
    else:
        v = (d.one("SELECT MAX(version) AS v FROM analyses WHERE mbid=?", (j["mbid"],))["v"] or 0) + 1
        d.run("INSERT INTO analyses (mbid,version,status,source,data,created_at,created_by) VALUES (?,?,?,?,?,?,?)", (j["mbid"], v, "candidate", "pipeline:" + data.get("pipeline", "?"), json.dumps(data), now(), "worker"))
    d.run("UPDATE jobs SET status='done', upload_path=NULL, finished_at=? WHERE id=?", (now(), jid))
    return JSONResponse({"status": "done", "as": status})


# ---------------------------------------------------------------- YouTube lookup and song requests
async def api_youtube(request):
    q = request.query_params.get("q", "").strip()
    if len(q) < 3:
        return JSONResponse({"results": []})
    try:
        return JSONResponse({"results": YT_FN[0](q)})
    except search.NoKey:
        return JSONResponse({"results": [], "error": "no_key"})
    except Exception as e:
        return JSONResponse({"results": [], "error": "unavailable"})


async def api_request_song(request):
    """Someone wants this song charted. Needs sign-in. The recording is saved from what the search showed."""
    who, e = need(request, "user", "moderator")
    if e:
        return e
    try:
        body = await request.json()
    except Exception:
        return err("body must be JSON")
    rec = body.get("recording") or {}
    mbid = request.path_params["mbid"]
    if rec.get("mbid") != mbid or not str(rec.get("title", ""))[:200] or len(mbid) > 64:
        return err("send the recording from the search result")
    d = get_db()
    ensure_recording({"mbid": mbid, "title": str(rec["title"])[:200], "artist": str(rec.get("artist", ""))[:200], "album": (rec.get("album") or None) and str(rec["album"])[:200],
                      "year": rec.get("year") if isinstance(rec.get("year"), int) else None, "length_s": rec.get("length_s") if isinstance(rec.get("length_s"), (int, float)) else None,
                      "kind": str(rec.get("kind") or "")[:30] or None})
    if not d.one("SELECT 1 AS x FROM song_requests WHERE mbid=? AND user_id=?", (mbid, who["id"])):
        n = d.one("SELECT COUNT(*) AS n FROM song_requests WHERE user_id=? AND created_at>?", (who["id"], datetime.fromtimestamp(time.time() - 86400, timezone.utc).isoformat()))["n"]
        if n >= 20:
            return err("daily limit reached", 429)
        d.run("INSERT INTO song_requests (mbid,user_id,created_at) VALUES (?,?,?)", (mbid, who["id"], now()))
    return JSONResponse({"requests": d.one("SELECT COUNT(*) AS n FROM song_requests WHERE mbid=?", (mbid,))["n"]}, status_code=201)


async def api_top_requests(request):
    who, e = need(request, "moderator")
    if e:
        return e
    rows = get_db().all("""SELECT r.mbid, r.title, r.artist, r.year, r.length_s, COUNT(*) AS n FROM song_requests q JOIN recordings r ON r.mbid=q.mbid
                           WHERE NOT EXISTS (SELECT 1 FROM analyses a WHERE a.mbid=q.mbid AND a.status='official')
                           GROUP BY r.mbid, r.title, r.artist, r.year, r.length_s ORDER BY n DESC, r.title LIMIT 100""")
    return JSONResponse({"requests": rows})


def make_app():
    routes = [
        Route("/health", health),
        Route("/api/search", api_search),
        Route("/api/youtube", api_youtube),
        Route("/api/recordings/{mbid}/request", api_request_song, methods=["POST"]),
        Route("/api/moderation/requests", api_top_requests),
        Route("/api/recordings/{mbid}", api_recording),
        Route("/api/recordings/{mbid}/versions", api_versions),
        Route("/api/recordings/{mbid}/suggestions", api_suggest, methods=["GET", "POST"]),
        Route("/api/recordings/{mbid}/audio", api_audio_put, methods=["PUT"]),
        Route("/api/recordings/{mbid}/revert", api_revert, methods=["POST"]),
        Route("/api/recordings/publish", api_publish, methods=["POST"]),
        Route("/api/jobs/{id:int}", api_job),
        Route("/api/moderation/queue", api_queue),
        Route("/api/moderation/{id:int}/{action}", api_review, methods=["POST"]),
        Route("/api/worker/claim", worker_claim, methods=["POST"]),
        Route("/api/worker/jobs/{id:int}/audio", worker_audio),
        Route("/api/worker/jobs/{id:int}/result", worker_result, methods=["POST"]),
    ]
    origins = [o for o in os.environ.get("CORS_ORIGINS", "*").split(",") if o]
    return Starlette(routes=routes, middleware=[Middleware(CORSMiddleware, allow_origins=origins, allow_methods=["*"], allow_headers=["*"])])


app = make_app()
