from aiogram import BaseMiddleware

import config
import db


class LogMiddleware(BaseMiddleware):
    """Shaxsiy xabarlarni jurnalga yozadi va bloklanganlarni to'xtatadi."""

    async def __call__(self, handler, event, data):
        if event.chat.type == "private" and event.from_user:
            u = event.from_user
            await db.touch(u)
            row = await db.get_user(u.id)
            if row and row["banned"] and u.id not in config.ADMIN_IDS:
                await event.answer("🚫 Siz bloklangansiz.")
                return
            if u.id not in config.ADMIN_IDS:
                await db.log_msg(u.id, "in", event.text or event.caption or f"[{event.content_type}]")
        return await handler(event, data)
