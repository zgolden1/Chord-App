"""Who is calling? Three kinds of caller:
  user        a signed-in person (Supabase Auth JWT, HS256)
  moderator   a user whose JWT carries app_metadata.role == "moderator"
  worker      the GPU worker, authenticated with WORKER_TOKEN
Set DEV_AUTH=1 for local development: 'Bearer dev:alice' is a user, 'Bearer dev:mod:bob' a moderator."""
import base64, hashlib, hmac, json, os, time


def _b64(s):
    return base64.urlsafe_b64decode(s + "=" * (-len(s) % 4))


def verify_jwt(token, secret):
    try:
        h, p, s = token.split(".")
        if json.loads(_b64(h)).get("alg") != "HS256":
            return None
        good = hmac.new(secret.encode(), (h + "." + p).encode(), hashlib.sha256).digest()
        if not hmac.compare_digest(good, _b64(s)):
            return None
        claims = json.loads(_b64(p))
        if claims.get("exp") and claims["exp"] < time.time():
            return None
        return claims
    except Exception:
        return None


def identify(request):
    """Returns dict(id, role) or None."""
    h = request.headers.get("authorization", "")
    if not h.lower().startswith("bearer "):
        return None
    tok = h[7:].strip()
    wt = os.environ.get("WORKER_TOKEN")
    if wt and hmac.compare_digest(tok, wt):
        return {"id": "worker", "role": "worker"}
    if os.environ.get("DEV_AUTH") == "1" and tok.startswith("dev:"):
        parts = tok.split(":")
        if len(parts) == 3 and parts[1] == "mod":
            return {"id": parts[2], "role": "moderator"}
        return {"id": parts[1], "role": "user"}
    secret = os.environ.get("SUPABASE_JWT_SECRET")
    if secret:
        c = verify_jwt(tok, secret)
        if c and c.get("sub"):
            role = (c.get("app_metadata") or {}).get("role")
            return {"id": c["sub"], "role": "moderator" if role == "moderator" else "user"}
    return None
