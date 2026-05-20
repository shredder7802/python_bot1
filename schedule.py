# ========== ФОНОВЫЙ ПЛАНИРОВЩИК НАПОМИНАНИЙ ==========
# Каждую минуту смотрит таблицу reminders и шлёт сообщения в Telegram.

import asyncio
from datetime import timedelta

from dateutil.relativedelta import relativedelta
from aiogram import Bot

from config import FMT, now_local, parse_local_datetime

# На сколько сдвинуть дату для повторяющихся событий
REPEAT_STEP = {
    "daily": lambda dt: dt + timedelta(days=1),
    "weekly": lambda dt: dt + timedelta(weeks=1),
    "monthly": lambda dt: dt + relativedelta(months=1),
}


async def reminder_scheduler(bot: Bot, db):
    while True:
        try:
            now = now_local()
            rows = db.get_pending_reminders(now.strftime(FMT))

            for row in rows:
                rid, event_id, remind_at, rtype, name, comment, ev_time, user_id = row
                try:
                    remind_dt = parse_local_datetime(remind_at)
                    event_dt = parse_local_datetime(ev_time)

                    if now < remind_dt:
                        continue  # ещё рано напоминать

                    # Текст напоминания
                    desc = comment if comment and comment != "-" else "Без описания"
                    text = (
                        f"🔔 Напоминание!\n\n"
                        f"📌 {name}\n"
                        f"💬 {desc}\n"
                        f"🕒 Начало: {event_dt.strftime(FMT)}"
                    )
                    await bot.send_message(chat_id=user_id, text=text)
                    db.mark_sent(rid)

                    # Повтор: каждый день / неделю / месяц — создаём следующее событие
                    if rtype in REPEAT_STEP:
                        next_dt = REPEAT_STEP[rtype](event_dt)
                        next_str = next_dt.strftime(FMT)
                        new_id = db.add_event(user_id, name, comment, next_str)
                        db.add_reminder(new_id, next_str, rtype)

                except Exception as e:
                    print(f"Ошибка напоминания {rid}: {e}")

        except Exception as e:
            print(f"Ошибка планировщика: {e}")

        await asyncio.sleep(60)
