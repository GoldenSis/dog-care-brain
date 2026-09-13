#!/usr/bin/env python3
"""Dog-Care-Brain API — stdlib ThreadingHTTPServer + sqlite3, zero deps.

Same shape as BrainShared/web/rally-atlas/api/server.py: one process, one SQLite
file, magic-link auth. Slice 1 mailer writes `.dev-outbox/` (no SMTP, no keys).

Run:  python3 api/server.py
Env:  DC_HOST, DC_PORT, DC_DB, DC_ROOT, DC_OUTBOX, DC_BLOBS, DC_INSECURE_COOKIE=1
"""
from __future__ import annotations

import hashlib, json, os, re, secrets, sqlite3, threading, time
from email.utils import formatdate
from http import cookies as httpcookies
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from urllib.parse import parse_qs, unquote, urlparse

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT_DEFAULT = os.path.dirname(HERE)
COOKIE = "dc_s"
MAGIC_TTL = 15 * 60
SESSION_TTL = 90 * 24 * 3600
MAX_BODY = 2 * 1024 * 1024
EMAIL_RE = re.compile(r"^[^@\s]+@[^@\s]+\.[^@\s]+$")
SLUG_RE = re.compile(r"^[a-z0-9][a-z0-9-]{0,80}$")
BLOB_RE = re.compile(r"^[a-f0-9]{32}\.(webm|ogg|m4a|wav|mp3)$")
MIME = {
    ".html": "text/html; charset=utf-8",
    ".js": "text/javascript; charset=utf-8",
    ".css": "text/css; charset=utf-8",
    ".json": "application/json",
    ".svg": "image/svg+xml",
    ".png": "image/png",
    ".jpg": "image/jpeg",
    ".jpeg": "image/jpeg",
    ".webp": "image/webp",
    ".webm": "audio/webm",
    ".md": "text/plain; charset=utf-8",
}

_lock = threading.Lock()

SEED_OBS = {
    "billie": [
        {"id": 1, "time": "08:25", "date": "Today", "title": "Breakfast & morning check-in",
         "text": "Finished her full breakfast and drank well. Bright, relaxed and ready for the day.",
         "tags": ["Nutrition", "Mood · bright"]},
        {"id": 2, "time": "10:10", "date": "Today", "title": "Woodland walk",
         "text": "A calm 42-minute sniff walk. Good recall around two dogs and no stiffness noticed.",
         "tags": ["Exercise · 42 min", "Behaviour · calm"]},
        {"id": 3, "time": "18:40", "date": "Yesterday", "title": "Evening medication",
         "text": "Joint supplement given with dinner. Coat and paws checked after rain.",
         "tags": ["Medication", "Health check"]},
    ],
    "charlie": [
        {"id": 4, "time": "09:15", "date": "Today", "title": "Settled into day care",
         "text": "A little vocal at drop-off, then settled on the green bed after five minutes.",
         "tags": ["Behaviour", "Mood · settled"]},
        {"id": 5, "time": "11:30", "date": "Today", "title": "Play session",
         "text": "Gentle play with Billie in the garden. Responded well to breaks and name cues.",
         "tags": ["Social", "Training"]},
    ],
}
SEED_DOGS = (
    ("billie", "Billie Blue"),
    ("charlie", "Charlie Rose"),
)


def cfg(name, default):
    return os.environ.get(name, default)


def db_path():
    return cfg("DC_DB", os.path.join(HERE, "dogcare.db"))


def outbox_dir():
    return cfg("DC_OUTBOX", os.path.join(os.path.dirname(HERE), ".dev-outbox"))


def blobs_dir():
    return cfg("DC_BLOBS", os.path.join(HERE, "blobs"))


def static_root():
    return os.path.realpath(cfg("DC_ROOT", ROOT_DEFAULT))


def _h(s):
    return hashlib.sha256(s.encode()).hexdigest()


def db():
    c = sqlite3.connect(db_path(), check_same_thread=False)
    c.row_factory = sqlite3.Row
    c.execute("PRAGMA foreign_keys=ON")
    c.execute("PRAGMA journal_mode=WAL")
    return c


def init():
    with open(os.path.join(HERE, "schema.sql"), encoding="utf-8") as f:
        schema = f.read()
    c = db()
    c.executescript(schema)
    cols = [r[1] for r in c.execute("PRAGMA table_info(business)")]
    if "imported" not in cols:
        c.execute("ALTER TABLE business ADD COLUMN imported INTEGER NOT NULL DEFAULT 0")
    c.commit()
    c.close()
    os.makedirs(outbox_dir(), exist_ok=True)
    os.makedirs(blobs_dir(), exist_ok=True)


def write_outbox(email, link):
    os.makedirs(outbox_dir(), exist_ok=True)
    safe = re.sub(r"[^a-z0-9._+-]+", "_", email.lower())
    name = f"{int(time.time())}-{safe}-{secrets.token_hex(4)}.json"
    path = os.path.join(outbox_dir(), name)
    payload = {
        "to": email,
        "subject": "Sign in to Muse",
        "link": link,
        "date": formatdate(localtime=True),
    }
    with open(path, "w", encoding="utf-8") as f:
        json.dump(payload, f, indent=2)
        f.write("\n")
    return path


def cookie_header(sid, clear=False):
    bits = [f"{COOKIE}={'' if clear else sid}", "Path=/", "HttpOnly", "SameSite=Lax",
            f"Max-Age={0 if clear else SESSION_TTL}"]
    if os.environ.get("DC_INSECURE_COOKIE") != "1":
        bits.append("Secure")
    return "; ".join(bits)


def user_of(handler):
    raw = handler.headers.get("Cookie")
    if not raw:
        return None
    try:
        sid = httpcookies.SimpleCookie(raw).get(COOKIE)
    except httpcookies.CookieError:
        return None
    if not sid or not sid.value:
        return None
    c = db()
    row = c.execute(
        "SELECT u.id, u.email, u.role, u.business_id FROM session s "
        "JOIN user u ON u.id=s.user_id WHERE s.sh=? AND s.expires > ?",
        (_h(sid.value), int(time.time())),
    ).fetchone()
    c.close()
    if not row:
        return None
    return {"id": row["id"], "email": row["email"], "role": row["role"],
            "business_id": row["business_id"]}


def ensure_account(email):
    """First verify creates the tenant + demo dogs so the pilot's UI still has Billie & Charlie."""
    now = int(time.time())
    c = db()
    row = c.execute("SELECT id, business_id FROM user WHERE email=?", (email,)).fetchone()
    if row:
        c.execute("UPDATE user SET last_seen=? WHERE id=?", (now, row["id"]))
        c.commit()
        uid, bid = row["id"], row["business_id"]
        c.close()
        return uid, bid
    slug = re.sub(r"[^a-z0-9]+", "-", email.split("@")[0].lower()).strip("-") or "biz"
    slug = f"{slug}-{secrets.token_hex(3)}"
    name = email.split("@")[0]
    c.execute("INSERT INTO business(name, slug, created) VALUES(?,?,?)", (name, slug, now))
    bid = c.execute("SELECT last_insert_rowid()").fetchone()[0]
    c.execute(
        "INSERT INTO user(email, role, business_id, created, last_seen) VALUES(?,?,?,?,?)",
        (email, "owner", bid, now, now),
    )
    uid = c.execute("SELECT last_insert_rowid()").fetchone()[0]
    c.execute("INSERT INTO pref(user_id, language) VALUES(?, 'en')", (uid,))
    seed_business(c, bid, uid)
    c.commit()
    c.close()
    return uid, bid


def seed_business(c, bid, uid):
    now = int(time.time())
    n = c.execute("SELECT COUNT(*) FROM dog WHERE business_id=?", (bid,)).fetchone()[0]
    if n:
        return
    ids = {}
    for slug, name in SEED_DOGS:
        c.execute(
            "INSERT INTO dog(business_id, slug, name, created) VALUES(?,?,?,?)",
            (bid, slug, name, now),
        )
        ids[slug] = c.execute("SELECT last_insert_rowid()").fetchone()[0]
    replace_observations(c, bid, uid, SEED_OBS, ids)


def replace_observations(c, bid, uid, observations, dog_ids=None):
    now = int(time.time())
    if dog_ids is None:
        dog_ids = {r["slug"]: r["id"] for r in
                   c.execute("SELECT id, slug FROM dog WHERE business_id=?", (bid,))}
    for slug in observations or {}:
        if slug not in dog_ids:
            if not SLUG_RE.match(slug):
                continue
            c.execute(
                "INSERT INTO dog(business_id, slug, name, created) VALUES(?,?,?,?)",
                (bid, slug, slug.replace("-", " ").title(), now),
            )
            dog_ids[slug] = c.execute("SELECT last_insert_rowid()").fetchone()[0]
    c.execute("DELETE FROM observation WHERE business_id=?", (bid,))
    for slug, items in (observations or {}).items():
        did = dog_ids.get(slug)
        if not did:
            continue
        for item in items or []:
            audio = item.get("audio")
            ref = None
            audio_json = None
            if isinstance(audio, dict):
                audio_json = json.dumps(audio)
                url = audio.get("url") or ""
                if "/blobs/" in url:
                    ref = url.rsplit("/", 1)[-1]
            c.execute(
                "INSERT INTO observation(business_id, dog_id, author_id, client_id, text, title, "
                "tags, time, date, voice_blob_ref, audio_json, created_at) "
                "VALUES(?,?,?,?,?,?,?,?,?,?,?,?)",
                (bid, did, uid, item.get("id"), item.get("text") or "",
                 item.get("title"), json.dumps(item.get("tags") or []),
                 item.get("time"), item.get("date"), ref, audio_json, now),
            )


def observations_map(c, bid):
    dogs = list(c.execute(
        "SELECT id, slug FROM dog WHERE business_id=? ORDER BY id", (bid,)))
    out = {d["slug"]: [] for d in dogs}
    rows = c.execute(
        "SELECT o.*, d.slug FROM observation o JOIN dog d ON d.id=o.dog_id "
        "WHERE o.business_id=? ORDER BY o.id ASC", (bid,),
    )
    for r in rows:
        item = {
            "id": r["client_id"] if r["client_id"] is not None else r["id"],
            "time": r["time"] or "",
            "date": r["date"] or "",
            "title": r["title"] or "",
            "text": r["text"] or "",
            "tags": json.loads(r["tags"] or "[]"),
        }
        if r["audio_json"]:
            try:
                item["audio"] = json.loads(r["audio_json"])
            except json.JSONDecodeError:
                pass
        out.setdefault(r["slug"], []).append(item)
    return out


def invites_list(c, bid):
    rows = c.execute(
        "SELECT * FROM invite WHERE business_id=? ORDER BY id DESC", (bid,))
    out = []
    for r in rows:
        out.append({
            "id": r["id"],
            "token": r["token"],
            "email": r["email"],
            "name": r["name"] or "",
            "role": r["role"] or "owner",
            "permissions": json.loads(r["areas"] or "[]"),
            "status": r["status"],
            "created": "Today",
        })
    return out


def replace_invites(c, bid, invites):
    now = int(time.time())
    c.execute("DELETE FROM invite WHERE business_id=?", (bid,))
    for item in invites or []:
        tok = item.get("token") or secrets.token_urlsafe(16)
        c.execute(
            "INSERT INTO invite(business_id, token, email, name, role, areas, status, created) "
            "VALUES(?,?,?,?,?,?,?,?)",
            (bid, tok, item.get("email") or "", item.get("name") or "",
             item.get("role") or "owner",
             json.dumps(item.get("permissions") or item.get("areas") or []),
             item.get("status") or "pending", now),
        )


def do_auth_request(payload, host):
    email = str(payload.get("email") or "").strip().lower()[:255]
    if not EMAIL_RE.match(email):
        return {"ok": False, "error": "invalid email"}, 400
    tok = secrets.token_urlsafe(32)
    now = int(time.time())
    with _lock:
        c = db()
        c.execute("INSERT INTO magic(th, email, created, expires) VALUES(?,?,?,?)",
                  (_h(tok), email, now, now + MAGIC_TTL))
        c.commit()
        c.close()
    proto = "http" if os.environ.get("DC_INSECURE_COOKIE") == "1" else "https"
    link = f"{proto}://{host}/api/auth/verify?t={tok}"
    write_outbox(email, link)
    return {"ok": True, "mailed": False}, 200


def do_auth_verify(query):
    tok = (query.get("t") or [""])[0]
    now = int(time.time())
    if not tok or len(tok) > 128:
        return None, "bad"
    with _lock:
        c = db()
        row = c.execute("SELECT email, expires, used FROM magic WHERE th=?", (_h(tok),)).fetchone()
        if not row or row["used"] or row["expires"] < now:
            c.close()
            return None, "expired"
        email = row["email"]
        c.execute("UPDATE magic SET used=1 WHERE th=?", (_h(tok),))
        c.commit()
        c.close()
    uid, _bid = ensure_account(email)
    sid = secrets.token_urlsafe(32)
    with _lock:
        c = db()
        c.execute("INSERT INTO session(sh, user_id, created, expires) VALUES(?,?,?,?)",
                  (_h(sid), uid, now, now + SESSION_TTL))
        c.execute("DELETE FROM magic WHERE expires < ?", (now - 86400,))
        c.execute("DELETE FROM session WHERE expires < ?", (now,))
        c.commit()
        c.close()
    return sid, None


def state_of(user):
    c = db()
    lang = "en"
    row = c.execute("SELECT language FROM pref WHERE user_id=?", (user["id"],)).fetchone()
    if row:
        lang = row["language"]
    dogs = [{"id": r["id"], "slug": r["slug"], "name": r["name"]}
            for r in c.execute("SELECT id, slug, name FROM dog WHERE business_id=? ORDER BY id",
                               (user["business_id"],))]
    obs = observations_map(c, user["business_id"])
    inv = invites_list(c, user["business_id"])
    c.close()
    return {"ok": True, "email": user["email"], "role": user["role"],
            "language": lang, "dogs": dogs, "observations": obs, "invites": inv}


class Handler(BaseHTTPRequestHandler):
    def log_message(self, *a):
        pass

    def _send(self, obj, code=200, extra=None):
        body = json.dumps(obj).encode()
        self.send_response(code)
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(body)))
        self.send_header("Cache-Control", "no-store")
        for k, v in (extra or []):
            self.send_header(k, v)
        self.end_headers()
        self.wfile.write(body)

    def _need_user(self):
        u = user_of(self)
        if not u:
            self._send({"ok": False, "error": "not signed in"}, 401)
        return u

    def _read_json(self):
        n = int(self.headers.get("Content-Length") or 0)
        if n > MAX_BODY:
            self._send({"ok": False, "error": "too big"}, 413)
            return None
        try:
            payload = json.loads(self.rfile.read(n) or b"{}")
        except (ValueError, TypeError):
            self._send({"ok": False, "error": "bad json"}, 400)
            return None
        if not isinstance(payload, dict):
            self._send({"ok": False, "error": "bad json"}, 400)
            return None
        return payload

    def do_GET(self):
        parsed = urlparse(self.path)
        path = parsed.path
        query = parse_qs(parsed.query)
        if path == "/api/health":
            return self._send({"ok": True, "ts": int(time.time())})
        if path == "/api/auth/verify":
            sid, err = do_auth_verify(query)
            dest = "/?signin=ok" if sid else f"/?signin={err or 'bad'}"
            self.send_response(302)
            self.send_header("Location", dest)
            self.send_header("Cache-Control", "no-store")
            if sid:
                self.send_header("Set-Cookie", cookie_header(sid))
            self.send_header("Content-Length", "0")
            self.end_headers()
            return
        if path == "/api/auth/me":
            u = user_of(self)
            if not u:
                return self._send({"ok": False}, 200)
            return self._send({"ok": True, "email": u["email"], "role": u["role"]})
        if path == "/api/state":
            u = self._need_user()
            if not u:
                return
            return self._send(state_of(u))
        if path == "/api/dogs":
            u = self._need_user()
            if not u:
                return
            return self._send({"ok": True, "dogs": state_of(u)["dogs"]})
        if path.startswith("/api/dogs/"):
            u = self._need_user()
            if not u:
                return
            try:
                did = int(path.rsplit("/", 1)[-1])
            except ValueError:
                return self._send({"ok": False, "error": "not found"}, 404)
            c = db()
            row = c.execute(
                "SELECT id, slug, name FROM dog WHERE id=? AND business_id=?",
                (did, u["business_id"]),
            ).fetchone()
            c.close()
            if not row:
                return self._send({"ok": False, "error": "not found"}, 404)
            return self._send({"ok": True, "dog": {"id": row["id"], "slug": row["slug"],
                                                   "name": row["name"]}})
        if path == "/api/observations":
            u = self._need_user()
            if not u:
                return
            return self._send({"ok": True, "observations": state_of(u)["observations"]})
        if path == "/api/invites":
            u = self._need_user()
            if not u:
                return
            return self._send({"ok": True, "invites": state_of(u)["invites"]})
        if path.startswith("/api/blobs/"):
            u = self._need_user()
            if not u:
                return
            name = path[len("/api/blobs/"):]
            if not BLOB_RE.match(name):
                return self._send({"ok": False, "error": "not found"}, 404)
            full = os.path.realpath(os.path.join(blobs_dir(), str(u["business_id"]), name))
            root = os.path.realpath(os.path.join(blobs_dir(), str(u["business_id"])))
            if not full.startswith(root + os.sep) or not os.path.isfile(full):
                return self._send({"ok": False, "error": "not found"}, 404)
            with open(full, "rb") as f:
                blob = f.read()
            ext = name.rsplit(".", 1)[-1]
            mime = {"webm": "audio/webm", "ogg": "audio/ogg", "m4a": "audio/mp4",
                    "wav": "audio/wav", "mp3": "audio/mpeg"}.get(ext, "application/octet-stream")
            self.send_response(200)
            self.send_header("Content-Type", mime)
            self.send_header("Content-Length", str(len(blob)))
            self.send_header("Cache-Control", "private, max-age=86400")
            self.end_headers()
            self.wfile.write(blob)
            return
        if path.startswith("/api/"):
            return self._send({"ok": False, "error": "not found"}, 404)
        return self._serve_static(path)

    def do_POST(self):
        path = urlparse(self.path).path
        if path == "/api/auth/logout":
            raw = self.headers.get("Cookie")
            if raw:
                try:
                    sid = httpcookies.SimpleCookie(raw).get(COOKIE)
                    if sid and sid.value:
                        with _lock:
                            c = db()
                            c.execute("DELETE FROM session WHERE sh=?", (_h(sid.value),))
                            c.commit()
                            c.close()
                except httpcookies.CookieError:
                    pass
            return self._send({"ok": True}, 200, [("Set-Cookie", cookie_header("", clear=True))])
        payload = self._read_json()
        if payload is None:
            return
        if path == "/api/auth/request":
            host = (self.headers.get("Host") or "127.0.0.1").split(",")[0].strip()
            obj, code = do_auth_request(payload, host)
            return self._send(obj, code)
        u = self._need_user()
        if not u:
            return
        if path == "/api/import":
            with _lock:
                c = db()
                done = c.execute("SELECT imported FROM business WHERE id=?",
                                 (u["business_id"],)).fetchone()[0]
                if done:
                    c.close()
                    out = state_of(u)
                    out["skipped"] = True
                    return self._send(out)
                c.execute("UPDATE business SET imported=1 WHERE id=?", (u["business_id"],))
                replace_observations(c, u["business_id"], u["id"], payload.get("observations") or {})
                replace_invites(c, u["business_id"], payload.get("invites") or [])
                lang = str(payload.get("language") or "en")[:8]
                c.execute("INSERT INTO pref(user_id, language) VALUES(?,?) "
                          "ON CONFLICT(user_id) DO UPDATE SET language=excluded.language",
                          (u["id"], lang))
                c.commit()
                c.close()
            return self._send(state_of(u))
        if path == "/api/dogs":
            slug = str(payload.get("slug") or "").strip().lower()
            name = str(payload.get("name") or slug).strip()[:80]
            if not SLUG_RE.match(slug):
                return self._send({"ok": False, "error": "bad slug"}, 400)
            with _lock:
                c = db()
                try:
                    c.execute(
                        "INSERT INTO dog(business_id, slug, name, created) VALUES(?,?,?,?)",
                        (u["business_id"], slug, name or slug, int(time.time())),
                    )
                    did = c.execute("SELECT last_insert_rowid()").fetchone()[0]
                    c.commit()
                except sqlite3.IntegrityError:
                    c.close()
                    return self._send({"ok": False, "error": "exists"}, 409)
                c.close()
            return self._send({"ok": True, "dog": {"id": did, "slug": slug, "name": name}})
        if path == "/api/blobs":
            raw = payload.get("data") or ""
            typ = str(payload.get("type") or "audio/webm")
            try:
                import base64
                blob = base64.b64decode(raw)
            except (ValueError, TypeError):
                return self._send({"ok": False, "error": "bad data"}, 400)
            if len(blob) > MAX_BODY:
                return self._send({"ok": False, "error": "too big"}, 413)
            ext = "webm"
            if "ogg" in typ:
                ext = "ogg"
            elif "mp4" in typ or "m4a" in typ:
                ext = "m4a"
            elif "wav" in typ:
                ext = "wav"
            elif "mpeg" in typ or "mp3" in typ:
                ext = "mp3"
            name = secrets.token_hex(16) + "." + ext
            dest_dir = os.path.join(blobs_dir(), str(u["business_id"]))
            os.makedirs(dest_dir, exist_ok=True)
            with open(os.path.join(dest_dir, name), "wb") as f:
                f.write(blob)
            return self._send({"ok": True, "ref": name})
        return self._send({"ok": False, "error": "not found"}, 404)

    def do_PUT(self):
        path = urlparse(self.path).path
        payload = self._read_json()
        if payload is None:
            return
        u = self._need_user()
        if not u:
            return
        with _lock:
            c = db()
            if path == "/api/observations":
                replace_observations(c, u["business_id"], u["id"], payload.get("observations") or {})
            elif path == "/api/invites":
                replace_invites(c, u["business_id"], payload.get("invites") or [])
            elif path == "/api/prefs":
                lang = str(payload.get("language") or "en")[:8]
                c.execute("INSERT INTO pref(user_id, language) VALUES(?,?) "
                          "ON CONFLICT(user_id) DO UPDATE SET language=excluded.language",
                          (u["id"], lang))
            else:
                c.close()
                return self._send({"ok": False, "error": "not found"}, 404)
            c.commit()
            c.close()
        return self._send(state_of(u))

    def _serve_static(self, path):
        root = static_root()
        rel = unquote(path)
        if rel == "/":
            rel = "/index.html"
        if ".." in rel.split("/"):
            self.send_error(404)
            return
        full = os.path.realpath(os.path.join(root, rel.lstrip("/")))
        if not full.startswith(root + os.sep) and full != root:
            self.send_error(404)
            return
        banned = ("/.git/", "/.dev-outbox/", "/api/blobs/", "/api/dogcare.db")
        if any(b in full.replace("\\", "/") for b in banned) or full.endswith(".db"):
            self.send_error(404)
            return
        if not os.path.isfile(full):
            self.send_error(404)
            return
        ext = os.path.splitext(full)[1].lower()
        with open(full, "rb") as fh:
            data = fh.read()
        if ext in (".html",) or os.path.basename(full) == "index.html":
            inject = b'<script>window.DOGCARE_API="/api";</script>'
            if inject not in data:
                data = data.replace(b"<head>", b"<head>\n    " + inject, 1)
        self.send_response(200)
        self.send_header("Content-Type", MIME.get(ext, "application/octet-stream"))
        self.send_header("Content-Length", str(len(data)))
        self.send_header("Cache-Control", "no-store")
        self.end_headers()
        self.wfile.write(data)


def main():
    init()
    host = cfg("DC_HOST", "127.0.0.1")
    port = int(cfg("DC_PORT", "8787"))
    httpd = ThreadingHTTPServer((host, port), Handler)
    print(f"dog-care-brain api on http://{host}:{port}  db={db_path()}  outbox={outbox_dir()}",
          flush=True)
    try:
        httpd.serve_forever()
    except KeyboardInterrupt:
        httpd.shutdown()


if __name__ == "__main__":
    main()
