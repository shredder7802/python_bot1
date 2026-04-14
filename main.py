import config
import logging
import asyncio
from aiogram import Bot, Dispatcher, F
from base import SQL  # подключение класса SQL из файла base
from aiogram.types import ReplyKeyboardRemove, \
    ReplyKeyboardMarkup, KeyboardButton, \
    InlineKeyboardMarkup, InlineKeyboardButton
from datetime import datetime
from aiogram.client.session.aiohttp import AiohttpSession# для хостинга

session = AiohttpSession(proxy='http://proxy.server:3128') # в proxy указан прокси сервер pythonanywhere, он нужен для подключения
bot = Bot(token=config.TOKEN, session=session)

db = SQL('db.db')  # соединение с БД

dp = Dispatcher()

logging.basicConfig(level=logging.INFO)

#inline клавиатура
kb_menu = InlineKeyboardMarkup(inline_keyboard=[
    [InlineKeyboardButton(text="Добавить событие",callback_data="new_event")],
    [InlineKeyboardButton(text="Мои события", callback_data="my_events")]
])

kb_ = InlineKeyboardMarkup(inline_keyboard=[
    [InlineKeyboardButton(text="Добавить событие",callback_data="new_event")],
    [InlineKeyboardButton(text="Мои события", callback_data="my_events")],
    [InlineKeyboardButton(text="Помощь", callback_data="help")],
    [InlineKeyboardButton(text="Настройки", callback_data="settings")]
])

kb_yesorno = InlineKeyboardMarkup(inline_keyboard=[
    [InlineKeyboardButton(text="Да",callback_data="yes")],
    [InlineKeyboardButton(text="Нет", callback_data="no")]
])

Keyboard = ReplyKeyboardMarkup(
    keyboard=[
        [KeyboardButton(text="/start", callback_data="")]
             ],
        one_time_keyboard=True
)

buttons = [
        [KeyboardButton(text="/start")]
    ]
kb = ReplyKeyboardMarkup(keyboard=buttons, resize_keyboard=True, one_time_keyboard=True)

kb_events = InlineKeyboardMarkup(inline_keyboard=[
    [InlineKeyboardButton(text="Удалить событие",callback_data="delete_event")],
    [InlineKeyboardButton(text="Изменить время", callback_data="my_events")],
    [InlineKeyboardButton(text="помощь", callback_data="help")],
    [InlineKeyboardButton(text="Настройки", callback_data="settings")]
])
kb_comment = InlineKeyboardMarkup(inline_keyboard=[
    [InlineKeyboardButton(text="Открыть комментарий",callback_data="open_comment")]
    ])
#когда пользователь написал/start



#когда пользователь написал сообщение
@dp.message()
async def start(message):
    id = message.from_user.id
    if not db.user_exist(id):#если пользователя нет в бд
        db.add_user(id)#добавляем
    status = db.get_field("users", id, "status")  # получаем статус пользователя
    if message.text == "/start":
        db.update_field("users", id, "status", 1) #изменяем статус пользователя
        await message.answer("Главное меню: ", reply_markup=kb_menu)#отправка сообщения с клавиатурой
    if status == 2:
        name = message.text
        await message.answer('Введите комментарий к  событию, если он не нужен напишите: "-" ')
        db.update_field("users", id, "status", 3)
        db.update_field("users", id, "name", name)
        return
    if status == 3:
        comment = message.text
        await message.answer("Теперь укажи дату и время в формате ДД.ММ.ГГГГ ЧЧ:ММ")
        #if len(time) != 16:
           # await message.answer("Неправильно! Укажи дату и время в формате ДД.ММ.ГГГГ ЧЧ:ММ")

        db.update_field("users", id, "status", 4)
        db.update_field("users", id, "comment", comment)
        return
    if status == 4:
        time = message.text
        name = db.get_field("users", id, "name")
        comment = db.get_field("users", id, "comment")
        try:
            event_time = datetime.strptime(time, "%d.%m.%Y %H:%M")
            current_time = datetime.now()
            if event_time < current_time:
                await message.answer(f"Нельзя создать событие в прошлом!\nТы ввел: {event_time.strftime('%d.%m.%Y %H:%M')}\nСейчас: {current_time.strftime('%d.%m.%Y %H:%M')}\nПожалуйста, введи будущую дату и время")
                return
            db.update_field("users", id, "time", event_time)
            formatted_current_time = current_time.strftime("%d.%m.%Y %H:%M")
            db.update_field('events', id, 'current_time', formatted_current_time)
            await message.answer("Выбери как часто событие будет напоминаться: ")
            #await message.answer(f"Подтвердите событие: {name} Начнется: {event_time.strftime('%d.%m.%Y %H:%M')} Ваш комментарий: {comment}",reply_markup=kb_yesorno)
        except ValueError:
            await message.answer("Неправильный формат! Введи дату такого формата: 28.03.2026 15:30")

# когда пользователь нажал на inline кнопку
@dp.callback_query()
async def start_call(call):
    id = call.from_user.id
    if not db.user_exist(id):# если пользователя нет в бд
        db.add_user(id)# добавляем

    if call.data == "new_event":  # проверка нажатия на кнопку
        db.update_field("users", id, "status", 2)
        await call.message.answer("Введите название события: ")

    if call.data == "no":
        db.update_field("users", id, "status", 1)  # изменяем статус пользователя
        await call.answer("Ваше событие удалено!")
        await call.message.delete()

    if call.data == "yes":
        name = db.get_field("users", id, "name")
        comment = db.get_field("users", id, "comment")
        time = db.get_field("users", id, "time")
        db.add_event(name, comment, time, id)
          # изменяем статус пользователя
        await call.answer("Событие сохранено!")
        await call.message.delete()
        db.update_field("users", id, "status", 1)

    #await call.answer("Оповещение сверху")
    #await call.message.answer("Отправка сообщения")
    #await call.message.edit_text("Редактирование сообщения")
    #await call.message.delete()#удаление сообщения
    await bot.answer_callback_query(call.id)#ответ на запрос, чтобы бот не зависал

async def main():
    await dp.start_polling(bot)

if __name__ == "__main__":
    asyncio.run(main())
