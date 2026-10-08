"""Explicit client projections and mutations; never expose internal care snapshots."""
import secrets
import re
import time

import daily
import quotes

STAFF = ("owner", "trusted-carer")
ROLES = (*STAFF, "client")


def message(value, limit, optional=False):
    if (not isinstance(value, str) or len(value) > limit or (not optional and not value.strip()) or
            re.search(r"[\x00-\x08\x0b-\x1f\x7f]", value)):
        raise ValueError("invalid message")


def client_id(c, user):
    row = c.execute("SELECT client_id FROM client_access WHERE user_id=? AND business_id=?",
                    (user["id"], user["business_id"])).fetchone()
    return row[0] if row else None


def allowed_dogs(c, user, current=None):
    current = current if current is not None else daily.load(c, user["business_id"])
    cid = client_id(c, user)
    return {d["id"] for d in current["dogs"] if cid is not None and d["clientId"] == cid}


def snapshot(c, user, current):
    bid = user["business_id"]
    staff = user["role"] in STAFF
    allowed = {d["id"] for d in current["dogs"]} if staff else allowed_dogs(c, user, current)
    cid = client_id(c,user)
    audiences = {row[0]:row[1] for row in c.execute("SELECT id,client_id FROM booking_client WHERE business_id=?",(bid,))}
    updates = [dict(row) for row in c.execute(
        "SELECT id,dog_id AS dogId,client_id AS clientId,text,created FROM client_update WHERE business_id=? ORDER BY created DESC,id", (bid,))
        if row["dogId"] in allowed and (staff or row["clientId"] == cid)]
    requests = [dict(row) for row in c.execute(
        "SELECT id,client_id AS clientId,dog_id AS dogId,service,start,end,note,status FROM booking_request WHERE business_id=? ORDER BY created DESC,id", (bid,))
        if row["dogId"] in allowed and (staff or row["clientId"] == cid)]
    cancelled = {b['id'] for b in current['bookings'] if b.get('status') == 'cancelled'}
    for request in requests:
        if request['status'] == 'accepted' and request['id'] in cancelled:
            request['status'] = 'cancelled'
    documents = [dict(row) for row in c.execute(
        "SELECT id,dog_id AS dogId,client_id AS clientId,label,name,mime AS type FROM client_document WHERE business_id=?", (bid,))
        if row["dogId"] in allowed and (staff or row["clientId"] == cid)]
    members = []
    if user["role"] == "owner":
        members = [dict(row) for row in c.execute(
            "SELECT u.id,u.email,u.role,a.client_id AS clientId FROM user u LEFT JOIN client_access a ON a.user_id=u.id "
            "WHERE u.business_id=? AND u.role IN ('client','trusted-carer') ORDER BY u.email", (bid,))]
    visible_bookings = [b for b in current['bookings'] if b['dogId'] in allowed and (staff or audiences.get(b['id']) == cid)]
    prices = {r['id']: quotes.quote(c, bid, r) for r in requests}
    prices.update({b['id']: quotes.quote(c, bid, b, booking=True) for b in visible_bookings})
    return {"updates": updates, "requests": requests, "documents": documents, "members": members,
            "bookingClients": {b['id']: audiences[b['id']] for b in visible_bookings if b['id'] in audiences},
            "quotes": prices, "extras": quotes.templates(c, bid) if user['role'] == 'owner' else []}


def project(c, user, state):
    current = state["daily"]
    state["portal"] = snapshot(c, user, current)
    if user["role"] == "client":
        allowed = allowed_dogs(c, user, current)
        cid = client_id(c, user)
        state.update(imported=True, observations={}, invites=[], knowledge=None, finance=None)
        state["dogs"] = [{"id": d["id"], "slug": d["id"], "name": d["name"]}
                         for d in current["dogs"] if d["id"] in allowed]
        booked = {r[0] for r in c.execute("SELECT id FROM booking_client WHERE business_id=? AND client_id=?",(user["business_id"],cid))}
        state["daily"] = {**daily.empty(),
                          "clients": [x for x in current["clients"] if x["id"] == cid],
                          "dogs": [x for x in current["dogs"] if x["id"] in allowed],
                          "bookings": [x for x in current["bookings"] if x["dogId"] in allowed and x["id"] in booked]}
    elif user["role"] != "owner":
        state.update(invites=[], finance=None)
    return state


def add_member(c, user, payload):
    daily.fields(payload, "email role clientId")
    email = payload["email"].strip().lower() if isinstance(payload["email"], str) else ""
    role = payload["role"]
    if role not in ("client", "trusted-carer") or not email or len(email) > 255:
        raise ValueError("invalid member")
    current = daily.load(c, user["business_id"])
    if role == "client" and payload["clientId"] not in {x["id"] for x in current["clients"]}:
        raise ValueError("unknown client")
    existing = c.execute("SELECT id,business_id,role FROM user WHERE email=?", (email,)).fetchone()
    if existing and (existing["business_id"] != user["business_id"] or existing["role"] not in ("client", "trusted-carer", "revoked")):
        raise ValueError("this account cannot be reassigned")
    if existing:
        uid = existing["id"]
        c.execute("UPDATE user SET role=? WHERE id=?", (role, uid))
        c.execute("DELETE FROM session WHERE user_id=?", (uid,))
    else:
        uid = c.execute("INSERT INTO user(email,role,business_id,created) VALUES(?,?,?,?)",
                        (email, role, user["business_id"], int(time.time()))).lastrowid
        c.execute("INSERT INTO pref(user_id,language) VALUES(?,'fr')", (uid,))
    c.execute("DELETE FROM client_access WHERE user_id=?", (uid,))
    if role == "client":
        c.execute("INSERT INTO client_access(user_id,business_id,client_id) VALUES(?,?,?)",
                  (uid, user["business_id"], payload["clientId"]))


def mutate(c, user, route, payload):
    bid = user["business_id"]
    current = daily.load(c, bid)
    if route == "members":
        add_member(c, user, payload)
    elif route == "revoke":
        daily.fields(payload, "userId")
        if type(payload["userId"]) is not int:
            raise ValueError("invalid member")
        row = c.execute("SELECT id FROM user WHERE id=? AND business_id=? AND role IN ('client','trusted-carer')",
                        (payload["userId"], bid)).fetchone()
        if not row:
            raise ValueError("unknown member")
        c.execute("UPDATE user SET role='revoked' WHERE id=?", (row[0],))
        c.execute("DELETE FROM client_access WHERE user_id=?", (row[0],))
        c.execute("DELETE FROM session WHERE user_id=?", (row[0],))
    elif route == "requests":
        daily.fields(payload, "dogId service start end note")
        if payload["dogId"] not in allowed_dogs(c, user, current):
            raise PermissionError("dog access denied")
        if payload["service"] not in ("walk", "day", "night"):
            raise ValueError("invalid service")
        units = (daily.calendar(payload["end"]) - daily.calendar(payload["start"])).days + (payload["service"] != "night")
        if not 1 <= units <= 366:
            raise ValueError("invalid dates")
        message(payload["note"], 2000, optional=True)
        ident = secrets.token_hex(16)
        c.execute("INSERT INTO booking_request(id,business_id,user_id,dog_id,client_id,service,start,end,note,created) VALUES(?,?,?,?,?,?,?,?,?,?)",
                  (ident, bid, user["id"], payload["dogId"], client_id(c,user), payload["service"], payload["start"], payload["end"], payload["note"], int(time.time())))
        quotes.capture(c, bid, ident, current, payload)
    elif route == "decide":
        daily.fields(payload, "id status")
        if payload["status"] not in ("accepted", "declined"):
            raise ValueError("invalid decision")
        request = c.execute("SELECT * FROM booking_request WHERE business_id=? AND id=? AND status='requested'", (bid, payload["id"])).fetchone()
        if not request or not any(d["id"] == request["dog_id"] and d["clientId"] == request["client_id"] for d in current["dogs"]):
            raise ValueError("request unavailable")
        if payload["status"] == "accepted":
            price = quotes.quote(c, bid, dict(request))
            current["bookings"].append({"id": request["id"], "dogId": request["dog_id"], "service": request["service"],
                                        "start": request["start"], "end": request["end"], "unitMinor": price["unitMinor"], "currency": price["currency"]})
            daily.validate(current, daily.load(c, bid))
            daily.save(c, bid, current)
        c.execute("UPDATE booking_request SET status=? WHERE id=? AND business_id=?", (payload["status"], request["id"], bid))
    elif route == 'cancel-booking':
        if user['role'] != 'owner':
            raise PermissionError('only the owner can cancel a booking')
        daily.fields(payload, 'id')
        daily.identifier(payload['id'])
        booking = next((b for b in current['bookings'] if b['id'] == payload['id']), None)
        if not booking:
            raise ValueError('booking unavailable')
        booking['status'] = 'cancelled'
        daily.validate(current, daily.load(c, bid), cancelling=True)
        daily.save(c, bid, current)
    elif route in ("extras", "extra-remove", "quote"):
        quotes.mutate(c, bid, current, route, payload)
    elif route == "updates":
        daily.fields(payload, "dogId text")
        if payload["dogId"] not in {d["id"] for d in current["dogs"] if d["clientId"] is not None}:
            raise ValueError("unknown client dog")
        message(payload["text"], 4000)
        c.execute("INSERT INTO client_update(id,business_id,dog_id,client_id,author_id,text,created) VALUES(?,?,?,?,?,?,?)",
                  (secrets.token_hex(16), bid, payload["dogId"], next(d["clientId"] for d in current["dogs"] if d["id"] == payload["dogId"]), user["id"], payload["text"], int(time.time())))
    elif route == "documents":
        blob = daily.upload(payload, current)
        if payload["dogId"] not in {d["id"] for d in current["dogs"] if d["clientId"] is not None}:
            raise ValueError("unknown client dog")
        c.execute("INSERT INTO client_document(id,business_id,dog_id,client_id,label,name,mime,contents) VALUES(?,?,?,?,?,?,?,?)",
                  (secrets.token_hex(16), bid, payload["dogId"], next(d["clientId"] for d in current["dogs"] if d["id"] == payload["dogId"]), payload["label"], payload["name"], payload["type"], blob))
    else:
        raise ValueError("unknown action")
