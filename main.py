from aiogram.client.session.aiohttp import AiohttpSession

import config
import logging
import asyncio
import aiohttp
from bs4 import BeautifulSoup
from aiogram import Bot, Dispatcher
from aiogram.types import InlineKeyboardMarkup, InlineKeyboardButton
from base import SQL
from apscheduler.schedulers.asyncio import AsyncIOScheduler

session = AiohttpSession(proxy='socks5://1.0.154.228:4145')
bot = Bot(token=config.TOKEN, session=session)


db = SQL('db.db')  # соединение с БД
dp = Dispatcher()

logging.basicConfig(level=logging.INFO)

HOROSCOPE_URLS = {
    "taurus":  "https://horoscopes.rambler.ru/taurus/",
    "aries":   "https://horoscopes.rambler.ru/aries/",
    "gemini":  "https://horoscopes.rambler.ru/gemini/",
    "cancer":  "https://horoscopes.rambler.ru/cancer/",
    "leo":     "https://horoscopes.rambler.ru/leo/",
    "virgo":   "https://horoscopes.rambler.ru/virgo/",
    "lidra":   "https://horoscopes.rambler.ru/libra/",
    "scorpio": "https://horoscopes.rambler.ru/scorpio/",
    "saget":   "https://horoscopes.rambler.ru/sagittarius/",
    "capri":   "https://horoscopes.rambler.ru/capricorn/",
    "aqu":     "https://horoscopes.rambler.ru/aquarius/",
    "pises":   "https://horoscopes.rambler.ru/pisces/",
}

PERIOD_SUFFIX = {
    "today":    "",
    "tomorrow": "tomorrow/",
    "weekly":   "weekly/",
}

def period_keyboard(sign: str) -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="Сегодня",  callback_data=f"hor_{sign}_today")],
        [InlineKeyboardButton(text="Завтра",   callback_data=f"hor_{sign}_tomorrow")],
        [InlineKeyboardButton(text="На неделю", callback_data=f"hor_{sign}_weekly")],
    ])

async def get_horoscope(sign: str, period: str = "today") -> str:
    base_url = HOROSCOPE_URLS.get(sign)
    if not base_url:
        return "Гороскоп для этого знака не найден."
    url = base_url + PERIOD_SUFFIX.get(period, "")
    try:
        async with aiohttp.ClientSession() as http_session:
            async with http_session.get(url, timeout=aiohttp.ClientTimeout(total=10)) as resp:
                html = await resp.text()
        soup = BeautifulSoup(html, "html.parser")
        paragraphs = soup.find_all("p")
        for p in paragraphs:
            text = p.get_text(strip=True)
            if len(text) > 50:
                return text
        return "Не удалось получить гороскоп."
    except Exception as e:
        return f"Ошибка при получении гороскопа: {e}"

#inline клавиатура
buttons2 = [
        [InlineKeyboardButton(text="Да", callback_data="yes")],
        [InlineKeyboardButton(text="Нет", callback_data="no")]
    ]
kb2 = InlineKeyboardMarkup(inline_keyboard=buttons2)

kb_main = InlineKeyboardMarkup(inline_keyboard=[
    [InlineKeyboardButton(text="Гороскоп", callback_data="zod")],
    [InlineKeyboardButton(text="Узнать свой знак зодиака и стихию", callback_data="st")],
    [InlineKeyboardButton(text="Посмотреть свой знак зодиака и стихию", callback_data="stu")],
    [InlineKeyboardButton(text="🔔 Ежедневная рассылка", callback_data="notify_toggle")],
])

kb = InlineKeyboardMarkup(inline_keyboard=[
    [InlineKeyboardButton(text="Стрелец", callback_data="saget")],
    [InlineKeyboardButton(text="Скорпион", callback_data="scorpio")],
    [InlineKeyboardButton(text="Телец", callback_data="taurus")],
    [InlineKeyboardButton(text="Дева", callback_data="virgo")],
    [InlineKeyboardButton(text="Лев", callback_data="leo")],
    [InlineKeyboardButton(text="Весы", callback_data="lidra")],
    [InlineKeyboardButton(text="Близнецы", callback_data="gemini")],
    [InlineKeyboardButton(text="Рыбы", callback_data="pises")],
    [InlineKeyboardButton(text="Овен", callback_data="aries")],
    [InlineKeyboardButton(text="Рак", callback_data="cancer")],
    [InlineKeyboardButton(text="Козерог", callback_data="capri")],
    [InlineKeyboardButton(text="Водолей", callback_data="aqu")],
])

#когда пользователь написал сообщение
@dp.message()
async def start(message):
    id = message.from_user.id
    if not db.user_exist(id):
        db.add_user(id)
    status = db.get_field("users", id, "status")

    if status == 0:
        await message.answer("Главное меню:", reply_markup=kb_main)

    if status == 3:
        day = message.text
        if not day.isdigit():
            await message.answer("Введи числом!")
            return
        db.update_field("users", id, "status", 4)
        await message.answer("Напишите месяц своего рождения. Пример: 4")

    if status == 4:
        month = message.text
        if not month.isdigit():
            await message.answer("Введи числом!")
            return
        db.update_field("users", id, "mes", month)
        db.update_field("users", id, "status", 5)
        month = int(month)
        day = int(db.get_field("users", id, "day"))
        if (month == 1 and day >= 20) or (month == 2 and day <= 18):
            goro, st = "Водолей", "Воздух"
        elif (month == 2 and day >= 19) or (month == 3 and day <= 20):
            goro, st = "Рыбы", "Вода"
        elif (month == 3 and day >= 21) or (month == 4 and day <= 19):
            goro, st = "Овен", "Огонь"
        elif (month == 4 and day >= 20) or (month == 5 and day <= 20):
            goro, st = "Телец", "Земля"
        elif (month == 5 and day >= 21) or (month == 6 and day <= 20):
            goro, st = "Близнецы", "Воздух"
        elif (month == 6 and day >= 21) or (month == 7 and day <= 22):
            goro, st = "Рак", "Вода"
        elif (month == 7 and day >= 23) or (month == 8 and day <= 22):
            goro, st = "Лев", "Огонь"
        elif (month == 8 and day >= 23) or (month == 9 and day <= 22):
            goro, st = "Дева", "Земля"
        elif (month == 9 and day >= 23) or (month == 10 and day <= 22):
            goro, st = "Весы", "Воздух"
        elif (month == 10 and day >= 23) or (month == 11 and day <= 21):
            goro, st = "Скорпион", "Вода"
        elif (month == 11 and day >= 22) or (month == 12 and day <= 21):
            goro, st = "Стрелец", "Огонь"
        else:
            goro, st = "Козерог", "Земля"
        await message.answer(f"Ваш знак зодиака: {goro}. Ваша стихия: {st}")
        db.update_field("users", id, "zod", goro)  # сохраняем знак для рассылки
        db.update_field("users", id, "status", 0)


#когда пользователь нажал на inline кнопку
@dp.callback_query()
async def start_call(call):
    id = call.from_user.id
    if not db.user_exist(id):
        db.add_user(id)
    status = db.get_field("users", id, "status")

    if call.data == "stu":
        zod = db.get_field("users", id, "zod")
        st = db.get_field("users", id, "st")
        if not zod:
            await call.answer("Вы не сохраняли знак зодиака и стихию", show_alert=True)
        else:
            await call.answer(f"Ваш знак: {zod}. Стихия: {st}", show_alert=True)

    elif call.data == "zod":
        await call.message.edit_text("Выберите ваш знак зодиака:", reply_markup=kb)
        await call.answer()

    elif call.data in HOROSCOPE_URLS:
        # сохраняем выбранный знак для рассылки
        db.update_field("users", id, "zod", call.data)
        await call.message.edit_text("Выберите период:", reply_markup=period_keyboard(call.data))
        await call.answer()

    elif call.data.startswith("hor_"):
        _, sign, period = call.data.split("_", 2)
        period_labels = {"today": "сегодня", "tomorrow": "завтра", "weekly": "на неделю"}
        horoscope = await get_horoscope(sign, period)
        await call.message.answer(f"Гороскоп {period_labels.get(period, '')}:\n\n{horoscope}")
        await call.answer()

    elif call.data == "st":
        db.update_field("users", id, "status", 3)
        await call.message.answer("Напишите день своего рождения. Пример: 21")
        await call.answer()

    elif call.data == "notify_toggle":
        current = db.get_field("users", id, "notify") or 0
        new_val = 0 if current else 1
        db.update_field("users", id, "notify", new_val)
        if new_val:
            await call.answer("🔔 Рассылка включена! Гороскоп будет приходить каждый день в 8:00", show_alert=True)
        else:
            await call.answer("🔕 Рассылка отключена", show_alert=True)

    else:
        await call.answer()

async def send_daily_horoscope():
    """Отправляет гороскоп на сегодня всем подписанным пользователям"""
    users = db.get_notify_users()
    for user_id, sign in users:
        try:
            horoscope = await get_horoscope(sign)
            await bot.send_message(user_id, f"🌟 Ваш гороскоп на сегодня:\n\n{horoscope}")
        except Exception as e:
            logging.warning(f"Не удалось отправить рассылку пользователю {user_id}: {e}")

async def main():
    scheduler = AsyncIOScheduler(timezone="Europe/Moscow")
    scheduler.add_job(send_daily_horoscope, "cron", hour=8, minute=0)
    scheduler.start()
    await dp.start_polling(bot)

if __name__ == "__main__":
    asyncio.run(main())
