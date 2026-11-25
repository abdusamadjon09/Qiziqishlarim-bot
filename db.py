import os
import time

import aiosqlite

from fields import FIELDS

SCHEMA = """
CREATE TABLE IF NOT EXISTS users(
  tg_id INTEGER PRIMARY KEY, username TEXT, tg_name TEXT,
  first_name TEXT, last_name TEXT, region TEXT, district TEXT, school TEXT,
  grade INTEGER, interests TEXT, fields TEXT DEFAULT '',
  banned INTEGER DEFAULT 0, registered INTEGER DEFAULT 0,
  created INTEGER, last_seen INTEGER);
CREATE TABLE IF NOT EXISTS groups(
  id INTEGER PRIMARY KEY AUTOINCREMENT, kind TEXT, key TEXT UNIQUE, name TEXT,
  chat_id INTEGER, invite_link TEXT, created INTEGER);
CREATE TABLE IF NOT EXISTS members(
  group_id INTEGER, tg_id INTEGER, joined INTEGER, UNIQUE(group_id, tg_id));
CREATE TABLE IF NOT EXISTS messages(
  id INTEGER PRIMARY KEY AUTOINCREMENT, tg_id INTEGER, direction TEXT, text TEXT, ts INTEGER);
"""

_db: aiosqlite.Connection | None = None


async def init(path: str):
    global _db
    os.makedirs(os.path.dirname(path) or ".", exist_ok=True)
    _db = await aiosqlite.connect(path)
    _db.row_factory = aiosqlite.Row
    await _db.executescript(SCHEMA)
    await _db.commit()
    for k, (name, _) in FIELDS.items():
        await ensure_group("field", k, name)
    for n in range(1, 12):
        await ensure_group("grade", str(n), f"{n}-sinf")


async def q(sql, args=()):
    cur = await _db.execute(sql, args)
    return [dict(r) for r in await cur.fetchall()]


async def one(sql, args=()):
    rows = await q(sql, args)
    return rows[0] if rows else None


async def run(sql, args=()):
    cur = await _db.execute(sql, args)
    await _db.commit()
    return cur.lastrowid


# ---------- foydalanuvchilar ----------
async def touch(u):
    now = int(time.time())
    name = u.full_name
    await run(
        "INSERT INTO users(tg_id,username,tg_name,created,last_seen) VALUES(?,?,?,?,?) "
        "ON CONFLICT(tg_id) DO UPDATE SET username=?, tg_name=?, last_seen=?",
        (u.id, u.username, name, now, now, u.username, name, now),
    )


async def get_user(tg_id):
    return await one("SELECT * FROM users WHERE tg_id=?", (tg_id,))


async def save_profile(tg_id, d: dict, fields: list[str]):
    await run(
        "UPDATE users SET first_name=?,last_name=?,region=?,district=?,school=?,grade=?,interests=?,fields=?,registered=1 WHERE tg_id=?",
        (d["first"], d["last"], d["region"], d["district"], d["school"], d["grade"], d["interests"], ",".join(fields), tg_id),
    )


async def log_msg(tg_id, direction, text):
    await run("INSERT INTO messages(tg_id,direction,text,ts) VALUES(?,?,?,?)", (tg_id, direction, (text or "")[:3000], int(time.time())))


# ---------- guruhlar ----------
async def ensure_group(kind, key, name):
    full = f"{kind}:{key}"
    g = await one("SELECT id FROM groups WHERE key=?", (full,))
    if g:
        return g["id"]
    return await run("INSERT INTO groups(kind,key,name,created) VALUES(?,?,?,?)", (kind, full, name, int(time.time())))


async def assign_groups(u: dict, fieldmap: dict | None = None):
    """Foydalanuvchini sinf, soha va maktab guruhlariga joylaydi."""
    await run(
        "DELETE FROM members WHERE tg_id=? AND group_id IN (SELECT id FROM groups WHERE kind IN ('field','grade','school'))",
        (u["tg_id"],),
    )
    gids = []
    for f in filter(None, (u["fields"] or "").split(",")):
        name = (fieldmap or {}).get(f) or FIELDS.get(f, (None,))[0] or f
        gids.append(await ensure_group("field", f, name))
    gids.append(await ensure_group("grade", str(u["grade"]), f"{u['grade']}-sinf"))
    skey = f"{u['region']}|{u['district']}|{u['school']}".lower()
    gids.append(await ensure_group("school", skey, f"🏫 {u['school']} ({u['district']})"))
    now = int(time.time())
    for g in gids:
        await run("INSERT OR IGNORE INTO members VALUES(?,?,?)", (g, u["tg_id"], now))
    return await user_groups(u["tg_id"])


async def user_groups(tg_id):
    return await q(
        "SELECT g.* FROM groups g JOIN members m ON m.group_id=g.id WHERE m.tg_id=? ORDER BY g.kind,g.name", (tg_id,)
    )


async def stats():
    return {
        "users": (await one("SELECT COUNT(*) c FROM users WHERE registered=1"))["c"],
        "all": (await one("SELECT COUNT(*) c FROM users"))["c"],
        "banned": (await one("SELECT COUNT(*) c FROM users WHERE banned=1"))["c"],
        "groups": (await one("SELECT COUNT(*) c FROM groups"))["c"],
        "bound": (await one("SELECT COUNT(*) c FROM groups WHERE chat_id IS NOT NULL"))["c"],
        "msgs": (await one("SELECT COUNT(*) c FROM messages"))["c"],
        "today": (await one("SELECT COUNT(*) c FROM users WHERE created>?", (int(time.time()) - 86400,)))["c"],
    }


async def field_names(keys: str):
    names = []
    for k in filter(None, (keys or "").split(",")):
        g = await one("SELECT name FROM groups WHERE key=?", ("field:" + k,))
        names.append(g["name"] if g else k)
    return names


async def close():
    global _db
    if _db:
        await _db.commit()
        await _db.close()
        _db = None
