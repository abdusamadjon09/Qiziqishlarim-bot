from html import escape as e

from aiogram import F, Router
from aiogram.filters import Command, CommandStart
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup
from aiogram.types import CallbackQuery, Message

import config
import db
from fields import extract
from keyboards import MAIN_BTNS, REGIONS, grade_kb, ikb, main_menu, region_kb

router = Router()
router.message.filter(F.chat.type == "private")


class Reg(StatesGroup):
    first = State()
    last = State()
    region = State()
    district = State()
    school = State()
    grade = State()
    interests = State()


class Edit(StatesGroup):
    interests = State()


class Search(StatesGroup):
    query = State()


WELCOME = (
    "🌟 <b>Qiziqishlarim PRO</b> botiga xush kelibsiz!\n\n"
    "Bu yerda maktabdagi bir xil qiziqish egalarini topasiz — bot sizni sinf, soha va maktab "
    "bo'yicha guruhlarga avtomatik joylaydi.\n\n"
    "🔒 <i>Eslatma: botga yozgan xabarlaringiz administratorlar tomonidan ko'rilishi mumkin.</i>\n\n"
    "Keling, ro'yxatdan o'tamiz 👇\n\n✍️ <b>Ismingizni</b> yozing:"
)


async def profile_text(u):
    fields = ", ".join(await db.field_names(u["fields"])) or "—"
    return (
        f"👤 <b>{e(u['first_name'])} {e(u['last_name'])}</b>\n"
        f"━━━━━━━━━━━━━━\n"
        f"📍 {e(u['region'])}, {e(u['district'])}\n"
        f"🏫 {e(u['school'])} · <b>{u['grade']}-sinf</b>\n"
        f"🎯 <b>Qiziqishlar:</b> {e(u['interests'])}\n"
        f"🧩 <b>Sohalar:</b> {e(fields)}"
    )


def groups_markup(groups):
    rows = [[(f"{g['name']} ↗", g["invite_link"])] for g in groups if g["invite_link"]]
    return ikb(rows) if rows else None


async def groups_text(groups):
    if not groups:
        return "Hozircha guruh yo'q."
    lines = []
    for g in groups:
        n = (await db.one("SELECT COUNT(*) c FROM members WHERE group_id=?", (g["id"],)))["c"]
        mark = "🔗" if g["invite_link"] else "⏳"
        lines.append(f"{mark} <b>{e(g['name'])}</b> — {n} a'zo")
    return "\n".join(lines) + "\n\n🔗 — Telegram guruh ulangan, ⏳ — tez orada ulanadi"


async def apply_fields(bot, tg_id, text):
    """Qiziqishlarni saqlaydi, yangi sohalar uchun guruh ochadi va foydalanuvchini guruhlarga joylaydi."""
    fm = extract(text)
    new = [n for k, n in fm.items() if not await db.one("SELECT 1 FROM groups WHERE key=?", ("field:" + k,))]
    return fm, new


async def notify_new_fields(bot, new):
    if not new:
        return
    for admin_id in config.ADMIN_IDS:
        try:
            await bot.send_message(admin_id, "🆕 <b>Yangi soha guruhi ochildi:</b>\n" + "\n".join(e(n) for n in new))
        except Exception:
            pass


# ---------- start / ro'yxat ----------
@router.message(CommandStart())
async def start(m: Message, state: FSMContext):
    await state.clear()
    u = await db.get_user(m.from_user.id)
    if u and u["registered"]:
        await m.answer(f"👋 Qaytganingiz bilan, <b>{e(u['first_name'])}</b>!", reply_markup=main_menu())
        return
    await state.set_state(Reg.first)
    await m.answer(WELCOME)


@router.message(Reg.first, F.text)
async def r_first(m: Message, state: FSMContext):
    if not 2 <= len(m.text) <= 40:
        return await m.answer("Ism 2–40 harf bo'lsin. Qayta yozing:")
    await state.update_data(first=m.text.strip())
    await state.set_state(Reg.last)
    await m.answer("👨‍👩‍👧 <b>Familiyangizni</b> yozing:")


@router.message(Reg.last, F.text)
async def r_last(m: Message, state: FSMContext):
    if not 2 <= len(m.text) <= 40:
        return await m.answer("Familiya 2–40 harf bo'lsin. Qayta yozing:")
    await state.update_data(last=m.text.strip())
    await state.set_state(Reg.region)
    await m.answer("🗺 <b>Viloyatingizni</b> tanlang:", reply_markup=region_kb())


@router.callback_query(Reg.region, F.data.startswith("reg:r:"))
async def r_region(c: CallbackQuery, state: FSMContext):
    await state.update_data(region=REGIONS[int(c.data.split(":")[2])])
    await state.set_state(Reg.district)
    await c.message.edit_text("🏘 <b>Tuman/shahringizni</b> yozing:")
    await c.answer()


@router.message(Reg.district, F.text)
async def r_district(m: Message, state: FSMContext):
    await state.update_data(district=m.text.strip()[:60])
    await state.set_state(Reg.school)
    await m.answer("🏫 <b>Maktabingiz</b> raqami/nomini yozing (masalan: 12-maktab):")


@router.message(Reg.school, F.text)
async def r_school(m: Message, state: FSMContext):
    await state.update_data(school=m.text.strip()[:60])
    await state.set_state(Reg.grade)
    await m.answer("🎓 <b>Sinfingizni</b> tanlang:", reply_markup=grade_kb())


@router.callback_query(Reg.grade, F.data.startswith("reg:g:"))
async def r_grade(c: CallbackQuery, state: FSMContext):
    await state.update_data(grade=int(c.data.split(":")[2]))
    await state.set_state(Reg.interests)
    await c.message.edit_text(
        "🎯 <b>Qiziqishlaringizni</b> vergul bilan yozing.\n<i>Masalan: Python, futbol, kitob, ingliz tili</i>"
    )
    await c.answer()


@router.message(Reg.interests, F.text)
async def r_interests(m: Message, state: FSMContext):
    d = await state.get_data()
    d["interests"] = m.text.strip()[:300]
    fm, new = await apply_fields(m.bot, m.from_user.id, d["interests"])
    await db.save_profile(m.from_user.id, d, list(fm))
    await state.clear()
    u = await db.get_user(m.from_user.id)
    groups = await db.assign_groups(u, fm)
    await notify_new_fields(m.bot, new)
    await m.answer("✅ <b>Ro'yxatdan o'tdingiz!</b>", reply_markup=main_menu())
    await m.answer(await profile_text(u))
    await m.answer("👥 <b>Sizning guruhlaringiz:</b>\n\n" + await groups_text(groups), reply_markup=groups_markup(groups))
    for admin_id in config.ADMIN_IDS:
        try:
            await m.bot.send_message(admin_id, "🆕 <b>Yangi a'zo</b>\n\n" + await profile_text(u))
        except Exception:
            pass


# ---------- menyu ----------
@router.message(F.text == "👤 Profilim")
async def me(m: Message):
    u = await db.get_user(m.from_user.id)
    if not u or not u["registered"]:
        return await m.answer("Avval /start orqali ro'yxatdan o'ting.")
    await m.answer(await profile_text(u))


@router.message(F.text == "👥 Guruhlarim")
async def my_groups(m: Message):
    groups = await db.user_groups(m.from_user.id)
    await m.answer("👥 <b>Guruhlaringiz:</b>\n\n" + await groups_text(groups), reply_markup=groups_markup(groups))


@router.message(F.text == "✏️ Qiziqishlarim")
async def edit_start(m: Message, state: FSMContext):
    u = await db.get_user(m.from_user.id)
    if not u or not u["registered"]:
        return await m.answer("Avval /start orqali ro'yxatdan o'ting.")
    await state.set_state(Edit.interests)
    await m.answer(f"Hozirgi qiziqishlar: <i>{e(u['interests'])}</i>\n\nYangisini vergul bilan yozing:")


@router.message(Edit.interests, F.text)
async def edit_save(m: Message, state: FSMContext):
    if m.text in MAIN_BTNS:
        await state.clear()
        return
    fm, new = await apply_fields(m.bot, m.from_user.id, m.text)
    await db.run("UPDATE users SET interests=?, fields=? WHERE tg_id=?", (m.text.strip()[:300], ",".join(fm), m.from_user.id))
    await state.clear()
    u = await db.get_user(m.from_user.id)
    groups = await db.assign_groups(u, fm)
    await notify_new_fields(m.bot, new)
    await m.answer("✅ Yangilandi!\n\n" + await groups_text(groups), reply_markup=groups_markup(groups))


@router.message(F.text == "🔎 Qidiruv")
async def search_start(m: Message, state: FSMContext):
    await state.set_state(Search.query)
    await m.answer("🔎 Qiziqish yoki guruh nomini yozing (masalan: <i>python</i>):")


@router.message(Search.query, F.text)
async def search_do(m: Message, state: FSMContext):
    if m.text in MAIN_BTNS:
        await state.clear()
        return
    await state.clear()
    like = f"%{m.text.strip()}%"
    people = await db.q(
        "SELECT * FROM users WHERE registered=1 AND banned=0 AND tg_id!=? AND (interests LIKE ? OR school LIKE ?) LIMIT 10",
        (m.from_user.id, like, like),
    )
    groups = await db.q("SELECT * FROM groups WHERE name LIKE ? LIMIT 10", (like,))
    text = f"🔎 <b>«{e(m.text)}»</b> bo'yicha natijalar\n"
    if groups:
        text += "\n<b>Guruhlar:</b>\n" + "\n".join(f"• {e(g['name'])}" for g in groups)
    if people:
        text += "\n\n<b>Odamlar:</b>\n" + "\n".join(
            f"• {e(p['first_name'])} — {p['grade']}-sinf, {e(p['interests'][:50])}"
            + (f" (@{p['username']})" if p["username"] else "")
            for p in people
        )
    if not groups and not people:
        text += "\nHech narsa topilmadi 😕"
    await m.answer(text, reply_markup=groups_markup(groups))


@router.message(F.text == "ℹ️ Yordam")
@router.message(Command("help"))
async def help_(m: Message):
    await m.answer(
        "ℹ️ <b>Yordam</b>\n\n👤 Profilim — ma'lumotlaringiz\n👥 Guruhlarim — sinf/soha/maktab guruhlari\n"
        "🔎 Qidiruv — qiziqish bo'yicha odam va guruh izlash\n✏️ Qiziqishlarim — qiziqishlarni yangilash\n\n"
        "Savol bo'lsa shu yerga yozing — administrator javob beradi 💬"
    )


@router.message(Command("id"))
@router.message(Command("admin"))
async def my_id(m: Message):
    """Admin bo'lmaganlarga ID ni ko'rsatadi (ADMIN_IDS ni to'g'ri yozish uchun)."""
    await m.answer(
        f"🆔 Sizning Telegram ID: <code>{m.from_user.id}</code>\n\n"
        f"⚙️ Serverda yuklangan adminlar soni: {len(config.ADMIN_IDS)}\n\n"
        "⛔ Siz hozircha admin emassiz. Admin bo'lish uchun shu raqamni hosting sozlamalaridagi "
        "<b>ADMIN_IDS</b> ga yozing va botni qayta ishga tushiring (Deploy)."
    )


@router.message(F.text & ~F.text.startswith("/"))
async def fallback(m: Message):
    u = await db.get_user(m.from_user.id)
    name = e(u["first_name"] or m.from_user.full_name) if u else e(m.from_user.full_name)
    for admin_id in config.ADMIN_IDS:
        try:
            await m.bot.send_message(
                admin_id, f"💬 <b>{name}</b> (<code>{m.from_user.id}</code>):\n{e(m.text)}",
                reply_markup=ikb([[("✉️ Javob yozish", f"a:reply:{m.from_user.id}")]]),
            )
        except Exception:
            pass
    await m.answer("💬 Xabaringiz administratorga yuborildi. Menyudan foydalaning 👇", reply_markup=main_menu())
