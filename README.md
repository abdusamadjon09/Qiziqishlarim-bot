# 🌟 Qiziqishlarim PRO — Telegram bot

Saytning Telegram-bot varianti: foydalanuvchi ro'yxatdan o'tadi, bot uni **sinf**, **soha** (qiziqish) va **maktab**
bo'yicha guruhlarga avtomatik joylaydi. Admin panel orqali hammasini boshqarish mumkin. (Al Ustoz bo'limi olib tashlangan.)

## Imkoniyatlar
**Foydalanuvchi:** ro'yxatdan o'tish (ism, familiya, viloyat, tuman, maktab, sinf, qiziqishlar), profil, guruhlarim,
qiziqish/guruh bo'yicha qidiruv, qiziqishlarni yangilash (guruhlar qayta taqsimlanadi), adminga savol yozish.

**Admin (`/admin`):** statistika · foydalanuvchilar (kartochka, bloklash, o'chirish) · guruhlar (a'zolar, qidirish) ·
sinflar va sohalar bo'yicha ko'rinish · foydalanuvchi xabarlari va unga javob yozish · hammaga yoki guruhga xabar
tarqatish · yangi guruh yaratish · CSV eksport · yangi a'zo haqida bildirishnoma.

## Ishga tushirish
```bash
pip install -r requirements.txt
cp .env.example .env     # BOT_TOKEN va ADMIN_IDS ni yozing
python bot.py
```

## Telegram guruhlarini ulash
Bot Telegramda guruh **yarata olmaydi**, shuning uchun: guruhni o'zingiz yarating → botni **admin** qiling
(havola yaratish huquqi bilan) → guruhda `/bind <guruh_ID>` yozing (ID ni admin paneldagi guruh sahifasidan oling).
Shundan so'ng a'zolar ro'yxatdan o'tganda o'z guruhlarining havolasini oladi.

## Hosting (24/7)
- **Render**: `render.yaml` tayyor. Diqqat: bepul tarifda disk o'chib ketadi (SQLite yo'qoladi) — Disk (`/var/data`) ulang yoki Railway/VPS ishlating.
- **Railway/VPS**: `python bot.py`, `DB_PATH` ni doimiy volume'ga yo'naltiring.

## Maxfiylik
Bot faqat o'ziga yozilgan xabarlarni saqlaydi (foydalanuvchining boshqa shaxsiy chatlarini ko'ra olmaydi — Telegram buni taqiqlaydi).
Foydalanuvchiga bu haqda `/start` da ogohlantiriladi.

## Fayllar tuzilishi (hammasi bitta papkada)
`bot.py` (asosiy fayl) · `config.py` · `db.py` · `fields.py` · `keyboards.py` · `middleware.py` ·
`user_handlers.py` · `admin_handlers.py` · `requirements.txt` · `Procfile` · `render.yaml` ·
`env.example` (GitHub'da nomini `.env.example` qiling) · `gitignore.txt` (nomini `.gitignore` qiling)
