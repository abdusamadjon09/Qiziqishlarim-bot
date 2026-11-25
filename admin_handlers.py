import asyncio
import csv
import io
import time
from html import escape as e

from aiogram import F, Router
from aiogram.filters import Command, CommandObject
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup
from aiogram.types import BufferedInputFile, CallbackQuery, Message

import config
import db
from fields import FIELDS
from keyboards import ikb

router = Router()
router.message.filter(F.from_user.id.in_(config.ADMIN_IDS))
router.callback_query.filter(F.from_user.id.in_(config.ADMIN_IDS))

PER = 8


class A(StatesGroup):
    reply = State()
    broadcast = State()
    search = State()
    newgroup = State()


def ts(t):
    return time.strftime("%d.%m %H:%M", time.localtime(t)) if t else "—"


def pager(prefix, page, total):
    row = []
    if page > 0:
        row.append(("⬅️", f"{prefix}:{page - 1}"))
    row.append((f"{page + 1}/{max(1, -(-total // PER))}", "a:noop"))
    if (page + 1) * PER < total:
        row.append(("➡️", f"{prefix}:{page + 1}"))
    return row


def menu_kb():
    return ikb([
        [("📊 Statistika", "a:stats"), ("👥 Foydalanuvchilar", "a:users:0")],
        [("🗂 Guruhlar", "a:groups:0"), ("🔎 Qidirish", "a:search")],
        [("🏫 Sinflar", "a:kind:grade"), ("🧩 Sohalar", "a:kind:field")],
        [("💬 Xabarlar", "a:msgs:0"), ("📣 Hammaga xabar", "a:bc:0")],
        [("➕ Guruh yaratish", "a:gnew"), ("📤 CSV eksport", "a:export")],
    ])


BACK = [("🏠 Menyu", "a:menu")]


async def show(c: CallbackQuery, text, kb):
    try:
        await c.message.edit_text(text, reply_markup=kb)
    except Exception:
        await c.message.answer(text, reply_markup=kb)
    await c.answer()


# ---------- menyu ----------
@router.message(Command("admin"))
async def admin_cmd(m: Message, state: FSMContext):
    await state.clear()
    await m.answer("🛠 <b>Admin panel</b>\nNima qilamiz?", reply_markup=menu_kb())


@router.callback_query(F.data == "a:menu")
async def menu(c: CallbackQuery, state: FSMContext):
    await state.clear()
    await show(c, "🛠 <b>Admin panel</b>\nNima qilamiz?", menu_kb())


@router.callback_query(F.data == "a:noop")
async def noop(c: CallbackQuery):
    await c.answer()


@router.callback_query(F.data == "a:stats")
async def stats(c: CallbackQuery):
    s = await db.stats()
    top = await db.q(
        "SELECT g.name, COUNT(m.tg_id) n FROM groups g LEFT JOIN members m ON m.group_id=g.id WHERE g.kind='field' GROUP BY g.id ORDER BY n DESC LIMIT 5"
    )
    text = (
        "📊 <b>Statistika</b>\n━━━━━━━━━━━━━━\n"
        f"👤 Ro'yxatdan o'tgan: <b>{s['users']}</b> (jami start: {s['all']})\n"
        f"🆕 Oxirgi 24 soatda: <b>{s['today']}</b>\n🚫 Bloklangan: {s['banned']}\n"
        f"🗂 Guruhlar: <b>{s['groups']}</b> (Telegramga ulangan: {s['bound']})\n💬 Xabarlar: {s['msgs']}\n\n"
        "🔥 <b>Top sohalar:</b>\n" + "\n".join(f"• {e(t['name'])} — {t['n']}" for t in top)
    )
    await show(c, text, ikb([BACK]))


# ---------- foydalanuvchilar ----------
@router.callback_query(F.data.startswith("a:users:"))
async def users(c: CallbackQuery):
    page = int(c.data.split(":")[2])
    total = (await db.one("SELECT COUNT(*) c FROM users WHERE registered=1"))["c"]
    rows = await db.q("SELECT * FROM users WHERE registered=1 ORDER BY created DESC LIMIT ? OFFSET ?", (PER, page * PER))
    kb = [[(f"{'🚫 ' if u['banned'] else ''}{u['first_name']} {u['last_name']} · {u['grade']}-sinf", f"a:user:{u['tg_id']}")] for u in rows]
    kb.append(pager("a:users", page, total))
    kb.append(BACK)
    await show(c, f"👥 <b>Foydalanuvchilar</b> ({total})", ikb(kb))


async def user_card(uid):
    u = await db.get_user(uid)
    if not u:
        return None, None
    groups = await db.user_groups(uid)
    text = (
        f"👤 <b>{e(u['first_name'] or u['tg_name'] or '?')} {e(u['last_name'] or '')}</b>\n"
        f"🆔 <code>{u['tg_id']}</code>" + (f" · @{u['username']}" if u["username"] else "") + "\n"
        f"📍 {e(u['region'] or '—')}, {e(u['district'] or '—')}\n🏫 {e(u['school'] or '—')} · {u['grade'] or '—'}-sinf\n"
        f"🎯 {e(u['interests'] or '—')}\n"
        f"🗂 {', '.join(e(g['name']) for g in groups) or '—'}\n"
        f"🕓 Ro'yxat: {ts(u['created'])} · Oxirgi: {ts(u['last_seen'])}\n"
        f"{'🚫 BLOKLANGAN' if u['banned'] else '✅ Faol'}"
    )
    kb = ikb([
        [("💬 Xabarlari", f"a:umsg:{uid}"), ("✉️ Javob yozish", f"a:reply:{uid}")],
        [("✅ Blokdan chiqarish" if u["banned"] else "🚫 Bloklash", f"a:ban:{uid}"), ("🗑 O'chirish", f"a:udel:{uid}")],
        [("⬅️ Ro'yxat", "a:users:0")] + BACK,
    ])
    return text, kb


@router.callback_query(F.data.startswith("a:user:"))
async def user_view(c: CallbackQuery):
    text, kb = await user_card(int(c.data.split(":")[2]))
    await show(c, text or "Topilmadi", kb or ikb([BACK]))


@router.callback_query(F.data.startswith("a:ban:"))
async def ban(c: CallbackQuery):
    uid = int(c.data.split(":")[2])
    u = await db.get_user(uid)
    await db.run("UPDATE users SET banned=? WHERE tg_id=?", (0 if u["banned"] else 1, uid))
    text, kb = await user_card(uid)
    await show(c, text, kb)


@router.callback_query(F.data.startswith("a:udel:"))
async def udel(c: CallbackQuery):
    uid = int(c.data.split(":")[2])
    await db.run("DELETE FROM members WHERE tg_id=?", (uid,))
    await db.run("DELETE FROM users WHERE tg_id=?", (uid,))
    await show(c, "🗑 Foydalanuvchi o'chirildi.", ikb([[("👥 Ro'yxat", "a:users:0")], BACK]))


@router.callback_query(F.data.startswith("a:umsg:"))
async def umsg(c: CallbackQuery):
    uid = int(c.data.split(":")[2])
    rows = await db.q("SELECT * FROM messages WHERE tg_id=? ORDER BY id DESC LIMIT 20", (uid,))
    lines = [f"{'👤' if r['direction'] == 'in' else '🛠'} <i>{ts(r['ts'])}</i> {e(r['text'][:200])}" for r in reversed(rows)]
    await show(c, "💬 <b>Botga yozgan xabarlari</b>\n\n" + ("\n".join(lines) or "Xabar yo'q"),
               ikb([[("✉️ Javob yozish", f"a:reply:{uid}")], [("⬅️ Orqaga", f"a:user:{uid}")]]))


@router.callback_query(F.data.startswith("a:reply:"))
async def reply_start(c: CallbackQuery, state: FSMContext):
    await state.set_state(A.reply)
    await state.update_data(uid=int(c.data.split(":")[2]))
    await c.message.answer("✉️ Javob matnini yuboring (bekor qilish: /admin):")
    await c.answer()


@router.message(A.reply)
async def reply_send(m: Message, state: FSMContext):
    uid = (await state.get_data())["uid"]
    try:
        await m.bot.send_message(uid, "👨‍💼 <b>Admin javobi:</b>\n\n" + e(m.text or m.caption or ""))
        await db.log_msg(uid, "out", m.text or "")
        await m.answer("✅ Yuborildi", reply_markup=ikb([[("👤 Profil", f"a:user:{uid}")], BACK]))
    except Exception as ex:
        await m.answer(f"❌ Yuborilmadi: {e(str(ex))}")
    await state.clear()


@router.callback_query(F.data.startswith("a:msgs:"))
async def all_msgs(c: CallbackQuery):
    page = int(c.data.split(":")[2])
    total = (await db.one("SELECT COUNT(*) c FROM messages WHERE direction='in'"))["c"]
    rows = await db.q(
        "SELECT m.*, u.first_name, u.tg_name FROM messages m LEFT JOIN users u ON u.tg_id=m.tg_id "
        "WHERE direction='in' ORDER BY m.id DESC LIMIT ? OFFSET ?", (PER, page * PER))
    kb = [[(f"{(r['first_name'] or r['tg_name'] or r['tg_id'])}: {r['text'][:28]}", f"a:umsg:{r['tg_id']}")] for r in rows]
    kb.append(pager("a:msgs", page, total))
    kb.append(BACK)
    await show(c, "💬 <b>So'nggi xabarlar</b> (tanlang — to'liq suhbat)", ikb(kb))


# ---------- guruhlar ----------
async def group_rows(where="", args=(), page=0):
    return await db.q(
        f"SELECT g.*, (SELECT COUNT(*) FROM members m WHERE m.group_id=g.id) n FROM groups g {where} "
        "ORDER BY n DESC, g.name LIMIT ? OFFSET ?", (*args, PER, page * PER))


@router.callback_query(F.data.startswith("a:groups:"))
async def groups(c: CallbackQuery):
    page = int(c.data.split(":")[2])
    total = (await db.one("SELECT COUNT(*) c FROM groups"))["c"]
    rows = await group_rows(page=page)
    kb = [[(f"{'🔗' if g['chat_id'] else '⏳'} {g['name']} ({g['n']})", f"a:group:{g['id']}")] for g in rows]
    kb.append(pager("a:groups", page, total))
    kb.append(BACK)
    await show(c, f"🗂 <b>Guruhlar</b> ({total})\n🔗 — Telegram guruhga ulangan", ikb(kb))


@router.callback_query(F.data.startswith("a:kind:"))
async def kind(c: CallbackQuery):
    k = c.data.split(":")[2]
    rows = await db.q(
        "SELECT g.*, (SELECT COUNT(*) FROM members m WHERE m.group_id=g.id) n FROM groups g WHERE kind=? ORDER BY length(key), key", (k,))
    title = {"grade": "🏫 Sinflar bo'yicha", "field": "🧩 Sohalar bo'yicha"}[k]
    kb = [[(f"{g['name']} — {g['n']} a'zo", f"a:group:{g['id']}")] for g in rows]
    kb.append(BACK)
    await show(c, f"<b>{title}</b>", ikb(kb))


@router.callback_query(F.data.startswith("a:group:"))
async def group_view(c: CallbackQuery):
    gid = int(c.data.split(":")[2])
    g = await db.one("SELECT * FROM groups WHERE id=?", (gid,))
    if not g:
        return await show(c, "Guruh topilmadi", ikb([BACK]))
    n = (await db.one("SELECT COUNT(*) c FROM members WHERE group_id=?", (gid,)))["c"]
    tg = ""
    if g["chat_id"]:
        try:
            tg = f"\n📱 Telegram guruhdagi a'zolar: <b>{await c.bot.get_chat_member_count(g['chat_id'])}</b>"
        except Exception:
            tg = "\n⚠️ Telegram guruhga ulanib bo'lmadi (bot guruhda adminmi?)"
    text = (
        f"🗂 <b>{e(g['name'])}</b>\nTuri: {g['kind']} · ID: <code>{gid}</code>\n👥 Bot a'zolari: <b>{n}</b>{tg}\n"
        + (f"🔗 {g['invite_link']}" if g["invite_link"] else
           f"\n⏳ Telegram guruh ulanmagan. Botni guruhga admin qilib qo'shing va guruhda yozing:\n<code>/bind {gid}</code>")
    )
    kb = [[("👥 A'zolar", f"a:gm:{gid}:0"), ("📣 A'zolarga xabar", f"a:bc:{gid}")]]
    if g["chat_id"]:
        kb.append([("🔓 Ulanishni uzish", f"a:unbind:{gid}")])
    if g["kind"] in ("custom", "school", "field"):
        kb.append([("🗑 Guruhni o'chirish", f"a:gdel:{gid}")])
    kb.append([("⬅️ Guruhlar", "a:groups:0")] + BACK)
    await show(c, text, ikb(kb))


@router.callback_query(F.data.startswith("a:gm:"))
async def group_members(c: CallbackQuery):
    _, _, gid, page = c.data.split(":")
    gid, page = int(gid), int(page)
    total = (await db.one("SELECT COUNT(*) c FROM members WHERE group_id=?", (gid,)))["c"]
    rows = await db.q(
        "SELECT u.* FROM users u JOIN members m ON m.tg_id=u.tg_id WHERE m.group_id=? ORDER BY m.joined DESC LIMIT ? OFFSET ?",
        (gid, PER, page * PER))
    kb = [[(f"{u['first_name']} {u['last_name']} · {u['grade']}-sinf", f"a:user:{u['tg_id']}")] for u in rows]
    kb.append(pager(f"a:gm:{gid}", page, total))
    kb.append([("⬅️ Guruh", f"a:group:{gid}")])
    await show(c, f"👥 <b>A'zolar</b> ({total})", ikb(kb))


@router.callback_query(F.data.startswith("a:unbind:"))
async def unbind(c: CallbackQuery):
    gid = int(c.data.split(":")[2])
    await db.run("UPDATE groups SET chat_id=NULL, invite_link=NULL WHERE id=?", (gid,))
    await c.answer("Uzildi")
    await group_view(c)


@router.callback_query(F.data.startswith("a:gdel:"))
async def gdel(c: CallbackQuery):
    gid = int(c.data.split(":")[2])
    await db.run("DELETE FROM members WHERE group_id=?", (gid,))
    await db.run("DELETE FROM groups WHERE id=?", (gid,))
    await show(c, "🗑 Guruh o'chirildi.", ikb([[("🗂 Guruhlar", "a:groups:0")], BACK]))


@router.callback_query(F.data == "a:gnew")
async def gnew(c: CallbackQuery, state: FSMContext):
    await state.set_state(A.newgroup)
    await c.message.answer("➕ Yangi guruh nomini yozing (masalan: <i>Robototexnika to'garagi</i>):")
    await c.answer()


@router.message(A.newgroup, F.text)
async def gnew_save(m: Message, state: FSMContext):
    name = m.text.strip()[:60]
    gid = await db.ensure_group("custom", name.lower(), f"⭐ {name}")
    await state.clear()
    await m.answer(f"✅ Guruh yaratildi (ID {gid}). Telegram guruhga ulash uchun uni guruhda yozing:\n<code>/bind {gid}</code>",
                   reply_markup=ikb([[("🗂 Ochish", f"a:group:{gid}")], BACK]))


@router.message(Command("bind"), F.chat.type.in_({"group", "supergroup"}))
async def bind(m: Message, command: CommandObject):
    if not command.args or not command.args.strip().isdigit():
        return await m.reply("Ishlatish: /bind &lt;guruh_ID&gt; (ID ni admin paneldan oling)")
    gid = int(command.args.strip())
    if not await db.one("SELECT id FROM groups WHERE id=?", (gid,)):
        return await m.reply("❌ Bunday guruh ID yo'q")
    link = None
    try:
        link = (await m.bot.create_chat_invite_link(m.chat.id, name="Qiziqishlarim bot")).invite_link
    except Exception:
        try:
            link = await m.bot.export_chat_invite_link(m.chat.id)
        except Exception:
            pass
    await db.run("UPDATE groups SET chat_id=?, invite_link=? WHERE id=?", (m.chat.id, link, gid))
    await m.reply("✅ Guruh ulandi!" + ("" if link else "\n⚠️ Havola olinmadi — botga «havola yaratish» huquqini bering."))


# ---------- qidirish ----------
@router.callback_query(F.data == "a:search")
async def search_start(c: CallbackQuery, state: FSMContext):
    await state.set_state(A.search)
    await c.message.answer("🔎 Ism, @username, maktab, qiziqish yoki guruh nomini yozing:")
    await c.answer()


@router.message(A.search, F.text)
async def search_do(m: Message, state: FSMContext):
    await state.clear()
    like = f"%{m.text.strip().lstrip('@')}%"
    us = await db.q(
        "SELECT * FROM users WHERE registered=1 AND (first_name LIKE ? OR last_name LIKE ? OR username LIKE ? OR school LIKE ? "
        "OR interests LIKE ? OR district LIKE ? OR CAST(tg_id AS TEXT) LIKE ?) LIMIT 15", (like,) * 7)
    gs = await group_rows("WHERE g.name LIKE ?", (like,))
    kb = [[(f"🗂 {g['name']} ({g['n']})", f"a:group:{g['id']}")] for g in gs]
    kb += [[(f"👤 {u['first_name']} {u['last_name']} · {u['grade']}-sinf", f"a:user:{u['tg_id']}")] for u in us]
    kb.append(BACK)
    await m.answer(f"🔎 Natija: {len(gs)} guruh, {len(us)} foydalanuvchi", reply_markup=ikb(kb))


# ---------- xabar tarqatish ----------
@router.callback_query(F.data.startswith("a:bc:"))
async def bc_start(c: CallbackQuery, state: FSMContext):
    gid = int(c.data.split(":")[2])
    await state.set_state(A.broadcast)
    await state.update_data(gid=gid)
    await c.message.answer("📣 Yuboriladigan xabarni jo'nating (matn/rasm/video). Bekor qilish: /admin")
    await c.answer()


@router.message(A.broadcast)
async def bc_send(m: Message, state: FSMContext):
    gid = (await state.get_data())["gid"]
    await state.clear()
    if gid:
        ids = [r["tg_id"] for r in await db.q("SELECT tg_id FROM members WHERE group_id=?", (gid,))]
    else:
        ids = [r["tg_id"] for r in await db.q("SELECT tg_id FROM users WHERE registered=1 AND banned=0")]
    ok = bad = 0
    status = await m.answer(f"⏳ Yuborilmoqda... ({len(ids)})")
    for uid in ids:
        try:
            await m.bot.copy_message(uid, m.chat.id, m.message_id)
            ok += 1
        except Exception:
            bad += 1
        await asyncio.sleep(0.05)
    await status.edit_text(f"✅ Yuborildi: {ok}\n❌ Xato: {bad}", reply_markup=ikb([BACK]))


# ---------- eksport ----------
@router.callback_query(F.data == "a:export")
async def export(c: CallbackQuery):
    rows = await db.q("SELECT * FROM users WHERE registered=1 ORDER BY created")
    buf = io.StringIO()
    w = csv.writer(buf)
    w.writerow(["tg_id", "username", "ism", "familiya", "viloyat", "tuman", "maktab", "sinf", "qiziqishlar", "sohalar", "ro'yxat"])
    for u in rows:
        w.writerow([u["tg_id"], u["username"], u["first_name"], u["last_name"], u["region"], u["district"], u["school"],
                    u["grade"], u["interests"], u["fields"], ts(u["created"])])
    await c.message.answer_document(BufferedInputFile(buf.getvalue().encode("utf-8-sig"), "foydalanuvchilar.csv"))
    await c.answer("Tayyor")
