"""Validated business daily records and private document storage contracts."""
import base64
import binascii
import json
import re
from datetime import date

ID = re.compile(r"[A-Za-z0-9][A-Za-z0-9_-]{0,80}")
CURRENCY = re.compile(r"[A-Z]{3}")
MAX_FILE = 5 * 1024 * 1024
MAX_RECORDS = 5000


def empty():
    return {"version": 1, "clients": [], "dogs": [], "bookings": [],
            "rates": {"currency": "CHF", "walk": None, "day": None, "night": None},
            "documents": []}


def load(c, bid):
    row = c.execute("SELECT snapshot FROM business_daily WHERE business_id=?", (bid,)).fetchone()
    return json.loads(row[0]) if row else empty()


def bind_clients(c, bid, value):
    families = {dog['id']:dog['clientId'] for dog in value['dogs']}
    for booking in value['bookings']:
        cid = families.get(booking['dogId'])
        if cid:
            c.execute('INSERT OR IGNORE INTO booking_client(business_id,id,client_id) VALUES(?,?,?)',(bid,booking['id'],cid))


def save(c, bid, value):
    bind_clients(c,bid,value)
    c.execute("INSERT INTO business_daily(business_id,snapshot) VALUES(?,?) "
              "ON CONFLICT(business_id) DO UPDATE SET snapshot=excluded.snapshot",
              (bid, json.dumps(value, ensure_ascii=False)))


def text(value, key, limit=120, optional=False):
    if (not isinstance(value, str) or len(value) > limit or
            (not optional and not value.strip()) or
            any(ord(ch) < 32 or ord(ch) == 127 for ch in value)):
        raise ValueError("bad " + key)
    return value


def identifier(value):
    if not isinstance(value, str) or not ID.fullmatch(value):
        raise ValueError("bad id")
    return value


def amount(value):
    if value is not None and (type(value) is not int or not 0 <= value <= 100000000):
        raise ValueError("bad amount")
    return value


def currency(value):
    if not isinstance(value, str) or not CURRENCY.fullmatch(value):
        raise ValueError("bad currency")
    return value


def calendar(value, optional=False):
    if optional and value == "":
        return None
    if not isinstance(value, str) or not re.fullmatch(r"\d{4}-\d{2}-\d{2}", value):
        raise ValueError("bad date")
    try:
        return date.fromisoformat(value)
    except ValueError:
        raise ValueError("bad date") from None


def fields(item, required):
    if not isinstance(item, dict) or set(item) != set(required.split()):
        raise ValueError("bad fields")


def collection(value):
    if not isinstance(value, list) or len(value) > MAX_RECORDS:
        raise ValueError("bad collection")
    ids = set()
    for item in value:
        if not isinstance(item, dict):
            raise ValueError("bad record")
        ident = identifier(item.get("id"))
        if ident in ids:
            raise ValueError("duplicate id")
        ids.add(ident)
    return ids


def validate(value, previous):
    fields(value, "version clients dogs bookings rates documents")
    if type(value["version"]) is not int or value["version"] != 1:
        raise ValueError("bad version")
    clients = collection(value["clients"])
    dogs = collection(value["dogs"])
    collection(value["bookings"])
    collection(value["documents"])
    for client in value["clients"]:
        fields(client, "id name")
        text(client["name"], "client name")
    for dog in value["dogs"]:
        fields(dog, "id name clientId")
        text(dog["name"], "dog name")
        if dog["clientId"] is not None:
            identifier(dog["clientId"])
        if dog["clientId"] is not None and dog["clientId"] not in clients:
            raise ValueError("unknown client")
    rates = value["rates"]
    fields(rates, "currency walk day night")
    currency(rates["currency"])
    for service in ("walk", "day", "night"):
        amount(rates[service])
    dog_clients = {item["id"]: item["clientId"] for item in value["dogs"]}
    old_bookings = {item["id"]: item for item in previous["bookings"]}
    for booking in value["bookings"]:
        fields(booking, "id dogId service start end unitMinor currency")
        identifier(booking["dogId"])
        if booking["dogId"] not in dogs:
            raise ValueError("unknown dog")
        if dog_clients[booking["dogId"]] not in clients:
            raise ValueError("booking needs a recorded client")
        if booking["service"] not in ("walk", "day", "night"):
            raise ValueError("bad service")
        days = (calendar(booking["end"]) - calendar(booking["start"])).days
        units = days if booking["service"] == "night" else days + 1
        if not 1 <= units <= 366:
            raise ValueError("bad booking range")
        amount(booking["unitMinor"])
        currency(booking["currency"])
        old = old_bookings.get(booking["id"])
        if old and old["service"] == booking["service"] and old["unitMinor"] is not None and any(
                old[key] != booking[key] for key in ("unitMinor", "currency")):
            raise ValueError("existing booking agreement must be retained")
    old_documents = {item["id"]: item for item in previous["documents"]}
    if {item["id"] for item in value["documents"]} != set(old_documents):
        raise ValueError("documents must be uploaded separately")
    for document in value["documents"]:
        fields(document, "id dogId label renewal type name href")
        old = old_documents[document["id"]]
        if any(document[key] != old[key] for key in ("dogId", "type", "name", "href")):
            raise ValueError("document reference cannot change")
        if document["dogId"] not in dogs:
            raise ValueError("unknown dog")
        text(document["label"], "document label")
        calendar(document["renewal"], optional=True)
    return value


def upload(payload, current):
    fields(payload, "dogId label renewal name type data")
    identifier(payload["dogId"])
    if payload["dogId"] not in {dog["id"] for dog in current["dogs"]}:
        raise ValueError("unknown dog")
    if len(current["documents"]) >= MAX_RECORDS:
        raise ValueError("too many documents")
    text(payload["label"], "document label")
    text(payload["name"], "file name", 180)
    calendar(payload["renewal"], optional=True)
    signatures = {"application/pdf": b"%PDF-", "image/jpeg": b"\xff\xd8\xff",
                  "image/png": b"\x89PNG\r\n\x1a\n"}
    typ = payload["type"]
    if not isinstance(typ, str) or typ not in signatures:
        raise ValueError("unsupported document type")
    raw = payload["data"]
    if not isinstance(raw, str) or len(raw) > ((MAX_FILE + 2) // 3) * 4:
        raise ValueError("document exceeds 5 MiB")
    try:
        blob = base64.b64decode(raw, validate=True)
    except (ValueError, binascii.Error):
        raise ValueError("bad document data") from None
    if not blob or len(blob) > MAX_FILE or not blob.startswith(signatures[typ]):
        raise ValueError("invalid document contents")
    return blob
