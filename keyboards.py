from aiogram.types import InlineKeyboardButton, InlineKeyboardMarkup, KeyboardButton, ReplyKeyboardMarkup

REGIONS = [
    "Toshkent shahri", "Toshkent viloyati", "Samarqand", "Buxoro", "Andijon", "Farg'ona", "Namangan",
    "Qashqadaryo", "Surxondaryo", "Xorazm", "Navoiy", "Jizzax", "Sirdaryo", "Qoraqalpog'iston",
]

MAIN_BTNS = ["👤 Profilim", "👥 Guruhlarim", "🔎 Qidiruv", "✏️ Qiziqishlarim", "ℹ️ Yordam"]


def main_menu():
    return ReplyKeyboardMarkup(
        keyboard=[
            [KeyboardButton(text="👤 Profilim"), KeyboardButton(text="👥 Guruhlarim")],
            [KeyboardButton(text="🔎 Qidiruv"), KeyboardButton(text="✏️ Qiziqishlarim")],
            [KeyboardButton(text="ℹ️ Yordam")],
        ],
        resize_keyboard=True,
    )


def ikb(rows):
    """rows: [[(text, data)], ...]; data 'http' bilan boshlansa URL tugma."""
    out = []
    for row in rows:
        line = []
        for t in row:
            if t[1].startswith("http"):
                line.append(InlineKeyboardButton(text=t[0], url=t[1]))
            else:
                line.append(InlineKeyboardButton(text=t[0], callback_data=t[1]))
        out.append(line)
    return InlineKeyboardMarkup(inline_keyboard=out)


def region_kb():
    rows, row = [], []
    for i, r in enumerate(REGIONS):
        row.append((r, f"reg:r:{i}"))
        if len(row) == 2:
            rows.append(row)
            row = []
    if row:
        rows.append(row)
    return ikb(rows)


def grade_kb():
    rows = [[(f"{n}", f"reg:g:{n}") for n in range(s, min(s + 4, 12))] for s in range(1, 12, 4)]
    return ikb(rows)
