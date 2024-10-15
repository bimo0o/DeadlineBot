import sqlite3
from aiogram import Bot, Dispatcher, types
from aiogram.types import ReplyKeyboardMarkup, KeyboardButton, InlineKeyboardMarkup, InlineKeyboardButton
from aiogram.filters import Command
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup
from aiogram.fsm.storage.memory import MemoryStorage
from aiogram import Router
from datetime import datetime, timedelta
import asyncio
import pytz

TOKEN = '8199760860:AAGGUDgYGANFPNuX2fRHA1YWwgpOfbXpg0c'
bot = Bot(token=TOKEN)
dp = Dispatcher(storage=MemoryStorage())

MAIN_MODERATOR_ID = 712016596

conn = sqlite3.connect('deadlines.db')
cursor = conn.cursor()

cursor.execute('''
    CREATE TABLE IF NOT EXISTS deadlines (
        id INTEGER PRIMARY KEY,
        description TEXT,
        deadline_date TEXT,
        notification_options TEXT,
        user_id INTEGER,
        is_personal INTEGER DEFAULT 0
    )
''')

cursor.execute('''
    CREATE TABLE IF NOT EXISTS moderators (
        id INTEGER PRIMARY KEY,
        username TEXT UNIQUE
    )
''')

cursor.execute('''
    CREATE TABLE IF NOT EXISTS user_settings (
        user_id INTEGER PRIMARY KEY,
        timezone TEXT DEFAULT 'UTC'
    )
''')

conn.commit()

class AddDeadline(StatesGroup):
    waiting_for_date = State()
    waiting_for_description = State()
    waiting_for_notifications = State()
    waiting_for_delete = State()
    waiting_for_edit = State()
    waiting_for_new_date = State()
    waiting_for_new_description = State()

router = Router()

@router.message(Command(commands=["start", "help"]))
async def send_welcome(message: types.Message):
    user_keyboard = ReplyKeyboardMarkup(keyboard=[
        [KeyboardButton(text="Показать дедлайны")],
        [KeyboardButton(text="Добавить дедлайн")],
        [KeyboardButton(text="Настройки уведомлений")],
        [KeyboardButton(text="Мои личные дедлайны")],
        [KeyboardButton(text="Настройка часового пояса")]
    ], resize_keyboard=True)

    if message.from_user.id == MAIN_MODERATOR_ID:
        moderator_keyboard = ReplyKeyboardMarkup(keyboard=[
            [KeyboardButton(text="Добавить модератора")],
            [KeyboardButton(text="Показать дедлайны")],
            [KeyboardButton(text="Добавить дедлайн")],
            [KeyboardButton(text="Удалить дедлайн")],
            [KeyboardButton(text="Редактировать дедлайн")],
            [KeyboardButton(text="Настройки уведомлений")],
            [KeyboardButton(text="Мои личные дедлайны")],
            [KeyboardButton(text="Настройка часового пояса")]
        ], resize_keyboard=True)
        await message.answer("Привет, главный модератор! Выберите действие:", reply_markup=moderator_keyboard)
    else:
        cursor.execute("SELECT username FROM moderators WHERE username = ?", (message.from_user.username,))
        is_moderator = cursor.fetchone()
        if is_moderator:
            moderator_keyboard = ReplyKeyboardMarkup(keyboard=[
                [KeyboardButton(text="Показать дедлайны")],
                [KeyboardButton(text="Добавить дедлайн")],
                [KeyboardButton(text="Удалить дедлайн")],
                [KeyboardButton(text="Редактировать дедлайн")],
                [KeyboardButton(text="Настройки уведомлений")],
                [KeyboardButton(text="Мои личные дедлайны")],
                [KeyboardButton(text="Настройка часового пояса")]
            ], resize_keyboard=True)
            await message.answer("Привет, модератор! Выберите действие:", reply_markup=moderator_keyboard)
        else:
            await message.answer("Привет! Выберите действие:", reply_markup=user_keyboard)

@router.message(lambda message: message.text == "Добавить дедлайн")
async def start_adding_deadline(message: types.Message, state: FSMContext):
    await message.answer("Введите дату и время дедлайна в формате DD.MM.YYYY HH:MM:")
    await state.set_state(AddDeadline.waiting_for_date)

@router.message(AddDeadline.waiting_for_date)
async def process_deadline_date(message: types.Message, state: FSMContext):
    try:
        user_timezone = await get_user_timezone(message.from_user.id)
        deadline_datetime = datetime.strptime(message.text.strip(), "%d.%m.%Y %H:%M")
        deadline_datetime = user_timezone.localize(deadline_datetime)
        await state.update_data(deadline_date=deadline_datetime)
        await message.answer("Теперь введите описание дедлайна:")
        await state.set_state(AddDeadline.waiting_for_description)
    except ValueError:
        await message.answer(
            "Неправильный формат даты и времени. Пожалуйста, введите дату и время в формате DD.MM.YYYY HH:MM.")

@router.message(AddDeadline.waiting_for_description)
async def process_deadline_description(message: types.Message, state: FSMContext):
    user_data = await state.get_data()
    deadline_date = user_data['deadline_date']
    description = message.text
    cursor.execute(
        "INSERT INTO deadlines (description, deadline_date, notification_options, user_id, is_personal) VALUES (?, ?, ?, ?, ?)",
        (description, deadline_date.strftime("%Y-%m-%d %H:%M:%S"), '', message.from_user.id, 1))
    conn.commit()
    await message.answer(f"Дедлайн '{description}' успешно добавлен на {deadline_date.strftime('%d.%m.%Y %H:%M')}.")
    await send_welcome(message)
    await state.clear()

@router.message(lambda message: message.text == "Показать дедлайны")
async def show_deadlines(message: types.Message):
    user_timezone = await get_user_timezone(message.from_user.id)
    cursor.execute(
        "SELECT id, description, deadline_date FROM deadlines WHERE is_personal = 0 OR user_id = ? ORDER BY deadline_date",
        (message.from_user.id,))
    deadlines = cursor.fetchall()
    if deadlines:
        response = "Список дедлайнов:\n\n"
        for idx, (deadline_id, desc, date) in enumerate(deadlines, 1):
            try:
                deadline_date = datetime.strptime(date, "%Y-%m-%d %H:%M:%S")
                deadline_date = pytz.UTC.localize(deadline_date).astimezone(user_timezone)
                now = datetime.now(user_timezone)
                if deadline_date > now:
                    time_left = deadline_date - now
                    days = time_left.days
                    hours, remainder = divmod(time_left.seconds, 3600)
                    minutes, _ = divmod(remainder, 60)
                    time_str = f"Осталось: {days} дней, {hours} часов, {minutes} минут"
                else:
                    time_overdue = now - deadline_date
                    days_overdue = time_overdue.days
                    time_str = f"Просрочено на {days_overdue} дней"
                response += f"Дедлайн #{idx}:\n- Описание: {desc}\n- Дата и время: {deadline_date.strftime('%d.%m.%Y %H:%M')}\n- {time_str}\n\n"
            except ValueError:
                response += f"Дедлайн #{idx}:\n- Описание: {desc}\n- Дата: {date} (Неправильный формат)\n\n"
        await message.answer(response)
    else:
        await message.answer("Нет активных дедлайнов.")

@router.message(lambda message: message.text == "Удалить дедлайн")
async def delete_deadline(message: types.Message, state: FSMContext):
    cursor.execute(
        "SELECT id, description, deadline_date FROM deadlines WHERE is_personal = 0 OR user_id = ? ORDER BY deadline_date",
        (message.from_user.id,))
    deadlines = cursor.fetchall()
    if deadlines:
        response = "Выберите номер дедлайна, который хотите удалить:\n\n"
        for idx, (deadline_id, desc, date) in enumerate(deadlines, 1):
            try:
                deadline_date = datetime.strptime(date, "%Y-%m-%d %H:%M:%S").strftime("%d.%m.%Y %H:%M")
                response += f"#{idx} - Описание: {desc}, Дата и время: {deadline_date}\n"
            except ValueError:
                response += f"#{idx} - Описание: {desc}, Дата: {date} (Неправильный формат)\n"
        await message.answer(response)
        await state.set_state(AddDeadline.waiting_for_delete)
    else:
        await message.answer("Нет дедлайнов для удаления.")

@router.message(AddDeadline.waiting_for_delete)
async def process_delete_deadline(message: types.Message, state: FSMContext):
    try:
        selected_deadline_idx = int(message.text.strip()) - 1
        cursor.execute("SELECT id FROM deadlines WHERE is_personal = 0 OR user_id = ? ORDER BY deadline_date",
                       (message.from_user.id,))
        deadlines = cursor.fetchall()
        if 0 <= selected_deadline_idx < len(deadlines):
            deadline_id = deadlines[selected_deadline_idx][0]
            cursor.execute("DELETE FROM deadlines WHERE id = ?", (deadline_id,))
            conn.commit()
            await message.answer("Дедлайн успешно удален.")
            await send_welcome(message)
        else:
            await message.answer("Неверный номер дедлайна. Пожалуйста, попробуйте еще раз.")
    except ValueError:
        await message.answer("Неверный ввод. Пожалуйста, введите номер дедлайна.")
    await state.clear()

@router.message(lambda message: message.text == "Настройки уведомлений")
async def notification_settings(message: types.Message):
    keyboard = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="1 час до конца", callback_data="notify_1hour")],
        [InlineKeyboardButton(text="1 день до конца", callback_data="notify_1day")],
        [InlineKeyboardButton(text="2 дня до конца", callback_data="notify_2days")],
        [InlineKeyboardButton(text="3 дня до конца", callback_data="notify_3days")],
        [InlineKeyboardButton(text="1 неделя до конца", callback_data="notify_1week")],
        [InlineKeyboardButton(text="Назад", callback_data="back_to_main")]
    ])
    await message.answer("Выберите, за сколько времени вы хотите получать уведомления:", reply_markup=keyboard)

@router.callback_query(lambda c: c.data.startswith('notify_'))
async def process_notification_callback(callback_query: types.CallbackQuery):
    notification_option = callback_query.data.split('_')[1]
    user_id = callback_query.from_user.id

    cursor.execute("SELECT notification_options FROM deadlines WHERE user_id = ?", (user_id,))
    current_options = cursor.fetchone()

    if current_options:
        options = set(current_options[0].split(',')) if current_options[0] else set()
    else:
        options = set()

    if notification_option in options:
        options.remove(notification_option)
    else:
        options.add(notification_option)

    new_options = ','.join(options)
    cursor.execute("UPDATE deadlines SET notification_options = ? WHERE user_id = ?", (new_options, user_id))
    conn.commit()

    await update_notification_keyboard(callback_query.message, options)

async def update_notification_keyboard(message: types.Message, selected_options: set):
    keyboard = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text=f"1 час до конца {'✅' if '1hour' in selected_options else ''}",
                              callback_data="notify_1hour")],
        [InlineKeyboardButton(text=f"1 день до конца {'✅' if '1day' in selected_options else ''}",
                              callback_data="notify_1day")],
        [InlineKeyboardButton(text=f"2 дня до конца {'✅' if '2days' in selected_options else ''}",
                              callback_data="notify_2days")],
        [InlineKeyboardButton(text=f"3 дня до конца {'✅' if '3days' in selected_options else ''}",
                              callback_data="notify_3days")],
        [InlineKeyboardButton(text=f"1 неделя до конца {'✅' if '1week' in selected_options else ''}",
                              callback_data="notify_1week")],
        [InlineKeyboardButton(text="Назад", callback_data="back_to_main")]
    ])
    await message.edit_reply_markup(reply_markup=keyboard)

@router.callback_query(lambda c: c.data == 'back_to_main')
async def process_back_to_main(callback_query: types.CallbackQuery):
    await send_welcome(callback_query.message)

@router.message(lambda message: message.text == "Мои личные дедлайны")
async def show_personal_deadlines(message: types.Message):
    user_timezone = await get_user_timezone(message.from_user.id)
    cursor.execute("SELECT id, description, deadline_date FROM deadlines WHERE user_id = ? AND is_personal = 1 ORDER BY deadline_date",
                   (message.from_user.id,))
    deadlines = cursor.fetchall()
    if deadlines:
        response = "Список ваших личных дедлайнов:\n\n"
        for idx, (deadline_id, desc, date) in enumerate(deadlines, 1):
            try:
                deadline_date = datetime.strptime(date, "%Y-%m-%d %H:%M:%S")
                deadline_date = pytz.UTC.localize(deadline_date).astimezone(user_timezone)
                now = datetime.now(user_timezone)
                if deadline_date > now:
                    time_left = deadline_date - now
                    days = time_left.days
                    hours, remainder = divmod(time_left.seconds, 3600)
                    minutes, _ = divmod(remainder, 60)
                    time_str = f"Осталось: {days} дней, {hours} часов, {minutes} минут"
                else:
                    time_overdue = now - deadline_date
                    days_overdue = time_overdue.days
                    time_str = f"Просрочено на {days_overdue} дней"
                response += f"Дедлайн #{idx}:\n- Описание: {desc}\n- Дата и время: {deadline_date.strftime('%d.%m.%Y %H:%M')}\n- {time_str}\n\n"
            except ValueError:
                response += f"Дедлайн #{idx}:\n- Описание: {desc}\n- Дата: {date} (Неправильный формат)\n\n"
        await message.answer(response)
    else:
        await message.answer("У вас нет личных дедлайнов.")

@router.message(lambda message: message.text == "Добавить модератора" and message.from_user.id == MAIN_MODERATOR_ID)
async def request_moderator_username(message: types.Message):
    await message.answer("Введите никнейм пользователя, которого хотите добавить модератором, в формате @nickname:")

@router.message(lambda message: message.text.startswith('@') and message.from_user.id == MAIN_MODERATOR_ID)
async def add_moderator(message: types.Message):
    username = message.text.strip()
    cursor.execute("SELECT username FROM moderators WHERE username = ?", (username,))
    moderator_exists = cursor.fetchone()
    if moderator_exists:
        await message.answer(f"Пользователь {username} уже является модератором.")
    else:
        cursor.execute("INSERT INTO moderators (username) VALUES (?)", (username,))
        conn.commit()
        await message.answer(f"Пользователь {username} успешно добавлен в модераторы.")

@router.message(lambda message: message.text == "Редактировать дедлайн")
async def edit_deadline(message: types.Message, state: FSMContext):
    cursor.execute(
        "SELECT id, description, deadline_date FROM deadlines WHERE is_personal = 0 OR user_id = ? ORDER BY deadline_date",
        (message.from_user.id,))
    deadlines = cursor.fetchall()
    if deadlines:
        response = "Выберите номер дедлайна, который хотите отредактировать:\n\n"
        for idx, (deadline_id, desc, date) in enumerate(deadlines, 1):
            try:
                deadline_date = datetime.strptime(date, "%Y-%m-%d %H:%M:%S").strftime("%d.%m.%Y %H:%M")
                response += f"#{idx} - Описание: {desc}, Дата и время: {deadline_date}\n"
            except ValueError:
                response += f"#{idx} - Описание: {desc}, Дата: {date} (Неправильный формат)\n"
        await message.answer(response)
        await state.set_state(AddDeadline.waiting_for_edit)
    else:
        await message.answer("Нет дедлайнов для редактирования.")

@router.message(AddDeadline.waiting_for_edit)
async def process_edit_deadline(message: types.Message, state: FSMContext):
    try:
        selected_deadline_idx = int(message.text.strip()) - 1
        cursor.execute("SELECT id FROM deadlines WHERE is_personal = 0 OR user_id = ? ORDER BY deadline_date",
                       (message.from_user.id,))
        deadlines = cursor.fetchall()
        if 0 <= selected_deadline_idx < len(deadlines):
            deadline_id = deadlines[selected_deadline_idx][0]
            await state.update_data(editing_deadline_id=deadline_id)
            await message.answer("Введите новую дату и время дедлайна в формате DD.MM.YYYY HH:MM:")
            await state.set_state(AddDeadline.waiting_for_new_date)
        else:
            await message.answer("Неверный номер дедлайна. Пожалуйста, попробуйте еще раз.")
    except ValueError:
        await message.answer("Неверный ввод. Пожалуйста, введите номер дедлайна.")

@router.message(AddDeadline.waiting_for_new_date)
async def process_new_deadline_date(message: types.Message, state: FSMContext):
    try:
        user_timezone = await get_user_timezone(message.from_user.id)
        new_deadline_datetime = datetime.strptime(message.text.strip(), "%d.%m.%Y %H:%M")
        new_deadline_datetime = user_timezone.localize(new_deadline_datetime)
        await state.update_data(new_deadline_date=new_deadline_datetime)
        await message.answer("Теперь введите новое описание дедлайна:")
        await state.set_state(AddDeadline.waiting_for_new_description)
    except ValueError:
        await message.answer(
            "Неправильный формат даты и времени. Пожалуйста, введите дату и время в формате DD.MM.YYYY HH:MM.")

@router.message(AddDeadline.waiting_for_new_description)
async def process_new_deadline_description(message: types.Message, state: FSMContext):
    user_data = await state.get_data()
    deadline_id = user_data['editing_deadline_id']
    new_deadline_date = user_data['new_deadline_date']
    new_description = message.text
    cursor.execute(
        "UPDATE deadlines SET description = ?, deadline_date = ? WHERE id = ?",
        (new_description, new_deadline_date.strftime("%Y-%m-%d %H:%M:%S"), deadline_id))
    conn.commit()
    await message.answer(f"Дедлайн успешно отредактирован. Новое описание: '{new_description}', новая дата: {new_deadline_date.strftime('%d.%m.%Y %H:%M')}.")
    await send_welcome(message)
    await state.clear()

@router.message(lambda message: message.text == "Настройка часового пояса")
async def timezone_settings(message: types.Message):
    keyboard = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="UTC", callback_data="tz_UTC")],
        [InlineKeyboardButton(text="Europe/Moscow", callback_data="tz_Europe/Moscow")],
        [InlineKeyboardButton(text="Asia/Yekaterinburg", callback_data="tz_Asia/Yekaterinburg")],
        [InlineKeyboardButton(text="Asia/Novosibirsk", callback_data="tz_Asia/Novosibirsk")],
        [InlineKeyboardButton(text="Asia/Vladivostok", callback_data="tz_Asia/Vladivostok")],
        [InlineKeyboardButton(text="Назад", callback_data="back_to_main")]
    ])
    await message.answer("Выберите ваш часовой пояс:", reply_markup=keyboard)

@router.callback_query(lambda c: c.data.startswith('tz_'))
async def process_timezone_callback(callback_query: types.CallbackQuery):
    timezone_str = callback_query.data.split('_')[1]
    user_id = callback_query.from_user.id

    cursor.execute("INSERT OR REPLACE INTO user_settings (user_id, timezone) VALUES (?, ?)",
                   (user_id, timezone_str))
    conn.commit()

    await callback_query.answer(f"Часовой пояс установлен: {timezone_str}")
    await callback_query.message.edit_text(f"Ваш часовой пояс: {timezone_str}")

async def get_user_timezone(user_id):
    cursor.execute("SELECT timezone FROM user_settings WHERE user_id = ?", (user_id,))
    result = cursor.fetchone()
    if result:
        return pytz.timezone(result[0])
    else:
        return pytz.UTC

async def send_notifications():
    while True:
        now = datetime.now(pytz.UTC)
        cursor.execute("SELECT id, description, deadline_date, notification_options, user_id FROM deadlines")
        deadlines = cursor.fetchall()

        for deadline_id, description, deadline_date, notification_options, user_id in deadlines:
            deadline_date = datetime.strptime(deadline_date, "%Y-%m-%d %H:%M:%S").replace(tzinfo=pytz.UTC)
            time_left = deadline_date - now

            if notification_options:
                options = notification_options.split(',')
                for option in options:
                    if option == '1hour' and timedelta(hours=1) <= time_left < timedelta(hours=1, minutes=1):
                        await bot.send_message(user_id, f"❗️дедлайн '{description}' через 1 час❗️")
                    elif option == '1day' and timedelta(days=1) <= time_left < timedelta(days=1, minutes=1):
                        await bot.send_message(user_id, f"❗️дедлайн '{description}' через 1 день❗️")
                    elif option == '2days' and timedelta(days=2) <= time_left < timedelta(days=2, minutes=1):
                        await bot.send_message(user_id, f"❗️дедлайн '{description}' через 2 дня❗️")
                    elif option == '3days' and timedelta(days=3) <= time_left < timedelta(days=3, minutes=1):
                        await bot.send_message(user_id, f"❗️дедлайн '{description}' через 3 дня❗️")
                    elif option == '1week' and timedelta(weeks=1) <= time_left < timedelta(weeks=1, minutes=1):
                        await bot.send_message(user_id, f"❗️дедлайн '{description}' через 1 неделю❗️")

        await asyncio.sleep(60)  # Проверка каждую минуту

dp.include_router(router)

async def main():
    await dp.start_polling(bot)

if __name__ == '__main__':
    loop = asyncio.get_event_loop()
    loop.create_task(send_notifications())
    loop.run_until_complete(main())