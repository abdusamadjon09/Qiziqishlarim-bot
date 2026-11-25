import os
import re

from dotenv import load_dotenv

load_dotenv()

BOT_TOKEN = os.getenv("BOT_TOKEN", "").strip()

# Admin ID lar: ADMIN_IDS (yoki ADMIN_ID / ADMINS) — raqamlar istalgan ajratgich bilan yozilishi mumkin
_raw = os.getenv("ADMIN_IDS") or os.getenv("ADMIN_ID") or os.getenv("ADMINS") or ""
ADMIN_IDS = {int(x) for x in re.findall(r"\d+", _raw)}

# Zaxira: muhit o'zgaruvchisi ishlamasa ham shu ID lar admin bo'ladi (o'zingizning Telegram ID ingiz)
ADMIN_IDS |= {8687741180}

DB_PATH = os.getenv("DB_PATH", "data/bot.db")
PORT = int(os.getenv("PORT", "8080"))
