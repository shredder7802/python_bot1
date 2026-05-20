# ========== TELEGRAM-БОТ: ПЛАНИРОВЩИК СОБЫТИЙ ==========
# main.py — весь основной код и функции
# base.py — база данных (не менять)
# schedule.py — напоминания (не менять)
# config.py — только TOKEN

import asyncio
import logging
from datetime import datetime, timedelta

import config
from aiogram import Bot, Dispatcher
from aiogram.client.session.aiohttp import AiohttpSession
from aiogram.exceptions import TelegramBadRequest
from aiogram.types import (
    CallbackQuery,
    InlineKeyboardButton,
    InlineKeyboardMarkup,
    Message,
    ReplyKeyboardRemove,
)

# --- Время: на VPS часто UTC, ты вводишь время по Красноярску (UTC+7) ---
# К «сейчас» на сервере прибавляем 7 часов, иначе «через 10 мин» станет «через 14 ч»
FMT = "%d.%m.%Y %H:%M"
HOURS_SHIFT = 7


def now_local():
    """Сейчас по Красноярску (если сервер в UTC)."""
    return datetime.now() + timedelta(hours=HOURS_SHIFT)


def parse_local_datetime(text):
    """Строка «28.05.2026 15:30» → datetime."""
    return datetime.strptime(text.strip(), FMT)


# base.py и schedule.py берут FMT и функции из config — подставляем их туда
config.FMT = FMT
config.now_local = now_local
config.parse_local_datetime = parse_local_datetime

from base import SQL
from schedule import reminder_scheduler

# --- Запуск бота ---
session = AiohttpSession(proxy="http://proxy.server:3128")
bot = Bot(token=config.TOKEN, session=session)
db = SQL("db.db")
dp = Dispatcher()
logging.basicConfig(level=logging.INFO)

# --- Статусы пользователя (поле users.status) ---
# 1 — в меню
# 2 — вводит название
# 3 — вводит комментарий
# 4 — вводит дату/время
# 5 — выбирает частоту напоминания
# 6 — подтверждает событие (Да/Нет)
# 7 — выбирает «за сколько напомнить»
# 8 — идёт сохранение (чтобы не было дублей при двойном нажатии)

ST_MENU = 1
ST_NAME = 2
ST_COMMENT = 3
ST_TIME = 4
ST_FREQ = 5
ST_CONFIRM = 6
ST_ADVANCE = 7
ST_SAVING = 8

# --- Клавиатуры (кнопки под сообщением) ---

kb_menu = InlineKeyboardMarkup(inline_keyboard=[
    [InlineKeyboardButton(text="➕ Добавить событие", callback_data="new_event")],
    [InlineKeyboardButton(text="📋 Мои события", callback_data="my_events")],
])

kb_frequency = InlineKeyboardMarkup(inline_keyboard=[
    [InlineKeyboardButton(text="Один раз", callback_data="freq_once")],
    [InlineKeyboardButton(text="Каждый день", callback_data="freq_daily")],
    [InlineKeyboardButton(text="Каждую неделю", callback_data="freq_weekly")],
    [InlineKeyboardButton(text="Каждый месяц", callback_data="freq_monthly")],
    [InlineKeyboardButton(text="⚙️ По умолчанию (за день и час)", callback_data="freq_default")],
])

kb_confirm = InlineKeyboardMarkup(inline_keyboard=[
    [InlineKeyboardButton(text="✅ Да", callback_data="confirm_yes")],
    [InlineKeyboardButton(text="❌ Нет", callback_data="confirm_no")],
])

# «За сколько напомнить» — разные кнопки для разной частоты
kb_adv_once = InlineKeyboardMarkup(inline_keyboard=[
    [InlineKeyboardButton(text="⏰ За 5 минут", callback_data="adv_5m")],
    [InlineKeyboardButton(text="⏰ За 10 минут", callback_data="adv_10m")],
    [InlineKeyboardButton(text="⏰ За 30 минут", callback_data="adv_30m")],
    [InlineKeyboardButton(text="🔔 В момент события", callback_data="adv_0m")],
])
kb_adv_daily = InlineKeyboardMarkup(inline_keyboard=[
    [InlineKeyboardButton(text="⏰ За 1 час", callback_data="adv_60m")],
    [InlineKeyboardButton(text="⏰ За 3 часа", callback_data="adv_180m")],
    [InlineKeyboardButton(text="⏰ За 6 часов", callback_data="adv_360m")],
    [InlineKeyboardButton(text="🔔 В момент события", callback_data="adv_0m")],
])
kb_adv_weekly = InlineKeyboardMarkup(inline_keyboard=[
    [InlineKeyboardButton(text="📅 За 1 день", callback_data="adv_1440m")],
    [InlineKeyboardButton(text="📅 За 3 дня", callback_data="adv_4320m")],
    [InlineKeyboardButton(text="🔔 В момент события", callback_data="adv_0m")],
])
kb_adv_monthly = InlineKeyboardMarkup(inline_keyboard=[
    [InlineKeyboardButton(text="📅 За 1 день", callback_data="adv_1440m")],
    [InlineKeyboardButton(text="📅 За 3 дня", callback_data="adv_4320m")],
    [InlineKeyboardButton(text="📅 За 1 неделю", callback_data="adv_10080m")],
    [InlineKeyboardButton(text="🔔 В момент события", callback_data="adv_0m")],
])

KB_BY_FREQ = {
    "once": kb_adv_once,
    "daily": kb_adv_daily,
    "weekly": kb_adv_weekly,
    "monthly": kb_adv_monthly,
}

# callback кнопки → (код частоты, подпись) или (минуты до события, подпись)
FREQ_MAP = {
    "freq_once": ("once", "Один раз"),
    "freq_daily": ("daily", "Каждый день"),
    "freq_weekly": ("weekly", "Каждую неделю"),
    "freq_monthly": ("monthly", "Каждый месяц"),
}
ADVANCE_MAP = {
    "adv_0m": (0, "В момент события"),
    "adv_5m": (5, "За 5 минут"),
    "adv_10m": (10, "За 10 минут"),
    "adv_30m": (30, "За 30 минут"),
    "adv_60m": (60, "За 1 час"),
    "adv_180m": (180, "За 3 часа"),
    "adv_360m": (360, "За 6 часов"),
    "adv_1440m": (1440, "За 1 день"),
    "adv_4320m": (4320, "За 3 дня"),
    "adv_10080m": (10080, "За 1 неделю"),
}
FREQ_TITLE = {v[0]: v[1] for v in FREQ_MAP.values()}

# Кнопки главного меню — только когда status = 1 (меню)
MENU_BUTTONS = {"new_event", "my_events"}


# ========== ВСПОМОГАТЕЛЬНЫЕ ФУНКЦИИ ==========

async def busy_alert(call, text="Сейчас нельзя: сначала закончи текущий шаг."):
    """Сообщение, если нажали кнопку не на том этапе."""
    await call.answer(text, show_alert=True)


def need_status(user_id, expected):
    """Проверка: пользователь на нужном шаге?"""
    return db.get_field(user_id, "status") == expected

def ensure_user(user_id):
    """Если пользователь новый — добавляем строку в users."""
    if not db.user_exist(user_id):
        db.add_user(user_id)


def clear_draft(user_id):
    """Очищаем черновик события в users и возвращаем в меню."""
    db.update_field(user_id, "status", ST_MENU)
    db.update_field(user_id, "name", "")
    db.update_field(user_id, "comment", "")
    db.update_field(user_id, "event_time", "")
    db.update_field(user_id, "type_remind", "")


def comment_text(comment):
    return "Нет" if comment == "-" else comment


def format_time_left(event_dt, now):
    """Текст «через 10 мин» для списка событий."""
    minutes = int((event_dt - now).total_seconds() // 60)
    if minutes <= 0:
        return "уже прошло"
    if minutes < 60:
        return f"через {minutes} мин"
    if minutes < 1440:
        return f"через {minutes // 60} ч {minutes % 60} мин"
    return f"через {minutes // 1440} дн {(minutes % 1440) // 60} ч"


async def safe_delete(msg):
    """Удалить сообщение; если уже удалено — не падать."""
    try:
        await msg.delete()
    except TelegramBadRequest:
        pass


def save_reminders(event_id, event_dt, type_remind):
    """Записывает в reminders, когда бот должен напомнить."""
    if type_remind == "default":
        # Два напоминания: за сутки и за час
        day_before = (event_dt - timedelta(minutes=1440)).strftime(FMT)
        hour_before = (event_dt - timedelta(minutes=60)).strftime(FMT)
        db.add_reminder(event_id, day_before, "once")
        db.add_reminder(event_id, hour_before, "once")
        return

    # type_remind вида "daily_60" = частота + минут до события
    parts = type_remind.split("_")
    freq = parts[0]
    minutes_before = int(parts[1]) if len(parts) > 1 else 0
    remind_at = (event_dt - timedelta(minutes=minutes_before)).strftime(FMT)
    db.add_reminder(event_id, remind_at, freq)


async def send_confirm(call, user_id, extra_lines=""):
    """Показывает итог перед сохранением."""
    name = db.get_field(user_id, "name")
    comment = db.get_field(user_id, "comment")
    time_str = db.get_field(user_id, "event_time")
    ev_dt = parse_local_datetime(time_str)

    text = (
        f"📝 Подтверди событие:\n\n"
        f"📌 Название: {name}\n"
        f"💬 Комментарий: {comment_text(comment)}\n"
        f"🕒 Время: {ev_dt.strftime(FMT)}\n"
        f"{extra_lines}\n"
        f"Всё верно?"
    )
    await call.message.answer(text, reply_markup=kb_confirm)


# ========== ТЕКСТОВЫЕ СООБЩЕНИЯ ==========

@dp.message()
async def on_message(message: Message):
    user_id = message.from_user.id
    ensure_user(user_id)

    # Команда /start
    if message.text == "/start":
        db.update_field(user_id, "status", ST_MENU)
        await message.answer("Главное меню", reply_markup=ReplyKeyboardRemove())
        await message.answer("Выбери действие:", reply_markup=kb_menu)
        return

    status = db.get_field(user_id, "status") or ST_MENU

    # Пока создаётся событие — только ответы текстом на текущий вопрос
    if status in (ST_FREQ, ST_ADVANCE, ST_CONFIRM, ST_SAVING):
        await message.answer(
            "Сейчас нужно нажать кнопку под сообщением, а не писать текст."
        )
        return

    if status == ST_MENU and message.text != "/start":
        await message.answer("Выбери действие кнопками:", reply_markup=kb_menu)
        return

    # Шаг 1: название
    if status == ST_NAME:
        db.update_field(user_id, "name", message.text)
        db.update_field(user_id, "status", ST_COMMENT)
        await message.answer('Комментарий (или "-" если не нужен):')
        return

    # Шаг 2: комментарий
    if status == ST_COMMENT:
        db.update_field(user_id, "comment", message.text)
        db.update_field(user_id, "status", ST_TIME)
        await message.answer("Дата и время: ДД.ММ.ГГГГ ЧЧ:ММ\nПример: 28.05.2026 15:30")
        return

    # Шаг 3: дата и время
    if status == ST_TIME:
        try:
            event_dt = parse_local_datetime(message.text)
            now = now_local()
            if event_dt <= now:
                await message.answer(
                    f"Нельзя в прошлом!\n"
                    f"Ты ввёл: {event_dt.strftime(FMT)}\n"
                    f"Сейчас: {now.strftime(FMT)}"
                )
                return
            db.update_field(user_id, "event_time", event_dt.strftime(FMT))
            db.update_field(user_id, "status", ST_FREQ)
            await message.answer("Как часто напоминать?", reply_markup=kb_frequency)
        except ValueError:
            await message.answer("Неверный формат. Пример: 21.05.2026 19:30")


# ========== НАЖАТИЯ НА КНОПКИ ==========

@dp.callback_query()
async def on_callback(call: CallbackQuery):
    user_id = call.from_user.id
    ensure_user(user_id)
    await call.answer()
    data = call.data
    status = db.get_field(user_id, "status") or ST_MENU

    # Главное меню — только из статуса «меню»
    if data in MENU_BUTTONS and status != ST_MENU:
        await busy_alert(call, "Сейчас ты создаёшь событие. Сначала закончи его или нажми ❌ Нет.")
        return

    # --- Главное меню ---
    if data == "new_event":
        clear_draft(user_id)
        db.update_field(user_id, "status", ST_NAME)
        await call.message.answer("Название события:")
        return

    if data == "my_events":
        events = db.get_user_events(user_id)
        if not events:
            await call.message.answer("Событий пока нет.", reply_markup=kb_menu)
            return
        now = now_local()
        for eid, name, ev_time, created in events:
            try:
                row = db.get_event_by_id(eid)
                comment = row[2] if row else "-"
                ev_dt = parse_local_datetime(ev_time)
                left = format_time_left(ev_dt, now)
                text = (
                    f"📌 {name}\n"
                    f"💬 {comment_text(comment)}\n"
                    f"🕒 {ev_time}\n"
                    f"⏳ Начнётся: {left}\n"
                    f"📅 Добавлено: {created}"
                )
                kb = InlineKeyboardMarkup(inline_keyboard=[
                    [InlineKeyboardButton(text="🗑 Удалить", callback_data=f"del_{eid}")]
                ])
                await call.message.answer(text, reply_markup=kb)
            except ValueError:
                await call.message.answer(f"📌 {name} — {ev_time}")
        await call.message.answer("Главное меню:", reply_markup=kb_menu)
        return

    if data.startswith("del_"):
        if status != ST_MENU:
            await busy_alert(call)
            return
        eid = int(data.split("_")[1])
        row = db.get_event_by_id(eid)
        if row:
            db.delete_event(eid)
            await call.message.edit_text(f"🗑 Удалено: «{row[1]}»")
        else:
            await call.answer("Не найдено", show_alert=True)
        return

    # --- Создание события: частота и «за сколько» ---
    if data in FREQ_MAP:
        if not need_status(user_id, ST_FREQ):
            await busy_alert(call)
            return
        freq_code, freq_title = FREQ_MAP[data]
        db.update_field(user_id, "type_remind", freq_code)
        db.update_field(user_id, "status", ST_ADVANCE)
        await call.message.answer(
            f"Выбрано: {freq_title}\nЗа сколько напомнить?",
            reply_markup=KB_BY_FREQ[freq_code],
        )
        return

    if data == "freq_default":
        if not need_status(user_id, ST_FREQ):
            await busy_alert(call)
            return
        db.update_field(user_id, "type_remind", "default")
        db.update_field(user_id, "status", ST_CONFIRM)
        await send_confirm(
            call, user_id,
            extra_lines="🔔 Напоминание: за 1 день и за 1 час до события",
        )
        return

    if data in ADVANCE_MAP:
        if not need_status(user_id, ST_ADVANCE):
            await busy_alert(call)
            return
        minutes, adv_title = ADVANCE_MAP[data]
        freq = db.get_field(user_id, "type_remind")
        db.update_field(user_id, "type_remind", f"{freq}_{minutes}")
        db.update_field(user_id, "status", ST_CONFIRM)
        repeat = "Один раз" if freq == "once" else f"🔁 {FREQ_TITLE.get(freq, freq)}"
        await send_confirm(
            call, user_id,
            extra_lines=f"🔁 Повтор: {repeat}\n🔔 Напоминание: {adv_title}",
        )
        return

    # --- Подтверждение ---
    if data == "confirm_yes":
        if not need_status(user_id, ST_CONFIRM):
            await busy_alert(call, "Подтверждение уже обработано или шаг другой.")
            return

        db.update_field(user_id, "status", ST_SAVING)
        name = db.get_field(user_id, "name")
        comment = db.get_field(user_id, "comment")
        time_str = db.get_field(user_id, "event_time")
        remind_type = db.get_field(user_id, "type_remind")

        if not time_str:
            clear_draft(user_id)
            await call.message.answer("Нет времени события. Создай заново.")
            return

        try:
            event_dt = parse_local_datetime(time_str)
            event_id = db.add_event(user_id, name, comment, time_str)
            save_reminders(event_id, event_dt, remind_type)
            clear_draft(user_id)
            await safe_delete(call.message)
            left = format_time_left(event_dt, now_local())
            await call.message.answer(
                f"✅ Сохранено: «{name}»\n"
                f"💬 Комментарий: {comment_text(comment)}\n"
                f"🕒 Начало: {time_str}\n"
                f"⏳ {left}",
                reply_markup=kb_menu,
            )
        except Exception:
            db.update_field(user_id, "status", ST_CONFIRM)
            await call.message.answer("Ошибка сохранения. Попробуй ещё раз.")
        return

    if data == "confirm_no":
        if not need_status(user_id, ST_CONFIRM):
            await busy_alert(call)
            return
        clear_draft(user_id)
        await safe_delete(call.message)
        await call.message.answer("Отменено.", reply_markup=kb_menu)
        return


# ========== СТАРТ ПРОГРАММЫ ==========

async def main():
    asyncio.create_task(reminder_scheduler(bot, db))
    await dp.start_polling(bot)


if __name__ == "__main__":
    asyncio.run(main())
